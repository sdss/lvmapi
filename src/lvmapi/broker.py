#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-25
# @Filename: broker.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os

from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend


__all__ = ["broker"]


# The RabbitMQ queue name for the broker and workers to use.
# This allows to create different pools of workers for dev and production.
QUEUE_NAME: str = os.getenv("TASKIQ_QUEUE_NAME", "lvmapi")


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
broker = AioPikaBroker(queue_name=QUEUE_NAME).with_result_backend(backend)
