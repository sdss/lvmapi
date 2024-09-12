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
from pydantic import BaseModel, Field

from lvmapi.tools import (
    get_spectrograph_mechanics,
    get_spectrograph_pressures,
    get_spectrograph_temperatures,
)
from lvmapi.tools.spectrograph import (
    get_etr,
    get_spectrogaph_status,
    get_spectrograph_temperatures_history,
    read_ion_pumps,
    read_thermistors,
)
from lvmapi.types import CamSpec, Sensors, SpecStatus, Spectrographs


class SpecStatusResponse(BaseModel):
    status: dict[Spectrographs, SpecStatus] = Field(
        ...,
        description="The status of each spectrograph",
    )
    last_exposure_no: int = Field(
        ...,
        description="The last exposure number",
    )
    total_exposure_time: float | None = Field(
        default=None,
        description="The total exposure time, including readout",
    )
    exposure_etr: float | None = Field(
        default=None,
        description="The estimated time remaining for the current exposure, "
        "including readout",
    )


class IonPumpResponse(BaseModel):
    """The status of the ion pumps."""

    pressure: float = Field(
        ...,
        description="The pressure reported by the ion pump in Torr",
    )
    on: bool = Field(
        ...,
        description="Whether the ion pump is on",
    )


router = APIRouter(prefix="/spectrographs", tags=["spectrographs"])


@router.get("/", summary="List of spectrographs")
async def route_get_cryostats() -> list[str]:
    """Returns the list of cryostats."""

    return list(get_args(Spectrographs))


@router.get(
    "/status",
    summary="Returns the spectrograph status",
    response_model=SpecStatusResponse,
)
async def route_get_status(spec: Spectrographs | None = None) -> SpecStatusResponse:
    """Returns the spectrograph status."""

    spec_status = await get_spectrogaph_status()

    return SpecStatusResponse(
        status=spec_status["status"],
        last_exposure_no=spec_status["last_exposure_no"],
        exposure_etr=spec_status["etr"][0],
        total_exposure_time=spec_status["etr"][1],
    )


@router.get("/etr", summary="Estimated time remaining")
async def route_get_etr():
    """The estimated time remaining for the current exposure, including readout."""

    return await get_etr()


@router.get("/temperatures", summary="Cryostat temperatures")
async def route_get_temperatures(
    start: str = Query("-30m", description="Flux-compatible start time"),
    stop: str = Query("now()", description="Flux-compatible stop time"),
    camera: CamSpec | None = Query(None, description="Camera to return, or all"),
    sensor: Sensors | None = Query(None, description="Sensor to return, or all"),
    last: bool = Query(False, description="Return only the last set of temperatures"),
) -> list[dict]:
    """Returns the temperatures of one or multiple cryostats."""

    df = await get_spectrograph_temperatures_history(
        start,
        stop,
        camera=camera,
        sensor=sensor,
    )

    if last:
        df = df.group_by(["camera", "sensor"]).last()

    df = df.with_columns(time=polars.col.time.dt.to_string("%Y-%m-%dT%H:%M:%S.%3f"))
    df = df.select(polars.col(["time", "camera", "sensor", "temperature"]))
    df = df.sort(["camera", "sensor"])

    return df.to_dicts()


@router.get("/thermistors")
@router.get(
    "/thermistors/{thermistor}",
    summary="Reads the thermistors",
    response_model=list[dict] | dict[str, bool] | bool,
)
async def route_get_thermistors(
    thermistor: str | None = None,
    interval=Query(None, description="Interval in seconds"),
):
    """Reads the thermistors and returns their states."""

    data = await read_thermistors(interval=interval)

    if isinstance(data, polars.DataFrame):
        data = data.with_columns(
            time=polars.col.time.dt.to_string("%Y-%m-%dT%H:%M:%S.%3f")
        )

        if thermistor is not None:
            data = data.filter(polars.col.channel == thermistor)

        return data.to_dicts()

    if thermistor:
        return data[thermistor]

    return data


@router.get("/ion")
async def route_get_ion() -> dict[str, IonPumpResponse]:
    """Reads the current values of the ion pumps."""

    ion_pump_data = await read_ion_pumps()

    return ion_pump_data


@router.get("/{spectrograph}", summary="Cryostat basic information")
@router.get("/{spectrograph}/summary", summary="Cryostat basic information")
async def route_get_summary(
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
