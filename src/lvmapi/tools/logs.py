#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-08-06
# @Filename: logs.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import io
import json
import pathlib
import smtplib
import warnings
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from typing import Any, Literal, TypedDict, get_args, overload

import polars
import psycopg
from astropy.time import Time
from jinja2 import Environment, FileSystemLoader
from psycopg.sql import SQL, Identifier
from pydantic import BaseModel

from sdsstools import get_sjd, run_in_executor

from lvmapi import config
from lvmapi.tools.notifications import create_notification, get_notifications
from lvmapi.tools.rabbitmq import CluClient
from lvmapi.tools.schedule import get_ephemeris_summary


class ExposureDataDict(BaseModel):
    """A dictionary of exposure data."""

    exposure_no: int
    mjd: int
    obstime: str = ""
    image_type: str = ""
    exposure_time: float | None = None
    ra: float | None = None
    dec: float | None = None
    airmass: float | None = None
    lamps: dict[str, bool] = {}
    n_standards: int = 0
    n_cameras: int = 0
    object: str = ""


def get_spectro_mjds():
    """Returns a list of MJDs with spectrograph data (or at least a folder)."""

    uri = config["database.uri"]
    table = config["database.tables.exposures"]

    df = polars.read_database_uri(
        f"SELECT DISTINCT(mjd) AS mjd FROM {table}",
        uri,
        engine="adbc",
    )

    return sorted(df["mjd"].unique().to_list())


def get_exposures(mjd: int):
    """Returns a list of spectrograph exposures for an MJD."""

    files = pathlib.Path(f"/data/spectro/{mjd}/").glob("*.fits.gz")

    return files


@overload
def get_exposure_data(
    mjd: int,
    as_dataframe: Literal[False] = False,
    compact_lamps: bool = False,
) -> dict[int, ExposureDataDict]: ...


@overload
def get_exposure_data(
    mjd: int,
    as_dataframe: Literal[True] = True,
    compact_lamps: bool = False,
) -> polars.DataFrame: ...


def get_exposure_data(
    mjd: int,
    as_dataframe: bool = False,
    compact_lamps: bool = False,
) -> dict[int, ExposureDataDict] | polars.DataFrame:
    """Returns the data for the exposures from a given MJD."""

    uri = config["database.uri"]
    table = config["database.tables.exposures"]

    df = polars.read_database_uri(
        f"""SELECT  exposure_no, image_type, spec, ccd, tile_id,
                    jsonb_path_query("header", '$')::TEXT as header
            FROM {table} WHERE mjd = {mjd}
        """,
        uri,
        engine="adbc",
    ).sort(["exposure_no", "spec", "ccd"])

    data: dict[int, ExposureDataDict] = {}
    exposure_nos = df["exposure_no"].unique().to_list()

    for exposure_no in exposure_nos:
        exp_data = df.filter(polars.col.exposure_no == exposure_no)
        n_cameras = len(exp_data)

        if n_cameras == 0:
            data[exposure_no] = ExposureDataDict(
                exposure_no=exposure_no,
                mjd=mjd,
                n_cameras=0,
            )
            continue

        header = json.loads(exp_data["header"][0])

        obstime = header.get("OBSTIME", "")
        image_type = header.get("IMAGETYP", "")
        exposure_time = header.get("EXPTIME", None)
        ra = header.get("TESCIRA", None)
        dec = header.get("TESCIDE", None)
        airmass = header.get("TESCIAM", None)
        std_acq = [header.get(f"STD{nn}ACQ", None) for nn in range(1, 13)]
        n_standards = sum([std for std in std_acq if std is not None])
        object = header.get("OBJECT", "")

        lamps = {
            lname if not compact_lamps else lname[0]: header.get(lheader, None) == "ON"
            for lheader, lname in [
                ("ARGON", "Argon"),
                ("NEON", "Neon"),
                ("LDLS", "LDLS"),
                ("QUARTZ", "Quartz"),
                ("HGNE", "HgNe"),
                ("XENON", "Xenon"),
            ]
        }

        data[exposure_no] = ExposureDataDict(
            exposure_no=exposure_no,
            mjd=mjd,
            obstime=obstime,
            image_type=image_type,
            exposure_time=exposure_time,
            ra=ra,
            dec=dec,
            airmass=airmass if airmass < 100 else -1,
            lamps=lamps,
            n_standards=n_standards,
            n_cameras=n_cameras,
            object=object,
        )

    if not as_dataframe:
        return data

    exposure_records: list[dict[str, Any]] = []
    for exp in data.values():
        exp_dict = dict(exp)

        # Convert the lamps to a string
        lamps = exp_dict.pop("lamps")
        sep = "," if not compact_lamps else ""
        lamps_on = sep.join([lamp for lamp, on in lamps.items() if on])
        exp_dict["lamps"] = lamps_on

        exposure_records.append(exp_dict)

    df = polars.DataFrame(exposure_records)

    return df


async def get_exposure_table_ascii(
    sjd: int | None = None,
    columns: list[str] | None = None,
    full_obstime: bool = True,
    compact_lamps: bool = False,
):
    """Returns the exposure table as an ASCII string."""

    sjd = sjd or get_sjd("LCO")

    df = await run_in_executor(
        get_exposure_data, sjd, as_dataframe=True, compact_lamps=compact_lamps
    )
    assert isinstance(df, polars.DataFrame)

    if df.height == 0:
        return None

    # Rename some columns to make the table narrower.
    # Use only second precision in obstime.
    exposure_df = df.rename(
        {
            "exposure_no": "exp_no",
            "image_type": "type",
            "exposure_time": "exp_time",
            "n_standards": "n_std",
            "n_cameras": "n_cam",
        }
    ).with_columns(
        obstime=polars.col.obstime.str.replace("T", " ").str.replace(r"\.\d+", "")
    )

    if not full_obstime:
        exposure_df = exposure_df.with_columns(
            obstime=polars.col.obstime.str.split(" ").list.get(1).cast(polars.String())
        )

    # Drop MJD column.
    exposure_df = exposure_df.drop("mjd")

    if columns:
        exposure_df = exposure_df.select(columns)

    n_tiles = exposure_df.filter(
        polars.col.type == "object",
        polars.col.object.str.starts_with("tile_id="),
    ).height

    exposure_io = io.StringIO()
    with polars.Config(
        tbl_formatting="ASCII_FULL_CONDENSED",
        tbl_hide_column_data_types=True,
        tbl_hide_dataframe_shape=True,
        tbl_cols=-1,
        tbl_rows=-1,
        tbl_width_chars=1000,
    ):
        print(f"# science_tiles: {n_tiles}\n", file=exposure_io)
        print(exposure_df, file=exposure_io)

    exposure_io.seek(0)
    return exposure_io.read().strip()


async def get_actor_versions(actor: str | None = None):
    """Returns a list of actor versions."""

    actors: list[str] = config["actors"]["list"]
    if actor is not None:
        actors = [actor]

    async with CluClient() as client:
        version_cmds = await asyncio.gather(
            *[client.send_command(actor, "version") for actor in actors]
        )

    versions: dict[str, str | None] = {}
    for iactor, version_cmd in enumerate(version_cmds):
        try:
            version: str | None = version_cmd.replies.get("version")
        except Exception:
            version = None
        versions[actors[iactor]] = version

    return versions


async def get_night_log_mjds():
    """Returns a list of MJDs with night log data."""

    uri = config["database.uri"]
    table_night_log = config["database.tables.night_log"]

    df = polars.read_database_uri(
        f"SELECT DISTINCT(mjd) AS mjd FROM {table_night_log}",
        uri,
        engine="adbc",
    )

    return sorted(df["mjd"].unique().to_list())


async def create_night_log_entry(mjd: int | None = None):
    """Creates a new entry in the night log for an MJD."""

    uri = config["database.uri"]
    table_night_log = Identifier(*config["database.tables.night_log"].split("."))
    table_comment = Identifier(*config["database.tables.night_log_comment"].split("."))

    mjd = mjd or get_sjd("LCO")

    async with await psycopg.AsyncConnection.connect(uri) as aconn:
        async with aconn.cursor() as acursor:
            # Insert new MJD or do nothing if already exists.
            await acursor.execute(
                SQL(
                    "INSERT INTO {table_night_log} (mjd, sent) VALUES (%s, false) "
                    "ON CONFLICT DO NOTHING RETURNING pk;"
                ).format(table_night_log=table_night_log),
                (mjd,),
            )
            is_new = (await acursor.fetchone()) is not None

            # Add a placeholder for the observers.
            if is_new:
                await acursor.execute(
                    SQL(
                        """
            INSERT INTO {table_comment} (night_log_pk, time, category, comment)
            VALUES ((SELECT pk FROM {table_night_log} WHERE mjd = %s), %s, %s, %s)
            """
                    ).format(
                        table_comment=table_comment,
                        table_night_log=table_night_log,
                    ),
                    (mjd, datetime.now(UTC), "observers", "Overwatcher"),
                )

            await aconn.commit()

    return mjd


NightLogCategories = Literal["weather", "issues", "other", "observers", "overwatcher"]


async def add_night_log_comment(
    sjd: int | None,
    comment: str,
    category: NightLogCategories | None = None,
    comment_pk: int | None = None,
):
    """Adds or updates a comment in the night log."""

    uri = config["database.uri"]
    table_night_log = Identifier(*config["database.tables.night_log"].split("."))
    table_comment = Identifier(*config["database.tables.night_log_comment"].split("."))

    sjd = sjd or get_sjd("LCO")

    if category is None:
        warnings.warn("No category provided. Defaulting to 'other'.")
        category = "other"

    if category not in get_args(NightLogCategories):
        raise ValueError(f"Invalid night log category {category!r}.")

    # Get a connection and cursor.
    async with await psycopg.AsyncConnection.connect(uri) as aconn:
        async with aconn.cursor() as acursor:
            # Check if there is already an entry for this SJD in night_log.
            result = await acursor.execute(
                SQL("SELECT pk FROM {night_log_table} WHERE mjd = %s").format(
                    night_log_table=table_night_log
                ),
                (sjd,),
            )

            night_log_pk = await result.fetchone()
            if night_log_pk is not None:
                night_log_pk = night_log_pk[0]
            else:
                # Insert a new entry in night_log.
                result = await acursor.execute(
                    SQL(
                        "INSERT INTO {table_night_log} (mjd, sent) "
                        "VALUES (%s, false) RETURNING pk"
                    ).format(table_night_log=table_night_log),
                    (sjd,),
                )

                fetch_night_log_pk = await result.fetchone()
                if not fetch_night_log_pk:
                    raise RuntimeError("Failed to insert new entry in night_log.")

                night_log_pk = fetch_night_log_pk[0]
                await aconn.commit()

            # The observers category should have a single comment.
            if category == "observers":
                await acursor.execute(
                    SQL(
                        "DELETE FROM {table_comment} WHERE night_log_pk = %s "
                        "AND category = %s"
                    ).format(table_comment=table_comment),
                    (night_log_pk, "observers"),
                )

            # Depending on whether we are updating or adding a new comment,
            # we use different queries.
            if comment_pk is None:
                query = """
                        INSERT INTO {table_comment}
                        (night_log_pk, time, category, comment)
                        VALUES (%s, %s, %s, %s);
                        """
                params = (night_log_pk, datetime.now(UTC), category, comment)
            else:
                query = """
                        UPDATE {table_comment}
                        SET time = %s, comment = %s
                        WHERE pk = %s;
                        """
                params = (datetime.now(UTC), comment, comment_pk)

            # Run the query.
            try:
                await acursor.execute(
                    SQL(query).format(table_comment=table_comment),
                    params,
                )
            except Exception as ee:
                raise RuntimeError(f"Failed to insert comment: {ee}")

            await aconn.commit()

    return comment_pk


async def delete_night_log_comment(pk: int):
    """Deletes a comment from the night log."""

    uri = config["database.uri"]
    table_comment = Identifier(*config["database.tables.night_log_comment"].split("."))

    async with await psycopg.AsyncConnection.connect(uri) as aconn:
        async with aconn.cursor() as acursor:
            await acursor.execute(
                SQL("DELETE FROM {table_comment} WHERE pk = %s").format(
                    table_comment=table_comment
                ),
                (pk,),
            )
            await aconn.commit()

    return True


async def get_night_log_data(sjd: int | None = None):
    """Returns the comments and other relevant data for the night log."""

    uri = config["database.uri"]
    table_night_log = Identifier(*config["database.tables.night_log"].split("."))
    table_comment = Identifier(*config["database.tables.night_log_comment"].split("."))

    sjd = sjd or get_sjd("LCO")

    query1 = "SELECT nl.pk, nl.sent FROM {night_log_table} AS nl WHERE nl.mjd = %s"
    query2 = """
        SELECT nlc.pk, nlc.time, nlc.category, nlc.comment
            FROM {night_log_table} AS nl
            JOIN {table_comment} AS nlc ON nl.pk = nlc.night_log_pk
            WHERE nl.mjd = %s
            ORDER BY nlc.time
    """

    async with await psycopg.AsyncConnection.connect(uri) as aconn:
        async with aconn.cursor() as acursor:
            # Get the night log entry for the SJD.
            nl = await acursor.execute(
                SQL(query1).format(night_log_table=table_night_log),
                (sjd,),
            )
            night_log = await nl.fetchone()

            # And the comments
            nlc = await acursor.execute(
                SQL(query2).format(
                    night_log_table=table_night_log,
                    table_comment=table_comment,
                ),
                (sjd,),
            )
            comments = await nlc.fetchall()

    if night_log is None:
        return {
            "mjd": sjd,
            "current": sjd == get_sjd("LCO"),
            "exists": False,
        }

    valid_categories = set(get_args(NightLogCategories))

    result = {
        "mjd": sjd,
        "current": sjd == get_sjd("LCO"),
        "exists": True,
        "sent": night_log[1],
        "observers": None,
        "comments": {category: [] for category in valid_categories - {"observers"}},
    }

    for comment in comments:
        pk, dt, category, text = comment
        if category not in valid_categories:
            category = "other"

        if category == "observers":
            result["observers"] = text
        else:
            result["comments"][category].append({"pk": pk, "date": dt, "comment": text})

    return result


def notifications_to_list(notifications: list[dict[str, Any]]) -> list[str]:
    """Converts a list of notifications to a list of strings."""

    if len(notifications) == 0:
        return ["No notifications"]

    notification_list: list[str] = []
    for notification in notifications:
        date = notification["date"].strftime("%Y-%m-%d %H:%M:%S")
        level = notification["level"].upper()
        message = notification["message"]
        payload = ", ".join(
            [f"{key}: {value}" for key, value in notification["payload"].items()]
        )

        notification_str = f"{date} - {level} - {message}"
        if payload:
            notification_str += f" {{ {payload} }}"

        notification_list.append(notification_str)

    return notification_list


async def get_plaintext_night_log(sjd: int | None = None):
    """Returns the night log as a plaintext string."""

    sjd = sjd or get_sjd("LCO")
    data = await get_night_log_data(sjd)

    nigh_log = """LVM Telescopes, Las Campanas Observatory, SDSSV

=============
Observing Log
=============

{date} (MJD {sjd})

Observing Team: {observers}

Observing Summary
=================

Weather
-------
{weather}

Issues/Bugs
-----------
{issues}

Other
-----
{other}

Overwatcher
-----------
{overwatcher}

Night metrics
-------------
- Night length: {night_length}.
- Number of object exposures: {n_object_exps}.
- Time not observing: {time_lost}
- Efficiency (with nominal overheads): {efficiency_nominal}%
- Efficiency (with readout): {efficiency_no_readout}%
- Efficiency (without readout): {efficiency_no_readout}%

Exposure data
-------------
{exposure_data}

Versions
--------
{versions}

Notifications
-------------
{notifications}

"""

    date = Time(sjd - 1, format="mjd").datetime.strftime("%A, %B %-d, %Y")

    observers = data["observers"] or "Overwatcher"

    comments = data["comments"]
    weather = ["- {}".format(comms["comment"]) for comms in comments["weather"]]
    issues = ["- {}".format(comms["comment"]) for comms in comments["issues"]]
    other = ["- {}".format(comms["comment"]) for comms in comments["other"]]
    overwatcher = ["- {}".format(comms["comment"]) for comms in comments["overwatcher"]]

    exposure_table = await get_exposure_table_ascii(
        sjd,
        columns=[
            "exp_no",
            "obstime",
            "type",
            "exp_time",
            "ra",
            "dec",
            "airmass",
            "lamps",
            "object",
        ],
        full_obstime=False,
        compact_lamps=True,
    )

    versions = await get_actor_versions()
    versions_l = [f"{actor}: {version or '?'}" for actor, version in versions.items()]

    notifications = await get_notifications(sjd)

    metrics = get_night_metrics(sjd)
    metrics_data = {
        "night_length": secs_to_hours(metrics["night_length"]),
        "n_object_exps": metrics["n_object_exps"],
        "time_lost": secs_to_hours(metrics["time_lost"])
        if metrics["night_started"]
        else "-",
        "efficiency_nominal": metrics["efficiency_nominal"]
        if metrics["night_started"]
        else "-",
        "efficiency_no_readout": metrics["efficiency_no_readout"]
        if metrics["night_started"]
        else "-",
        "efficiency_readout": metrics["efficiency_readout"]
        if metrics["night_started"]
        else "-",
    }

    return nigh_log.format(
        date=date,
        sjd=sjd,
        observers=observers,
        weather="\n".join(weather) or "No comments",
        issues="\n".join(issues) or "No comments",
        other="\n".join(other) or "No comments",
        overwatcher="\n".join(overwatcher) or "No comments",
        versions="\n".join(versions_l),
        exposure_data=exposure_table or "No exposures found",
        notifications="\n".join(notifications_to_list(notifications)),
        **metrics_data,
    )


def secs_to_hours(secs: float) -> str:
    """Converts seconds to hours."""

    hours = int(secs / 3600)
    minutes = int((secs % 3600) / 60)

    return f"{hours}h{minutes:02d}m"


async def email_night_log(
    sjd: int | None = None,
    update_database: bool = True,
    send_slack_notification: bool = True,
    only_if_not_sent: bool = False,
):
    """Emails the night log for an SJD."""

    sjd = sjd or get_sjd("LCO")

    root = pathlib.Path(__file__).parents[1]
    template = root / config["night_logs.email_template"]
    loader = FileSystemLoader(template.parent)

    env = Environment(
        loader=loader,
        lstrip_blocks=True,
        trim_blocks=True,
    )
    html_template = env.get_template(template.name)

    data = await get_night_log_data(sjd)
    exposure_table = await get_exposure_table_ascii(
        sjd,
        columns=[
            "exp_no",
            "obstime",
            "type",
            "exp_time",
            "ra",
            "dec",
            "airmass",
            "lamps",
            "object",
        ],
        full_obstime=False,
        compact_lamps=True,
    )

    if data["sent"] and only_if_not_sent:
        raise RuntimeError(f"Night log for MJD {sjd} has already been sent.")

    observers = data["observers"] or "Overwatcher"
    date = Time(sjd - 1, format="mjd").datetime.strftime("%A, %B %-d, %Y")
    lvmweb_url = config["night_logs.lvmweb_url"] + str(sjd)

    versions = await get_actor_versions()
    notifications = await get_notifications(sjd)

    metrics = get_night_metrics(sjd)
    metrics_data = {
        "night_length": secs_to_hours(metrics["night_length"]),
        "n_object_exps": metrics["n_object_exps"],
        "time_lost": secs_to_hours(metrics["time_lost"]),
        "efficiency_nominal": metrics["efficiency_nominal"],
        "efficiency_no_readout": metrics["efficiency_no_readout"],
        "efficiency_readout": metrics["efficiency_readout"],
        "night_started": metrics["night_started"],
    }

    html_message = html_template.render(
        sjd=sjd,
        lvmweb_url=lvmweb_url,
        observers=observers,
        date=date,
        weather=data["comments"]["weather"],
        issues=data["comments"]["issues"],
        other=data["comments"]["other"],
        overwatcher=data["comments"]["overwatcher"],
        exposure_table=exposure_table.strip() if exposure_table else None,
        software_versions=versions,
        notifications=("\n".join(notifications_to_list(notifications))).strip(),
        metrics=metrics_data,
    )

    recipients = config["night_logs.email_recipients"]
    from_address = config["night_logs.email_from"]

    email_server = config["night_logs.email_server"]
    email_host, *email_rest = email_server.split(":")
    email_port: int = 0
    if len(email_rest) == 1:
        email_port = int(email_rest[0])

    email_reply_to = config["night_logs.email_reply_to"]

    msg = MIMEMultipart("alternative" if html_message else "mixed")
    msg["Subject"] = f"LVM Observing Summary for MJD {sjd}"
    msg["From"] = from_address
    msg["To"] = ", ".join(recipients)
    msg["Reply-To"] = email_reply_to

    plaintext_email = await get_plaintext_night_log(sjd)
    msg.attach(MIMEText(plaintext_email, "plain"))

    html = MIMEText(html_message, "html")
    msg.attach(html)

    with smtplib.SMTP(host=email_host, port=email_port) as smtp:
        smtp.sendmail(from_address, recipients, msg.as_string())

    if update_database:
        uri = config["database.uri"]
        table = Identifier(*config["database.tables.night_log"].split("."))
        query1 = "UPDATE {table} SET sent = true WHERE mjd = %s"

        async with await psycopg.AsyncConnection.connect(uri) as aconn:
            async with aconn.cursor() as acursor:
                await acursor.execute(SQL(query1).format(table=table), (sjd,))
                await aconn.commit()

    if send_slack_notification:
        await create_notification(
            f"The night log for MJD {sjd} can be found <{lvmweb_url}|here>.",
            level="INFO",
        )


class NightMetricsDict(TypedDict):
    """A dictionary of night metrics."""

    sjd: int
    twilight_start: float
    twilight_end: float
    night_length: float
    n_object_exps: int
    total_exp_time: float
    time_lost: float
    efficiency_no_readout: float
    efficiency_readout: float
    efficiency_nominal: float
    night_started: bool
    night_ended: bool


def get_night_metrics(sjd: int | None = None) -> NightMetricsDict:
    """Retrieves automatically calculated metrics for the night."""

    READOUT_OVERHEAD: float = 50
    NOMINAL_OVERHEAD: float = 90

    sjd = sjd or get_sjd("LCO")

    exposures = get_exposure_data(sjd, as_dataframe=True)
    ephemeris = get_ephemeris_summary(sjd)

    # Get beginning and end of the night.
    twilight_end = Time(ephemeris["twilight_end"], format="jd")
    twilight_start = Time(ephemeris["twilight_start"], format="jd")

    night_length = twilight_start.unix - twilight_end.unix
    current_night_length = night_length

    now = Time.now()

    if now.unix < twilight_end.unix and now.unix < twilight_start.unix:
        return {
            "sjd": sjd,
            "twilight_end": ephemeris["twilight_end"],
            "twilight_start": ephemeris["twilight_start"],
            "night_length": round(night_length, 2),
            "n_object_exps": 0,
            "total_exp_time": 0.0,
            "time_lost": 0.0,
            "efficiency_no_readout": 0.0,
            "efficiency_readout": 0.0,
            "efficiency_nominal": 0.0,
            "night_started": False,
            "night_ended": False,
        }

    if now.unix > twilight_end.unix and now.unix < twilight_start.unix:
        twilight_start = now
        current_night_length = twilight_start.unix - twilight_end.unix

    if (
        exposures.height == 0
        or exposures.filter(polars.col.image_type == "object").height == 0
    ):
        return {
            "sjd": sjd,
            "twilight_end": ephemeris["twilight_end"],
            "twilight_start": ephemeris["twilight_start"],
            "night_length": round(night_length, 2),
            "n_object_exps": 0,
            "total_exp_time": 0.0,
            "time_lost": twilight_start.unix - twilight_end.unix,
            "efficiency_no_readout": 0.0,
            "efficiency_readout": 0.0,
            "efficiency_nominal": 0.0,
            "night_started": True,
            "night_ended": False,
        }

    # Calculate exposure endtime
    exposures = exposures.with_columns(
        obstime=polars.col.obstime.str.to_datetime(),
        endtime=polars.from_epoch(
            polars.col.obstime.dt.timestamp("ms") / 1000 + polars.col.exposure_time,
            time_unit="s",
        ),
    )

    # Filter exposures that started during the night.
    exposures = exposures.filter(
        polars.col.image_type == "object",
        polars.col.obstime > twilight_end.datetime,
        polars.col.endtime < (twilight_start.datetime + timedelta(seconds=300)),
    )

    n_exp = exposures.height
    total_exp_time = exposures["exposure_time"].sum()

    # Efficiency with and without taking into account readout.
    eff_no_readout = total_exp_time / current_night_length
    eff_readout = (total_exp_time + n_exp * READOUT_OVERHEAD) / current_night_length
    eff_nominal = (total_exp_time + n_exp * NOMINAL_OVERHEAD) / current_night_length

    return {
        "sjd": sjd,
        "twilight_end": ephemeris["twilight_end"],
        "twilight_start": ephemeris["twilight_start"],
        "night_length": night_length,
        "n_object_exps": n_exp,
        "total_exp_time": round(total_exp_time, 2),
        "time_lost": round(current_night_length - total_exp_time, 2),
        "efficiency_no_readout": round(eff_no_readout * 100, 2),
        "efficiency_readout": round(eff_readout * 100, 2),
        "efficiency_nominal": round(eff_nominal * 100, 2),
        "night_started": now.unix >= twilight_end.unix,
        "night_ended": now.unix >= twilight_start.unix,
    }
