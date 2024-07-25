#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-25
# @Filename: broker.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend


__all__ = ["broker"]


async def broker_startup():
    """Start broker on startup."""

    if not broker.is_worker_process:
        await broker.startup()


async def broker_shutdown():
    """Shut down broker."""

    if not broker.is_worker_process:
        await broker.shutdown()


# TaskIQ broker.
backend = RedisAsyncResultBackend("redis://localhost")
broker = AioPikaBroker().with_result_backend(backend)
