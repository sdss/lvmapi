#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-06-14
# @Filename: macros.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from lvmapi.auth import AuthDependency
from lvmapi.tasks import cleanup_task, shutdown_task


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
