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


__all__ = ["CluClient"]


class CluClient:
    """Yields an initialised AMQP client."""

    def __init__(self):
        host: str = os.environ.get("RABBITMQ_HOST", "localhost")
        port: int = int(os.environ.get("RABBITMQ_port", "5672"))

        self.client = AMQPClient(host=host, port=port)
        self.initialised: bool = False

    async def __aenter__(self):
        if not self.initialised:
            await self.client.start()
            self.initialised = True

        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        await self.client.stop()
