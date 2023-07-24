#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-07-24
# @Filename: tools.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations


__all__ = ["Gort"]


class Gort:
    """Yields an initialised GORT client."""

    def __init__(self):
        from gort import Gort

        self.g = Gort(host="localhost", port=25672)

    async def __aenter__(self):
        await self.g.init()
        return self.g

    async def __aexit__(self, exc_type, exc, tb):
        await self.g.stop()
