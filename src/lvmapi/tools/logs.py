#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-08-06
# @Filename: logs.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import json
import pathlib
import warnings
from datetime import UTC, datetime

import polars
import psycopg
from psycopg.sql import SQL, Identifier
from pydantic import BaseModel

from sdsstools import get_sjd

from lvmapi import config


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


def get_exposure_data(mjd: int):
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
            lamp_name: header.get(lamp_header, None) == "ON"
            for lamp_header, lamp_name in [
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

    return data


NIGHT_LOG_CATEGORIES = set(["observers", "weather", "issues", "other"])


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


async def add_night_log_comment(
    sjd: int | None,
    comment: str,
    category: str | None = None,
):
    """Adds a comment to the night log."""

    uri = config["database.uri"]
    table_night_log = Identifier(*config["database.tables.night_log"].split("."))
    table_comment = Identifier(*config["database.tables.night_log_comment"].split("."))

    sjd = sjd or get_sjd("LCO")

    if category is None:
        warnings.warn("No category provided. Defaulting to 'other'.")
        category = "other"

    category = category.lower()
    if category not in NIGHT_LOG_CATEGORIES:
        warnings.warn(f'Non-standard category "{category}".')

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

            pk = await result.fetchone()
            if pk is not None:
                pk = pk[0]
            else:
                # Insert a new entry in night_log.
                result = await acursor.execute(
                    SQL(
                        "INSERT INTO {table_night_log} (mjd, sent) "
                        "VALUES (%s, false) RETURNING pk"
                    ).format(table_night_log=table_night_log),
                    (sjd,),
                )

                fetch_pk = await result.fetchone()
                if not fetch_pk:
                    raise RuntimeError("Failed to insert new entry in night_log.")

                pk = fetch_pk[0]
                await aconn.commit()

            # The observers category should have a single comment.
            if category == "observers":
                await acursor.execute(
                    SQL(
                        "DELETE FROM {table_comment} WHERE night_log_pk = %s "
                        "AND category = %s"
                    ).format(table_comment=table_comment),
                    (pk, "observers"),
                )

            # Now add the comment.
            result = await acursor.execute(
                SQL(
                    "INSERT INTO {table_comment} "
                    "(night_log_pk, time, category, comment) "
                    "VALUES (%s, %s, %s, %s) RETURNING pk"
                ).format(table_comment=table_comment),
                (pk, datetime.now(UTC), category, comment),
            )

            fetch_pk = await result.fetchone()
            if not fetch_pk:
                raise RuntimeError("Failed to insert new comment in night_log_comment.")

            await aconn.commit()

    return fetch_pk[0]


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

    result = {
        "mjd": sjd,
        "current": sjd == get_sjd("LCO"),
        "exists": True,
        "sent": night_log[1],
        "observers": None,
        "comments": {category: [] for category in NIGHT_LOG_CATEGORIES - {"observers"}},
    }

    for comment in comments:
        pk, dt, category, text = comment
        if category not in NIGHT_LOG_CATEGORIES:
            category = "other"

        if category == "observers":
            result["observers"] = text
        else:
            result["comments"][category].append({"pk": pk, "date": dt, "comment": text})

    return result
