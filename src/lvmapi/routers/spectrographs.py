#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-11
# @Filename: cryostats.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import re
import warnings

from typing import Annotated, get_args

import polars
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from lvmopstools.devices.ion import IonPumpDict
from lvmopstools.devices.nps import read_nps

from lvmapi.tools.spectrograph import (
    exposure_etr,
    read_ion_pumps,
    read_thermistors,
    read_thermistors_influxdb,
    spectrogaph_status,
    spectrograph_mechanics,
    spectrograph_pressures,
    spectrograph_temperatures,
    spectrograph_temperatures_history,
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

    pressure: float | None = Field(
        ...,
        description="The pressure reported by the ion pump in Torr",
    )
    on: bool | None = Field(
        ...,
        description="Whether the ion pump is on",
    )


class CryostatsResponse(BaseModel):
    """Reponse model for ``/cryostats``."""

    ln2_temperatures: Annotated[
        dict[str, float | None],
        Field(description="LN2 temperatures"),
    ]
    pressures: Annotated[
        dict[str, float | None],
        Field(
            description="Pressures in Torr as reported by the "
            "cryostat pressure transceivers"
        ),
    ]
    pressures_ion: Annotated[
        dict[str, IonPumpDict],
        Field(description="Pressures in Torr as reported by the ion pumps"),
    ]
    thermistors: Annotated[
        dict[str, bool | None],
        Field(description="Whether the thermistors are sensing LN2"),
    ]
    purging: Annotated[
        bool | None,
        Field(description="Is the purge valve open?"),
    ] = False
    filling: Annotated[
        dict[str, bool | None],
        Field(description="Whether the cryostat are filling"),
    ]


router = APIRouter(prefix="/spectrographs", tags=["spectrographs"])


@router.get("/", summary="List of spectrographs")
async def route_get_sectrographs() -> list[str]:
    """Returns the list of cryostats."""

    return list(get_args(Spectrographs))


@router.get(
    "/status",
    summary="Returns the spectrograph status",
    response_model=SpecStatusResponse,
)
async def route_get_status() -> SpecStatusResponse:
    """Returns the spectrograph status."""

    spec_status = await spectrogaph_status()

    return SpecStatusResponse(
        status=spec_status["status"],
        last_exposure_no=spec_status["last_exposure_no"],
        exposure_etr=spec_status["etr"][0],
        total_exposure_time=spec_status["etr"][1],
    )


@router.get("/etr", summary="Estimated time remaining")
async def route_get_etr():
    """The estimated time remaining for the current exposure, including readout."""

    return await exposure_etr()


@router.get("/temperatures", summary="Cryostat temperatures")
async def route_get_temperatures(
    start: str = Query("-30m", description="Flux-compatible start time"),
    stop: str = Query("now()", description="Flux-compatible stop time"),
    camera: CamSpec | None = Query(None, description="Camera to return, or all"),
    sensor: Sensors | None = Query(None, description="Sensor to return, or all"),
    last: bool = Query(False, description="Return only the last set of temperatures"),
) -> list[dict]:
    """Returns the temperatures of one or multiple cryostats."""

    df = await spectrograph_temperatures_history(
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
    interval: float | None = Query(None, description="Interval in seconds"),
):
    """Reads the thermistors and returns their states."""

    data = await read_thermistors_influxdb(interval)

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

    return {key: IonPumpResponse(**value) for key, value in ion_pump_data.items()}


@router.get("/cryostats", summary="Cryostat information")
async def route_get_cryostats():
    """Returns cryostat information regarding LN2 fills and pressures."""

    temperatures_response = await spectrograph_temperatures(ignore_errors=True)
    ln2_temperaures = {
        camera.split("_")[0]: temp
        for camera, temp in temperatures_response.items()
        if camera.endswith("ln2")
    }

    pressures = await spectrograph_pressures(ignore_errors=True)
    pressures_ion = await read_ion_pumps()
    thermistors = await read_thermistors()

    purging = False
    filling = {}

    try:
        nps = await read_nps()
        purging = nps["sp1.purge"]["state"]
        for key, value in nps.items():
            if match := re.match(r"sp[1-3]\.([rzb][1-3])", key):
                filling[match.group(1)] = value["state"]
    except Exception:
        warnings.warn("Error retrieving NPS information.")

    return CryostatsResponse(
        ln2_temperatures=ln2_temperaures,
        pressures=pressures,
        pressures_ion=pressures_ion,
        thermistors=thermistors,
        purging=purging,
        filling=filling,
    )


@router.get("/{spectrograph}", summary="Cryostat basic information")
@router.get("/{spectrograph}/summary", summary="Cryostat basic information")
async def route_get_summary(
    spectrograph: Spectrographs,
    mechs: bool = Query(False, description="Return mechanics information?"),
) -> dict[str, float | str | None]:
    """Retrieves current spectrograph information (temperature, pressure, etc.)"""

    try:
        temps_response = await spectrograph_temperatures(
            spectrograph,
            ignore_errors=True,
        )
        pres_reponse = await spectrograph_pressures(
            spectrograph,
            ignore_errors=True,
        )

        if mechs:
            mechs_response = await spectrograph_mechanics(
                spectrograph,
                ignore_errors=True,
            )
        else:
            mechs_response = {}

    except Exception:
        raise HTTPException(500, detail="Error retrieving cryostat information.")

    return temps_response | pres_reponse | mechs_response
