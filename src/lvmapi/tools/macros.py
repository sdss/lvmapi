#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-06-14
# @Filename: macros.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from gort import Gort


__all__ = ["shutdown"]


async def shutdown():
    """Performs an emergency shutdown of the enclosure and telescopes."""

    gort = await Gort(verbosity="warning").init()
    await gort.shutdown(park_telescopes=True)

    return
