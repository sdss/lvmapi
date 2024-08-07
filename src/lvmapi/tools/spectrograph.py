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

from sdsstools import GatheringTaskGroup

from lvmapi.tools.influxdb import query_influxdb
from lvmapi.tools.rabbitmq import CluClient
from lvmapi.types import Cameras, Sensors, Spectrographs


if TYPE_CHECKING:
    from lvmapi.types import SpecStatus


__all__ = [
    "get_spectrograph_temperature_label",
    "get_spectrograph_temperatures",
    "get_spectrograph_pressures",
    "get_spectrograph_mechanics",
    "read_thermistors",
    "get_spectrogaph_status",
]


def get_spectrograph_temperature_label(camera: str, sensor: str = "ccd"):
    """Returns the archon label associated with a temperature sensor."""

    if sensor == "ccd":
        if camera == "r":
            return "mod2/tempa"
        elif camera == "b":
            return "mod12/tempc"
        elif camera == "z":
            return "mod12/tempa"

    else:
        if camera == "r":
            return "mod2/tempb"
        elif camera == "b":
            return "mod2/tempc"
        elif camera == "z":
            return "mod12/tempb"


async def get_spectrograph_temperatures(spec: Spectrographs):
    """Returns a dictionary of spectrograph temperatures."""

    async with CluClient() as client:
        scp_command = await client.send_command(
            f"lvmscp.{spec}",
            "status",
            internal=True,
        )

    if scp_command.status.did_fail:
        raise ValueError("Failed retrieving status from SCP.")

    status = scp_command.replies.get("status")

    response: dict[str, float] = {}

    cameras: list[Cameras] = ["r", "b", "z"]
    sensors: list[Sensors] = ["ccd", "ln2"]

    for camera in cameras:
        for sensor in sensors:
            label = get_spectrograph_temperature_label(camera, sensor)
            if label not in status:
                raise ValueError(f"Cannot find status label {label!r}.")
            response[f"{camera}{spec[-1]}_{sensor}"] = status[label]

    return response


async def get_spectrograph_temperatures_history(
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
        field = get_spectrograph_temperature_label(camera[0], sensor)
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
                label = get_spectrograph_temperature_label(cc, ss)

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


async def get_spectrograph_pressures(spec: Spectrographs):
    """Returns a dictionary of spectrograph pressures."""

    async with CluClient() as client:
        ieb_command = await client.send_command(
            f"lvmieb.{spec}",
            "transducer status",
            internal=True,
        )

    if ieb_command.status.did_fail:
        raise ValueError("Failed retrieving status from IEB.")

    pressures = ieb_command.replies.get("transducer")

    response: dict[str, float] = {}
    for key in pressures:
        if "pressure" in key:
            response[key] = pressures[key]

    return response


async def get_spectrograph_mechanics(spec: Spectrographs):
    """Returns a dictionary of spectrograph shutter and hartmann door status."""

    response: dict[str, str] = {}

    async with CluClient() as client:
        for device in ["shutter", "hartmann"]:
            ieb_cmd = await client.send_command(
                f"lvmieb.{spec}",
                f"{device} status",
                internal=True,
            )

            if ieb_cmd.status.did_fail:
                raise ValueError(f"Failed retrieving {device } status from IEB.")

            if device == "shutter":
                key = f"{spec}_shutter"
                response[key] = "open" if ieb_cmd.replies.get(key)["open"] else "closed"
            else:
                for door in ["left", "right"]:
                    key = f"{spec}_hartmann_{door}"
                    reply = ieb_cmd.replies.get(key)
                    response[key] = "open" if reply["open"] else "closed"

    return response


@overload
async def read_thermistors(interval: float) -> polars.DataFrame: ...


@overload
async def read_thermistors(interval: None) -> dict[str, bool]: ...


async def read_thermistors(
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


async def get_spectrogaph_status() -> tuple[dict[Spectrographs, SpecStatus], int]:
    """Returns the status of the spectrograph (integrating, reading, etc.)"""

    spec_names = get_args(Spectrographs)

    async with CluClient() as client:
        async with GatheringTaskGroup() as group:
            for spec in spec_names:
                group.create_task(
                    client.send_command(
                        f"lvmscp.{spec}",
                        "status -s",
                        internal=True,
                    )
                )

    result: dict[Spectrographs, SpecStatus] = {}
    last_exposure_no: int = -1

    for task in group.results():
        if task.status.did_fail:
            continue

        status = task.replies.get("status")
        controller: Spectrographs = status["controller"]
        status_names: str = status["status_names"]

        if "ERROR" in status_names:
            result[controller] = "error"
        elif "IDLE" in status_names:
            result[controller] = "idle"
        elif "EXPOSING" in status_names:
            result[controller] = "exposing"
        elif "READING" in status_names:
            result[controller] = "reading"
        else:
            result[controller] = "unknown"

        last_exposure_no_key = status.get("last_exposure_no", -1)
        if last_exposure_no_key > last_exposure_no:
            last_exposure_no = last_exposure_no_key

    for spec in spec_names:
        if spec not in result:
            result[spec] = "unknown"

    return result, last_exposure_no
