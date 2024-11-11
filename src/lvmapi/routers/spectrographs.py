#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-11
# @Filename: cryostats.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import datetime
import pathlib
import re
import warnings

from typing import Annotated, get_args

import polars
from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from lvmopstools.devices.ion import IonPumpDict
from lvmopstools.devices.nps import read_nps

from lvmapi.tools.spectrograph import (
    FillMetadataReturn,
    exposure_etr,
    get_fill_list,
    read_ion_pumps,
    read_thermistors,
    read_thermistors_influxdb,
    register_ln2_fill,
    retrieve_fill_measurements,
    retrieve_fill_metadata,
    spectrograph_mechanics,
    spectrograph_pressures,
    spectrograph_status,
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


class FillDataModel(BaseModel):
    """Response for the ``/fills/data`` endpoint."""

    time: Annotated[datetime.datetime, Field(description="Time of the measurement")]

    # There are many more fields so we just allow them all.
    model_config = {"extra": "allow"}


class RegisterFillPostModel(BaseModel):
    """Request model for the ``/fills/register`` endpoint."""

    action: Annotated[
        str,
        Field(description="LN2 action performed"),
    ]
    complete: Annotated[
        bool,
        Field(description="Is the action complete?"),
    ]
    start_time: Annotated[
        str | None,
        Field(description="Start time of the action"),
    ]
    end_time: Annotated[
        str | None,
        Field(description="End time of the action"),
    ]
    purge_start: Annotated[
        str | None,
        Field(description="Purge start time"),
    ]
    purge_complete: Annotated[
        str | None,
        Field(description="Purge finish time"),
    ]
    fill_start: Annotated[
        str | None,
        Field(description="Fill start time"),
    ]
    fill_complete: Annotated[
        str | None,
        Field(description="Fill finish time"),
    ]
    fail_time: Annotated[
        str | None,
        Field(description="Time of failure"),
    ]
    abort_time: Annotated[
        str | None,
        Field(description="Time of abort"),
    ]
    failed: Annotated[
        bool,
        Field(description="Did the action fail?"),
    ]
    aborted: Annotated[
        bool,
        Field(description="Was the action aborted?"),
    ]
    error: Annotated[
        str | None,
        Field(description="Error message"),
    ]
    log_file: Annotated[
        str | None,
        Field(description="Path to the log file"),
    ]
    json_file: Annotated[
        str | None,
        Field(description="Path to the JSON file"),
    ]
    configuration: Annotated[
        dict | None,
        Field(description="Configuration data"),
    ]
    log_data: Annotated[
        list[dict] | None,
        Field(description="Log data in JSON format"),
    ]
    plot_paths: Annotated[
        dict[str, str] | None,
        Field(description="Paths to plots"),
    ]
    valve_times: Annotated[
        dict[str, dict[str, str | bool | None]] | None,
        Field(description="Valve open/close times"),
    ]
    pk: Annotated[
        int | None,
        Field(description="Primary key of the record to update."),
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

    spec_status = await spectrograph_status()

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


@router.get("/fills/running", summary="Is a fill currently running?")
async def route_get_fills_running() -> bool:
    """Returns whether an LN2 fill is currently running."""

    return pathlib.Path("/data/lvmcryo.lock").exists()


@router.get("/fills/measurements", summary="Cryostat fill measurements")
async def route_get_fills_measurements(
    start_time: int,
    end_time: int,
) -> list[FillDataModel]:
    """Returns cryostat fill measurements."""

    if start_time < 0 or end_time < 0 or start_time > end_time:
        raise HTTPException(400, detail="Invalid start or end times.")

    data = await retrieve_fill_measurements(start_time, end_time)
    data_dict = data.to_dicts()

    return [FillDataModel(**row) for row in data_dict]


@router.post("/fills/register", summary="Register an LN2 fill")
async def route_post_fills_register(data: RegisterFillPostModel) -> int:
    """Registers or updates an LN2 fill in the database."""

    try:
        pk = await register_ln2_fill(**data.model_dump())
    except Exception as ee:
        raise HTTPException(500, detail=str(ee))

    return pk


@router.get("/fills/list", summary="List LN2 fills and record PKs")
async def route_get_fills_list() -> dict[int, str]:
    """Returns a mapping of LN2 fill PK to start time."""

    return await get_fill_list()


@router.get("/fills/{pk}/metadata", summary="Get LN2 fill metadata")
async def route_get_fills_metadata(
    pk: Annotated[int, Path(description="Primary key of the LN2 fill record")],
    transparent_plots: Annotated[
        bool,
        Query(description="Return transparent metadata?"),
    ] = False,
    as_base64: Annotated[
        bool,
        Query(description="Return plots as base64-encoded strings?"),
    ] = False,
) -> FillMetadataReturn:
    """Returns the metadata for an LN2 fill."""

    try:
        return await retrieve_fill_metadata(
            pk,
            transparent_plots=transparent_plots,
            as_base64=as_base64,
        )
    except ValueError as err:
        if "Cannnot find LN2 fill with pk" in str(err):
            raise HTTPException(400, detail="Invalid primary key.")
        raise


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
