#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-07-24
# @Filename: tools.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os


__all__ = ["Gort"]


class Gort:
    """Yields an initialised GORT client."""

    def __init__(self):
        from gort import Gort

        gort_host: str = os.environ.get("RABBITMQ_HOST", "localhost")
        gort_port: int = int(os.environ.get("RABBITMQ_port", "5672"))

        self.g = Gort(host=gort_host, port=gort_port)
        self.initialised: bool = False

    async def __aenter__(self):
        if not self.initialised:
            await self.g.init()
            self.initialised = True

        return self.g

    async def __aexit__(self, exc_type, exc, tb):
        await self.g.stop()
