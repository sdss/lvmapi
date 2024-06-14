#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-06-14
# @Filename: gort.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from contextlib import asynccontextmanager

from typing import TYPE_CHECKING, AsyncGenerator

from gort import Gort


if TYPE_CHECKING:
    from fastapi import FastAPI


__all__ = ["get_gort_client"]


@asynccontextmanager
async def get_gort_client(
    app: FastAPI | None = None,
    verbosity: str = "warning",
) -> AsyncGenerator[Gort]:
    """Returns an initialised GORT client.

    Parameters
    ----------
    app
        The FastAPI app. If provided, the GORT client is added to the app state.
        If the state already has a GORT client, checks that it is connected and if
        so returns it.

    Returns
    -------
    gort
        The GORT client.

    """

    gort: Gort

    if app and hasattr(app.state, "gort"):
        gort = app.state.gort
        if not gort.connected:
            await gort.init()
    else:
        gort = await Gort(verbosity=verbosity).init()
        if app:
            app.state.gort = gort

    yield gort
