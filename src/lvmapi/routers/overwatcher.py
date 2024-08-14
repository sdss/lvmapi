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

from lvmapi.tasks import get_gort_log_task
from lvmapi.tools.rabbitmq import CluClient


class OverwatcherStatusModel(BaseModel):
    """Overwatcher status model."""

    enabled: Annotated[bool, Field(description="Is the overwatcher enabled?")]
    observing: Annotated[bool, Field(description="Is the overwatcher observing?")]
    calibrating: Annotated[bool, Field(description="Is the overwatcher taking cals?")]
    allow_dome_calibrations: Annotated[
        bool,
        Field(description="Is the overwatcher allowed to take dome cals?"),
    ]


router = APIRouter(prefix="/overwatcher", tags=["overwatcher"])


@router.get("/")
async def get_overwatcher():
    """Not implemented."""

    return {}


@router.get(
    "/status",
    description="Returns the status of the overwatcher",
    response_model=OverwatcherStatusModel,
)
async def get_overwatcher_status() -> OverwatcherStatusModel:
    """Returns the status of the overwatcher."""

    async with CluClient() as clu:
        status_cmd = await clu.send_command("lvm.overwatcher", "status")
        status = status_cmd.replies.get("status")

    return status


@router.get("/status/enabled", description="Is the overwatcher enabled?")
async def get_overwatcher_enabled() -> bool:
    """Returns whether the overwatcher is enabled."""

    async with CluClient() as clu:
        status_cmd = await clu.send_command("lvm.overwatcher", "status")
        status = status_cmd.replies.get("status")

    return status["enabled"]


@router.put(
    "/status/{enable_or_disable}",
    description="Enable or disable the overwatcher",
)
async def put_overwatcher_enabled(
    enable_or_disable: Annotated[
        Literal["enable", "disable"],
        Path(description="Whether to enable or disable the overwatcher"),
    ],
):
    """Enables or disables the overwatcher."""

    async with CluClient() as clu:
        await clu.send_command("lvm.overwatcher", enable_or_disable)


@router.get("/logs", description="Returns a list of log files")
async def get_logs_files_route():
    """Returns a list of log files."""

    files = pathlib.Path("/data/logs/lvmgort/").glob("[0-9]*.log")

    return sorted([file.name for file in files])


@router.get("/logs/{logfile}", description="Returns a logfile text")
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
