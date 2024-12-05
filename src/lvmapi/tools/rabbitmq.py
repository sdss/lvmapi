#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-12
# @Filename: rabbitmq.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import os
import uuid

from typing import TYPE_CHECKING

from clu import AMQPClient
from lvmopstools.clu import send_clu_command
from sdsstools.utils import GatheringTaskGroup

from lvmapi import config


if TYPE_CHECKING:
    pass


__all__ = ["CluClient", "send_clu_command", "ping_actors"]


class CluClient:
    """AMQP client asynchronous generator.

    Returns an object with an ``AMQPClient`` instance. The normal way to
    use it is to do ::

        async with CluClient() as client:
            await client.send_command(...)

    Alternatively one can do ::

        client = await anext(CluClient())
        await client.send_command(...)

    The asynchronous generator differs from the one in ``AMQPClient`` in that
    it does not close the connection on exit.

    This class is a singleton, which effectively means the AMQP client is reused
    during the life of the worker. The singleton can be cleared by calling
    `.clear`.

    The host and port for the connection can be passed on initialisation. Otherwise
    it will use the values in the environment variables ``RABBITMQ_HOST`` and
    ``RABBITMQ_PORT`` or the default values in the configuration file.

    """

    __initialised: bool = False
    __instance: CluClient | None = None

    def __new__(cls, host: str | None = None, port: int | None = None):
        if (
            cls.__instance is None
            or (host is not None and cls.__instance.host != host)
            or (port is not None and cls.__instance.port != port)
        ):
            cls.clear()

            cls.__instance = super(CluClient, cls).__new__(cls)
            cls.__instance.__initialised = False

        return cls.__instance

    def __init__(self, host: str | None = None, port: int | None = None):
        if self.__initialised is True:
            # Bail out if we are returning a singleton instance
            # which is already initialised.
            return

        host_default = os.environ.get("RABBITMQ_HOST", "10.8.38.21")
        port_default = int(os.environ.get("RABBITMQ_PORT", 5672))

        self.host: str = host or host_default
        self.port: int = port or port_default

        self.client = AMQPClient(
            host=self.host,
            port=self.port,
            name=f"lvmapi-{uuid.uuid4()}",
        )
        self.__initialised = True

        self._lock = asyncio.Lock()

    def is_connected(self):
        """Is the client connected?"""

        connection = self.client.connection
        connected = connection.connection and not connection.connection.is_closed
        channel_closed = hasattr(connection, "channel") and connection.channel.is_closed

        if not connected or channel_closed:
            return False

        return True

    async def __aenter__(self):
        # Small delay to allow the event loop to update the
        # connection status if needed.
        await asyncio.sleep(0.05)

        async with self._lock:
            if not self.is_connected():
                await self.client.start()

        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def __anext__(self):
        if not self.is_connected():
            await self.client.start()

        return self.client

    @classmethod
    def clear(cls):
        """Clears the current instance."""

        if cls.__instance and cls.__instance.is_connected():
            asyncio.create_task(cls.__instance.client.stop())

        cls.__instance = None
        cls.__initialised = False


async def ping_actors(actors: list[str] | None = None):
    """Pings all actors and returns a list of replies."""

    actors = actors or config["actors"]["list"]
    assert actors is not None

    async with CluClient() as client:
        async with GatheringTaskGroup() as group:
            for actor in actors:
                group.create_task(client.send_command(actor, "ping"))

    results = group.results()

    actor_to_pong: dict[str, bool] = {}
    for idx, result in enumerate(results):
        replies = result.replies

        if "text" in replies[-1].message and replies[-1].message["text"] == "Pong.":
            actor_to_pong[actors[idx]] = True
        else:
            actor_to_pong[actors[idx]] = False

    return actor_to_pong
