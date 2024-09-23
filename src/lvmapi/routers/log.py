#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-08-06
# @Filename: log.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
from datetime import datetime

from typing import Annotated

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field

from lvmapi.tasks import get_exposure_data_task
from lvmapi.tools.log import (
    get_exposure_data,
    get_exposures,
    get_night_log_data,
    get_night_log_mjds,
    get_spectro_mjds,
)


class NightLogComment(BaseModel):
    """A comment in the night log."""

    time: Annotated[datetime, Field(description="The time the comment was loaded")]
    comment: Annotated[str, Field(description="The comment text")]


class NightLogData(BaseModel):
    """The night log data for an MJD."""

    mjd: Annotated[
        int,
        Field(description="The MJD associated with the comments"),
    ]
    exists: Annotated[
        bool,
        Field(description="Whether the night log exists in the DB"),
    ]
    sent: Annotated[
        bool,
        Field(description="Whether the night log has been sent"),
    ] = False
    comments: Annotated[
        dict[str, list[NightLogComment]],
        Field(description="The list of comments, organised by category"),
    ] = {}


router = APIRouter(prefix="/log", tags=["log"])


@router.get("/")
async def route_get_log():
    """Not implemented."""

    return {}


@router.get("/exposures/mjds", summary="List of MJDs with spectrograph data")
async def route_get_spectro_mjds():
    """Returns a list of MJDs with spectrograph data (or at least a folder)."""

    mjds = await asyncio.get_event_loop().run_in_executor(None, get_spectro_mjds)
    return mjds


@router.get(
    "/exposures/data/{mjd}",
    summary="Returns data from exposures for an MJD.",
)
async def route_get_exposures_data(
    mjd: Annotated[
        int,
        Path(description="The SJD (Sloan-flavoured MJD) for which to list exposures."),
    ],
    as_task: Annotated[
        bool,
        Query(description="Whether to schedule this as a task."),
    ] = False,
):
    """Returns a log of exposures for an MJD.."""

    if as_task is False:
        executor = asyncio.get_event_loop().run_in_executor
        exposure_data = await executor(None, get_exposure_data, mjd)
        return exposure_data

    task = await get_exposure_data_task.kiq(mjd)
    return task.task_id


@router.get("/exposures/{mjd}", summary="Returns a list of exposures for an MJD.")
async def route_get_exposures(
    mjd: Annotated[
        int,
        Path(description="The SJD (Sloan-flavoured MJD) for which to list exposures."),
    ],
):
    """Returns a list of exposures for an MJD."""

    executor = asyncio.get_event_loop().run_in_executor
    exposures = await executor(None, get_exposures, mjd)

    return list(map(str, exposures))


@router.get("/night_logs", summary="List of night log MJDs.")
async def route_get_night_logs():
    """Returns a list of MJDs with night log data."""

    mjds = await get_night_log_mjds()
    return mjds


@router.get("/night_logs/{mjd}", summary="Night log data for an MJD")
async def route_get_night_logs_mjd(
    mjd: Annotated[
        int | None,
        Path(
            description="The MJD for which to retrieve night log data. "
            "Use 0 for tonight's log."
        ),
    ],
):
    """Returns the night log data for an MJD."""

    print("mjd", mjd)
    data = await get_night_log_data(mjd if mjd != 0 else None)

    comments = {
        category: [NightLogComment(**comment) for comment in comments]
        for category, comments in data.pop("comments", {}).items()
    }
    return NightLogData(**data, comments=comments)
