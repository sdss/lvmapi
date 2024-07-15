#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-11
# @Filename: cryostats.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import get_args

import polars
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from lvmapi.tools import (
    get_spectrograph_mechanics,
    get_spectrograph_pressures,
    get_spectrograph_temperatures,
)
from lvmapi.tools.spectrograph import (
    get_spectrogaph_status,
    get_spectrograph_temperatures_history,
    read_thermistors,
)
from lvmapi.types import CamSpec, Sensors, SpecStatus, Spectrographs


class SplitDataFrameToDict(BaseModel):
    columns: list[str]
    data: list[tuple]


router = APIRouter(prefix="/spectrographs", tags=["spectrographs"])


@router.get("/", summary="List of spectrographs")
async def get_cryostats() -> list[str]:
    """Returns the list of cryostats."""

    return list(get_args(Spectrographs))


@router.get("/status", summary="Returns the spectrograph status")
async def get_status(
    spec: Spectrographs | None = None,
) -> dict[Spectrographs, SpecStatus]:
    """Returns the spectrograph status."""

    status = await get_spectrogaph_status()
    if spec:
        return {spec: status[spec]}

    return status


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

    df = await get_spectrograph_temperatures_history(
        start,
        stop,
        camera=camera,
        sensor=sensor,
    )

    return {"columns": df.columns, "data": df.rows()}


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

    if isinstance(data, polars.DataFrame):
        if thermistor is not None:
            data = data.filter(polars.col.channel == thermistor)
        return {"columns": data.columns, "data": data.rows()}

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
