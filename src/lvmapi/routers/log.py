#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-08-06
# @Filename: log.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Path, Query

from lvmapi.tasks import get_exposure_data_task
from lvmapi.tools.log import get_exposure_data, get_exposures, get_spectro_mjds


router = APIRouter(prefix="/log", tags=["log"])


@router.get("/")
async def get_log():
    """Not implemented."""

    return {}


@router.get("/mjds")
async def get_spectro_mjds_route():
    """Returns a list of MJDs with spectrograph data (or at least a folder)."""

    mjds = await asyncio.get_event_loop().run_in_executor(None, get_spectro_mjds)
    return mjds


@router.get(
    "/exposures/{mjd}",
    description="Returns a list of exposures for an MJD.",
)
async def get_exposures_route(
    mjd: int = Path(
        title="The SJD (Sloan-flavoured MJD) for which to list exposures.",
    ),
):
    """Returns a list of exposures for an MJD."""

    executor = asyncio.get_event_loop().run_in_executor
    exposures = await executor(None, get_exposures, mjd)

    return list(map(str, exposures))


@router.get(
    "/exposures/data/{mjd}",
    description="Returns data from exposures for an MJD.",
)
async def get_exposure_data_route(
    mjd: int = Path(
        title="The SJD (Sloan-flavoured MJD) for which to list exposures.",
    ),
    as_task: bool = Query(
        False,
        description="Whether to schedule this as a task.",
    ),
):
    """Returns a log of exposures for an MJD.."""

    if as_task is False:
        executor = asyncio.get_event_loop().run_in_executor
        exposure_data = await executor(None, get_exposure_data, mjd)
        return exposure_data

    task = await get_exposure_data_task.kiq(mjd)
    return task.task_id
