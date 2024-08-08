#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-03-25
# @Filename: overwatcher.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import pathlib

from fastapi import APIRouter, Query

from lvmapi.tasks import get_gort_log_task
from lvmapi.tools import get_redis_connection


router = APIRouter(prefix="/overwatcher", tags=["overwatcher"])


@router.get("/")
async def get_overwatcher():
    """Not implemented."""

    return {}


@router.get("/enabled", description="Is the overwatcher enabled?")
def get_overwatcher_enabled() -> bool:
    """Returns whether the overwatcher is enabled."""

    redis = get_redis_connection()

    enabled = redis.get("gort:overwatcher:enabled")
    assert enabled is None or isinstance(enabled, str)

    if enabled is None:
        return False

    return bool(int(enabled))


@router.put("/enabled/{enabled}", description="Enable or disable the overwatcher")
def put_overwatcher_enabled(enabled: bool) -> bool:
    """Enables or disables the overwatcher."""

    redis = get_redis_connection()
    redis.set("gort:overwatcher:enabled", int(enabled))

    return enabled


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
