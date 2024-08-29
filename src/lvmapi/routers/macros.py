#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-06-14
# @Filename: macros.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from fastapi import APIRouter

from lvmapi.auth import AuthDependency
from lvmapi.tasks import shutdown_task


router = APIRouter(prefix="/macros", tags=["macros"])


@router.get("/shutdown", dependencies=[AuthDependency])
async def shutdown_route() -> str:
    """Schedules an emergency shutdown of the enclosure and telescopes."""

    task = await shutdown_task.kiq()
    return task.task_id
