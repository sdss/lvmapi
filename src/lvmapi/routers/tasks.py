#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-25
# @Filename: tasks.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from taskiq_redis.exceptions import ResultIsMissingError

from lvmapi.broker import broker


class TaskResult(BaseModel):
    """A model to represent the result of a task."""

    is_err: bool
    is_ready: bool
    log: str | None = None
    return_value: Any | None = None
    execution_time: float | None = None
    labels: dict | None = None
    error: str | None = None


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}/ready")
async def task_ready(task_id: str) -> bool:
    """Returns whether a tasks has finished running."""

    return await broker.result_backend.is_result_ready(task_id)


@router.get("/{task_id}/result")
async def task_result(task_id: str):
    """Returns whether a tasks has finished running."""

    try:
        result = await broker.result_backend.get_result(task_id)
    except ResultIsMissingError:
        return TaskResult(
            is_ready=False,
            is_err=True,
            error="Task not found or result not ready.",
        )

    error = result.error if result.error is None else str(result.error)

    return TaskResult(is_ready=True, **result.dict(exclude={"error"}), error=error)
