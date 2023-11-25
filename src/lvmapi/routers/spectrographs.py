#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-11
# @Filename: cryostats.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import get_args

import pandas
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from lvmapi.tools import (
    get_spectrograph_mechanics,
    get_spectrograph_pressures,
    get_spectrograph_temperature_label,
    get_spectrograph_temperatures,
    query_influxdb,
)
from lvmapi.tools.spectrograph import read_thermistors
from lvmapi.types import Cameras, CamSpec, Sensors, Spectrographs


class SplitDataFrameToDict(BaseModel):
    columns: list[str]
    data: list[list]


router = APIRouter(prefix="/spectrographs", tags=["spectrographs"])


@router.get("/", summary="List of spectrographs")
async def get_cryostats() -> list[str]:
    """Returns the list of cryostats."""

    return list(get_args(Spectrographs))


@router.get(
    "/temperatures",
    summary="Cryostat temperatures",
    response_model=SplitDataFrameToDict,
)
async def get_temperatures(
    start: str = Query("-30m", description="Flux-compatible start time"),
    stop: str = Query("now()", description="Flux-compatible stop time"),
    camera: CamSpec | None = Query(None, description="Camera to return, or all"),
    sensor: Sensors | None = Query(None, description="Sensor to return, or all"),
):
    """Returns the temperatures of one or multiple cryostats."""

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

    try:
        results = await query_influxdb(query)
    except Exception:
        raise HTTPException(500, detail="Failed querying InfluxDB.")

    if len(results) == 0:
        return {"columns": ["time", "camera", "sensor", "temperature"], "data": []}

    results.loc[:, "time"] = results["_time"].map(lambda tt: tt.isoformat())
    results.loc[:, "camera"] = pandas.Series("", dtype="S3")
    results.loc[:, "sensor"] = pandas.Series("", dtype="S3")
    results.loc[:, "temperature"] = results._value

    for spec in ["sp1", "sp2", "sp3"]:
        for cc in get_args(Cameras):
            for ss in get_args(Sensors):
                label = get_spectrograph_temperature_label(cc, ss)

                results.loc[
                    (results._measurement == f"lvmscp.{spec}")
                    & (results._field == f"status.{label}"),
                    "camera",
                ] = f"{cc}{spec[-1]}"

                results.loc[results._field == f"status.{label}", "sensor"] = ss

    results = results.loc[:, ["time", "camera", "sensor", "temperature"]]

    if camera:
        results = results.loc[results.camera == camera, :]

    if sensor:
        results = results.loc[results.sensor == sensor, :]

    return results.to_dict(orient="split", index=False)


@router.get("/thermistors")
@router.get(
    "/thermistors/{thermistor}",
    summary="Reads the thermistors",
    response_model=SplitDataFrameToDict | dict[str, bool] | bool,
)
async def get_thermistors(
    thermistor: str | None = None,
    interval=Query(None, description="Interval in seconds"),
):
    """Reads the thermistors and returns their states."""

    data = await read_thermistors(interval=interval)

    if isinstance(data, pandas.DataFrame):
        if thermistor is not None:
            data = data.loc[data.channel == thermistor.lower(), :]
        return data.to_dict(orient="split", index=False)

    if thermistor:
        return data[thermistor]

    return data


@router.get("/{spectrograph}", summary="Cryostat basic information")
@router.get("/{spectrograph}/summary", summary="Cryostat basic information")
async def get_summary(
    spectrograph: Spectrographs,
    mechs: bool = Query(False, description="Return mechanics information?"),
) -> dict[str, float | str]:
    """Retrieves current spectrograph information (temperature, pressure, etc.)"""

    try:
        temps_response = await get_spectrograph_temperatures(spectrograph)
        pres_reponse = await get_spectrograph_pressures(spectrograph)

        if mechs:
            mechs_response = await get_spectrograph_mechanics(spectrograph)
        else:
            mechs_response = {}

    except Exception:
        raise HTTPException(500, detail="Error retrieving cryostat information.")

    return temps_response | pres_reponse | mechs_response
