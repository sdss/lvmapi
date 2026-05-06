#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-25
# @Filename: broker.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os

from aio_pika import ExchangeType
from taskiq_aio_pika import AioPikaBroker, Exchange, Queue
from taskiq_redis import RedisAsyncResultBackend


__all__ = ["broker_startup", "broker_shutdown", "broker"]


async def broker_startup():
    """Start broker on startup."""

    if not broker.is_worker_process:
        await broker.startup()


async def broker_shutdown():
    """Shut down broker."""

    if not broker.is_worker_process:
        await broker.shutdown()


# The RabbitMQ queue name for the broker and workers to use.
# This allows to create different pools of workers for dev and production.
QUEUE_NAME: str = os.getenv("TASKIQ_QUEUE_NAME", "lvmapi-taskiq")
EXCHANGE_NAME = "taskiq-dev" if "dev" in QUEUE_NAME else "taskiq"

# TaskIQ broker.
backend = RedisAsyncResultBackend("redis://localhost")
broker = AioPikaBroker(
    exchange=Exchange(
        name=EXCHANGE_NAME,
        type=ExchangeType.TOPIC,
        declare=True,
        durable=False,
        auto_delete=True,
    ),
    task_queues=[
        Queue(
            name=QUEUE_NAME,
            routing_key=QUEUE_NAME,
        )
    ],
    dead_letter_queue=Queue(
        name=f"{QUEUE_NAME}.dead_letter",
        routing_key=f"{QUEUE_NAME}.dead_letter",
    ),
).with_result_backend(backend)
