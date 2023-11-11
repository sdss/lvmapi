#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-07-24
# @Filename: tools.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os

from clu import AMQPClient

from . import config


__all__ = ["CluClient"]


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

    """

    __initialised: bool = False
    __instance: CluClient | None = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super(CluClient, cls).__new__(cls)
            cls.__instance.__initialised = False

        return cls.__instance

    def __init__(self):
        if self.__initialised is True:
            return

        host: str = os.environ.get("RABBITMQ_HOST", config["rabbitmq.host"])
        port: int = int(os.environ.get("RABBITMQ_port", config["rabbitmq.port"]))

        self.client = AMQPClient(host=host, port=port)
        self.__initialised = True

    async def __aenter__(self):
        if not self.client.is_connected():
            await self.client.start()

        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def __anext__(self):
        if not self.client.is_connected():
            await self.client.start()

        return self.client

    @classmethod
    def clear(cls):
        """Clears the current instance."""

        cls.__instance = None
        cls.__initialised = False
