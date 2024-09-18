#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-07-24
# @Filename: tools.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import json
from datetime import UTC, datetime

from typing import get_args, overload

import polars
import psycopg
import psycopg.sql

from lvmopstools.devices.ion import read_ion_pumps, toggle_ion_pump
from lvmopstools.devices.specs import (
    exposure_etr,
    spectrograph_mechanics,
    spectrograph_pressures,
    spectrograph_status,
    spectrograph_temperature_label,
    spectrograph_temperatures,
)
from lvmopstools.devices.thermistors import channel_to_valve, read_thermistors

from lvmapi import config
from lvmapi.tools.influxdb import query_influxdb
from lvmapi.types import Cameras, Sensors, SpecStatus, Spectrographs


__all__ = [
    "spectrograph_temperature_label",
    "spectrograph_temperatures",
    "spectrograph_temperatures_history",
    "spectrograph_pressures",
    "spectrograph_mechanics",
    "spectrograph_status",
    "read_thermistors",
    "read_thermistors_influxdb",
    "read_ion_pumps",
    "toggle_ion_pump",
    "exposure_etr",
    "retrieve_fill_measurements",
    "register_ln2_fill",
]


SpecToStatus = dict[Spectrographs, SpecStatus]


async def spectrograph_temperatures_history(
    start: str = "-30m",
    stop: str = "now()",
    camera: str | None = None,
    sensor: str | None = None,
):
    time_range = f"|> range(start: {start}, stop: {stop})"

    spec_filter = r'|> filter(fn: (r) => r["_measurement"] =~ /lvmscp\.sp[1-3]/)'
    if camera is not None:
        spec_filter = (
            f'|> filter(fn: (r) => r["_measurement"] == "lvmscp.sp{camera[-1]}")'
        )

    sensor_filter = r'|> filter(fn: (r) => r["_field"] =~ /mod(2|12)\/temp[abc]/)'
    if camera is not None and sensor is not None:
        field = spectrograph_temperature_label(camera[0], sensor)
        sensor_filter = f'|> filter(fn: (r) => r["_field"] == "status.{field}")'

    query = rf"""
    from(bucket: "actors")
        {time_range}
        {spec_filter}
        {sensor_filter}
    """

    results = await query_influxdb(query)

    if len(results) == 0:
        return polars.DataFrame(
            None,
            schema={
                "time": polars.String,
                "camera": polars.String,
                "sensor": polars.String,
                "temperature": polars.Float32,
            },
        )

    final_df = results.select(
        time=polars.col._time,
        camera=polars.lit(None, dtype=polars.String),
        sensor=polars.lit(None, dtype=polars.String),
        temperature=polars.col._value.cast(polars.Float32),
    )

    for spec in ["sp1", "sp2", "sp3"]:
        for cc in get_args(Cameras):
            for ss in get_args(Sensors):
                label = spectrograph_temperature_label(cc, ss)

                _measurement = f"lvmscp.{spec}"
                _field = f"status.{label}"

                final_df[
                    (
                        (results["_measurement"] == _measurement)
                        & (results["_field"] == _field)
                    ).arg_true(),
                    "camera",
                ] = f"{cc}{spec[-1]}"

                final_df[(results["_field"] == _field).arg_true(), "sensor"] = ss

    final_df = final_df.select(polars.col(["time", "camera", "sensor", "temperature"]))
    final_df = final_df.sort(["time", "camera", "sensor"])

    if camera:
        final_df = final_df.filter(polars.col.camera == camera)

    if sensor:
        final_df = final_df.filter(polars.col.sensor == sensor)

    return final_df


@overload
async def read_thermistors_influxdb(interval: float) -> polars.DataFrame: ...


@overload
async def read_thermistors_influxdb(interval: None) -> dict[str, bool]: ...


async def read_thermistors_influxdb(
    interval: float | None = None,
) -> polars.DataFrame | dict[str, bool]:
    """Returns thermistor states from InfluxDB.

    Parameters
    ----------
    interval
        How far to look back in seconds. If None, returns the latest value.

    Returns
    -------
    states
        If ``interval=None``, a dictionary of thermistor states. Otherwise a
        Polars dataframe with the thermistor states, one row per measurement
        within the interval.

    """

    if interval is None:
        start = "-1m"
        last = "|> last()"
    else:
        start = f"-{interval}s"
        last = ""

    query = f"""
from(bucket: "spec")
  |> range(start: {start}, stop: now())
  |> filter(fn: (r) => r["_measurement"] == "thermistors")
  |> filter(fn: (r) => r["channel_name"] != "")
  {last}
  |> group(columns: ["_field"])
  |> keep(columns: ["_time", "channel_name", "_value"])
"""

    data = await query_influxdb(query)

    if interval is None:
        result: dict[str, bool] = {}
        for row in data.iter_rows(named=True):
            result[row["channel_name"]] = bool(row["_value"])
        return result

    df = data.select(
        time=polars.col._time,
        channel=polars.col.channel_name,
        state=polars.col._value.cast(polars.Boolean),
    )
    df = df.sort(["channel", "time"])

    return df


async def retrieve_fill_measurements(
    start: float | datetime,
    end: float | datetime,
) -> polars.DataFrame:
    """Retrieves LN2 fill data from InfluxDB.

    This function retrieves the LN2 fill data from InfluxDB for a given interval.
    That includes LN2 and CCD temperatures, pressures, NPS outlet status, and
    thermistor status. This query is intended mostly for ``lvmcryo`` to collect
    metrology data after a fill.

    Parameters
    ----------
    start
        The start of the interval. Either a ``datetime`` object in UTC or a Unix
        timestamp.
    end
        The end of the interval.

    Returns
    -------
    fill_data
        A Polars DataFrame with the fill data.

    """

    query_start_time: int | str
    query_end_time: int | str

    if isinstance(start, datetime):
        query_start_time = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        query_start_time = int(start)

    if isinstance(end, datetime):
        query_end_time = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        query_end_time = int(end)

    # Get data from the "spec" bucket (pressure and thermistors).

    query_cryo = f"""
        from(bucket: "spec")
        |> range(start: {query_start_time}, stop: {query_end_time})
        |> filter(fn: (r) => r["_measurement"] == "pressure" or r["_measurement"] == "thermistors")
        |> filter(fn: (r) => (r["_measurement"] == "thermistors" and r["_field"] =~ /channel[0-9]+/) or
                             (r["_measurement"] == "pressure" and r["_field"] == "cmb"))
        |> aggregateWindow(every: 1s, fn: mean, createEmpty: false)
        |> yield(name: "mean")
    """  # noqa: E501

    data_cryo = await query_influxdb(query_cryo)

    pressure_data = data_cryo.filter(polars.col._measurement == "pressure")

    # Select pressures and pivot. Pressure is the data we poll the least so for
    # short intervals there may not be any data.
    if len(pressure_data) > 0:
        pressures = (
            pressure_data.select(
                time=polars.col._time.cast(polars.Datetime("ms", UTC)),
                ccd=polars.col.ccd,
                value=polars.col._value,
            )
            .with_columns(ccd="pressure_" + polars.col.ccd)
            .pivot("ccd", index="time", values="value")
            .sort("time")
        )
    else:
        pressures = polars.DataFrame(None, schema={"time": polars.Datetime("ms", UTC)})

    # Select thermistors and pivot.
    ch_to_valve = channel_to_valve()
    thermistors = (
        data_cryo.filter(polars.col._measurement == "thermistors")
        .select(
            time=polars.col._time.cast(polars.Datetime("ms", UTC)),
            field=polars.col._field,
            value=polars.col._value.cast(polars.Boolean),
        )
        .with_columns(
            channel="thermistor_"
            + polars.col.field.str.replace("channel", "")
            .cast(polars.Int32)
            .replace_strict(ch_to_valve, default=None)
        )
        .drop("field")
        .drop_nulls()
        .pivot("channel", index="time", values="value")
        .sort("time")
    )

    # Get temperatures and pivot
    data_temp = await spectrograph_temperatures_history(
        start=str(query_start_time),
        stop=str(query_end_time),
    )

    temp_df = (
        data_temp.select(
            time=polars.col.time.cast(polars.Datetime("ms", UTC)),
            sensor="temp_" + polars.col.camera + "_" + polars.col.sensor,
            value=polars.col.temperature,
        )
        .pivot(
            "sensor",
            index="time",
            values="value",
        )
        .sort("time")
    )

    # Create a uniform range of times.
    if not isinstance(start, datetime):
        start = datetime.fromtimestamp(start, UTC)
    if not isinstance(end, datetime):
        end = datetime.fromtimestamp(end, UTC)

    time_range = (
        polars.datetime_range(start, end, "1s", eager=True, time_unit="ms")
        .alias("time")
        .to_frame()
    )

    # Join with the data frames.
    data = (
        time_range.join_asof(pressures, on="time", strategy="nearest")
        .join_asof(thermistors, on="time", strategy="nearest")
        .join_asof(temp_df, on="time", strategy="nearest")
        .with_columns(polars.all().forward_fill().backward_fill())
    )

    return data


async def register_ln2_fill(
    *,
    action: str,
    start_time: str | None,
    end_time: str | None,
    purge_start: str | None,
    purge_complete: str | None,
    fill_start: str | None,
    fill_complete: str | None,
    fail_time: str | None,
    abort_time: str | None,
    failed: bool,
    aborted: bool,
    error: str | None,
    log_file: str | None,
    json_file: str | None,
    configuration: dict | None,
    log_data: list[dict] | None,
    plot_paths: dict[str, str] | None,
    valve_times: dict[str, dict[str, str]] | None,
) -> int:
    """Registers LN2 fill data in the database."""

    uri = config["database.uri"]
    table: list[str] = config["database.tables.ln2_fill"].split(".")

    async with await psycopg.AsyncConnection.connect(uri) as aconn:
        async with aconn.cursor() as acur:
            await acur.execute(
                psycopg.sql.SQL(
                    """
INSERT INTO {} (start_time, end_time, purge_start, purge_complete,
                fill_start, fill_complete, fail_time, abort_time,
                failed, aborted, error, action, log_file, json_file,
                configuration, log_data, plot_paths, valve_times)
VALUES (%(start_time)s, %(end_time)s, %(purge_start)s, %(purge_complete)s,
        %(fill_start)s, %(fill_complete)s, %(fail_time)s, %(abort_time)s,
        %(failed)s, %(aborted)s, %(error)s, %(action)s, %(log_file)s,
        %(json_file)s, %(configuration)s, %(log_data)s, %(plot_paths)s,
        %(valve_times)s)
RETURNING pk;
"""
                ).format(psycopg.sql.Identifier(*table)),
                {
                    "start_time": start_time,
                    "end_time": end_time,
                    "purge_start": purge_start,
                    "purge_complete": purge_complete,
                    "fill_start": fill_start,
                    "fill_complete": fill_complete,
                    "fail_time": fail_time,
                    "abort_time": abort_time,
                    "failed": failed,
                    "aborted": aborted,
                    "error": error,
                    "action": action,
                    "log_file": log_file,
                    "json_file": json_file,
                    "configuration": json.dumps(configuration)
                    if configuration
                    else None,
                    "log_data": json.dumps(log_data) if log_data else None,
                    "plot_paths": json.dumps(plot_paths) if plot_paths else None,
                    "valve_times": json.dumps(valve_times) if valve_times else None,
                },
            )

            await aconn.commit()
            returned = await acur.fetchone()

    if returned is None:
        raise ValueError("Could not retrieve primary key.")

    pk = returned[0]

    return pk
