#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-03-25
# @Filename: overwatcher.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from fastapi import APIRouter

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
