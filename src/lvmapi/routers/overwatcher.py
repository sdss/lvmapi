#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-03-25
# @Filename: overwatcher.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import pathlib

from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field

from lvmapi.auth import AuthDependency
from lvmapi.tasks import get_gort_log_task
from lvmapi.tools.rabbitmq import CluClient


class OverwatcherStatusModel(BaseModel):
    """Overwatcher status model."""

    running: Annotated[
        bool,
        Field(description="Is the overwatcher running?"),
    ] = False

    enabled: Annotated[
        bool,
        Field(description="Is the overwatcher enabled?"),
    ] = False

    observing: Annotated[
        bool,
        Field(description="Is the overwatcher observing?"),
    ] = False

    cancelling: Annotated[
        bool,
        Field(description="Are observations being cancelled?"),
    ] = False

    calibrating: Annotated[
        bool,
        Field(description="Is the overwatcher taking cals?"),
    ] = False

    night: Annotated[
        bool | None,
        Field(description="Is currently night (after twilight)?"),
    ] = None

    safe: Annotated[
        bool | None,
        Field(description="Is it safe to observe?"),
    ] = None

    allow_calibrations: Annotated[
        bool,
        Field(description="Is the overwatcher allowed to take cals?"),
    ] = False

    running_calibration: Annotated[
        str | None,
        Field(description="Name of the currently running calibration"),
    ] = None

    tile_id: Annotated[
        int | None,
        Field(description="Tile ID of the current observation"),
    ] = None

    dither_position: Annotated[
        int | None,
        Field(description="Dither position of the current observation"),
    ] = None

    stage: Annotated[
        str | None,
        Field(description="Stage of the current observation"),
    ] = None

    standard_no: Annotated[
        int | None,
        Field(description="Standard number of the current observation"),
    ] = None


class OverwatcherCalibrationModel(BaseModel):
    """Overwatcher calibration model."""

    name: Annotated[
        str,
        Field(description="The name of the calibration"),
    ]

    start_time: Annotated[
        str | None,
        Field(description="The start time of the calibration"),
    ]

    max_start_time: Annotated[
        str | None,
        Field(description="The maximum start time of the calibration"),
    ]

    after: Annotated[
        str | None,
        Field(description="Start the calibration only after this one is complete"),
    ]

    time_to_cal: Annotated[
        float | None,
        Field(description="Number of seconds to the calibration start"),
    ]

    status: Annotated[
        str,
        Field(description="The status of the calibration"),
    ]

    requires_dome: Annotated[
        Literal["open", "closed"] | None,
        Field(description="Required position of the dome"),
    ]

    close_dome_after: Annotated[
        bool,
        Field(description="Close the dome after the calibration"),
    ]


router = APIRouter(prefix="/overwatcher", tags=["overwatcher"])


@router.get("/", summary="Overwatcher route")
async def get_overwatcher():
    """Not implemented."""

    return {}


@router.get(
    "/status",
    summary="Returns the status of the overwatcher",
    response_model=OverwatcherStatusModel,
)
async def get_overwatcher_status() -> OverwatcherStatusModel:
    """Returns the status of the overwatcher."""

    status: dict[str, bool]
    async with CluClient() as clu:
        status_cmd = await clu.send_command("lvm.overwatcher", "status")

        try:
            status = status_cmd.replies.get("status")
        except KeyError:
            status = {"running": False}

        observer_command = await clu.send_command("lvm.overwatcher", "observer status")

        try:
            observer_status = observer_command.replies.get("observer_status")
            observer_status.pop("observing")  # Duplicated.
        except KeyError:
            observer_status = {}

    running_cal = await route_get_calibrations_current()

    return OverwatcherStatusModel(
        **status,
        **observer_status,
        running_calibration=running_cal,
    )


@router.get("/status/enabled", summary="Is the overwatcher enabled?")
async def get_overwatcher_enabled() -> bool:
    """Returns whether the overwatcher is enabled."""

    status = await get_overwatcher_status()

    return status.enabled


@router.put(
    "/status/{enable_or_disable}",
    summary="Enable or disable the overwatcher",
    dependencies=[AuthDependency],
)
async def put_overwatcher_enabled(
    enable_or_disable: Annotated[
        Literal["enable", "disable"],
        Path(description="Whether to enable or disable the overwatcher"),
    ],
    now: Annotated[
        bool,
        Query(description="Whether to stop observing immediately"),
    ] = False,
):
    """Enables or disables the overwatcher."""

    async with CluClient() as clu:
        await clu.send_command(
            "lvm.overwatcher",
            enable_or_disable,
            "--now" if enable_or_disable == "disable" and now else "",
        )


@router.get("/status/allow_calibrations", summary="Allow calibrations?")
async def get_allow_calibrations() -> bool:
    """Returns whether the overwatcher can take calibrations."""

    status = await get_overwatcher_status()

    return status.allow_calibrations


@router.put(
    "/status/allow_calibrations/{enable_or_disable}",
    summary="Enable or disable calibrations",
    dependencies=[AuthDependency],
)
async def put_allow_calibrations_enabled(
    enable_or_disable: Annotated[
        Literal["enable", "disable"],
        Path(description="Whether to enable or disable calibrations"),
    ],
):
    """Enables or disables calibrations."""

    command: str = "calibrations "
    if enable_or_disable == "enable":
        command += "enable-calibrations"
    else:
        command += "disable-calibrations"

    async with CluClient() as clu:
        await clu.send_command("lvm.overwatcher", command)


@router.get("/logs", summary="Returns a list of log files")
async def get_logs_files_route():
    """Returns a list of log files."""

    files = pathlib.Path("/data/logs/lvmgort/").glob("[0-9]*.log")

    return sorted([file.name for file in files])


@router.get("/logs/{logfile}", summary="Returns a logfile text")
async def get_logs_data_route(
    logfile: str,
    n_lines: int | None = Query(None, description="Returns only the last N lines"),
    as_task: bool = Query(
        False,
        description="Whether to schedule this as a task.",
    ),
):
    """Returns a logfile text."""

    task = await get_gort_log_task.kiq(logfile, n_lines=n_lines)
    if as_task:
        return task.task_id

    result = await task.wait_result()
    return result.return_value


@router.get("/calibrations/list", summary="Returns the list of calibrations")
async def route_get_calibrations_list() -> list[OverwatcherCalibrationModel]:
    """Returns the list of calibrations."""

    async with CluClient() as clu:
        calibrations_cmd = await clu.send_command(
            "lvm.overwatcher",
            "calibrations list",
        )

    if calibrations_cmd.status.did_fail:
        return []

    calibrations = calibrations_cmd.replies.get("calibrations")

    return [OverwatcherCalibrationModel(**calibration) for calibration in calibrations]


@router.get("/calibrations/running", summary="Currently running calibration")
async def route_get_calibrations_current() -> str | None:
    """Returns the name of the currently running calibration, if any."""

    cals = await route_get_calibrations_list()
    for cal in cals:
        if cal.status in ["running", "retrying"]:
            return cal.name
