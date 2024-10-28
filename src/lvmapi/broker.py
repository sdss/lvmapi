#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-25
# @Filename: broker.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os

import aio_pika
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend


__all__ = ["broker"]


# The RabbitMQ queue name for the broker and workers to use.
# This allows to create different pools of workers for dev and production.
QUEUE_NAME: str = os.getenv("TASKIQ_QUEUE_NAME", "lvmapi")

EXCHANE_NAME = "taskiq-dev" if "dev" in QUEUE_NAME else "taskiq"


async def broker_startup():
    """Start broker on startup."""

    # Purge all messages from the queue before starting.
    connection = await aio_pika.connect_robust("amqp://guest:guest@127.0.0.1/")

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        try:
            queue = await channel.declare_queue(
                QUEUE_NAME,
                arguments={
                    "x-dead-letter-exchange": "",
                    "x-dead-letter-routing-key": "lvmapi-dev.dead_letter",
                },
            )
            await queue.purge()
        except Exception:
            pass

    if not broker.is_worker_process:
        await broker.startup()


async def broker_shutdown():
    """Shut down broker."""

    if not broker.is_worker_process:
        await broker.shutdown()


# TaskIQ broker.
backend = RedisAsyncResultBackend("redis://localhost")
broker = AioPikaBroker(
    queue_name=QUEUE_NAME,
    exchange_name=EXCHANE_NAME,
).with_result_backend(backend)
