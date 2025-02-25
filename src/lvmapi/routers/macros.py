#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-06-14
# @Filename: macros.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from lvmapi.auth import AuthDependency
from lvmapi.tasks import cleanup_task, power_cycle_ag_cameras, shutdown_task


router = APIRouter(prefix="/macros", tags=["macros"])


@router.get(
    "/shutdown",
    dependencies=[AuthDependency],
    summary="Runs the shutdown macro",
)
async def route_get_shutdown(
    disable_overwatcher: Annotated[
        bool,
        Query(description="Disables the Overwatcher after closing the dome."),
    ],
) -> str:
    """Schedules an emergency shutdown of the enclosure and telescopes."""

    task = await shutdown_task.kiq(disable_overwatcher=disable_overwatcher)
    return task.task_id


@router.get("/shutdownLCO", summary="Runs the shutdown macro (LCO internal version)")
async def route_get_shutdown_lco(
    override_code: Annotated[
        str,
        Query(description="An override code to allow shutting without authentication."),
    ],
    disable_overwatcher: Annotated[
        bool,
        Query(description="Disables the Overwatcher after closing the dome."),
    ],
) -> str:
    """Schedules an emergency shutdown of the enclosure and telescopes."""

    lco_override_code = os.getenv("LCO_OVERRIDE_CODE", None)
    if lco_override_code is None or override_code != lco_override_code:
        raise HTTPException(status_code=401, detail="Invalid override code.")

    task = await shutdown_task.kiq(disable_overwatcher=disable_overwatcher)
    return task.task_id


@router.get(
    "/cleanup",
    dependencies=[AuthDependency],
    summary="Runs the cleanup macro",
)
async def route_get_cleanup(
    readout: Annotated[
        bool,
        Query(
            description="If the spectrographs are idle and with a readout pending, "
            "reads the spectrographs."
        ),
    ] = True,
) -> str:
    """Runs the cleanup recipe as a task."""

    task = await cleanup_task.kiq(readout=readout)
    return task.task_id


@router.get("/shutdown_from_dupont", include_in_schema=False)
async def route_get_shutdown_from_dupont(request: Request) -> str:
    """Schedules an emergency shutdown of the enclosure and telescopes.

    This is a special version of the shutdown macro that does not require
    authentication but that will fail unless the request comes from the
    DuPont telescope.

    """

    host_valid = request.client and request.client.host == "10.8.38.21"
    dupont_valid = request.headers.get("x-real-ip", "") == "10.8.68.201"

    if not host_valid or not dupont_valid:
        raise HTTPException(status_code=401, detail="Invalid request. Not authorised.")

    task = await shutdown_task.kiq()
    return task.task_id


@router.get("/power_cycle_ag_cameras", summary="Power cycle the AG cameras")
async def route_get_power_cycle_ag_cameras(
    camera: Annotated[
        list[str] | None,
        Query(
            description="Cameras to power cycle (accepts a list). "
            "Otherwise power cycles all the cameras.",
        ),
    ] = None,
) -> str:
    """Power cycle the AG cameras."""

    task = await power_cycle_ag_cameras.kiq(cameras=camera)
    return task.task_id
