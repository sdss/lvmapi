#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-07-24
# @Filename: tools.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING, get_args, overload

import polars

from lvmopstools.devices.ion import read_ion_pumps, toggle_ion_pump
from lvmopstools.devices.specs import (
    exposure_etr,
    spectrograph_mechanics,
    spectrograph_pressures,
    spectrograph_status,
    spectrograph_temperature_label,
    spectrograph_temperatures,
)
from lvmopstools.devices.thermistors import read_thermistors

from lvmapi.tools.influxdb import query_influxdb
from lvmapi.types import Cameras, Sensors, SpecStatus, Spectrographs


if TYPE_CHECKING:
    pass


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
