#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-24
# @Filename: tasks.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio

from typing import Literal

from lvmapi.app import broker
from lvmapi.tools.gort import get_gort_client


@broker.task()
async def move_dome_task(direction: Literal["open", "close"], force: bool = False):
    """Opens/closes the dome.

    Uses GORT to ensure that the telescopes are parked before moving the dome.

    """

    from lvmapi.app import app

    async with get_gort_client(app) as gort:
        if direction == "open":
            await gort.enclosure.open()
        else:
            await gort.enclosure.close(force=force)

    return True


@broker.task()
async def shutdown_task():
    """Shuts down the system."""

    from lvmapi.app import app

    async with get_gort_client(app) as gort:
        await gort.shutdown(park_telescopes=True)

    return True


@broker.task()
async def restart_kubernetes_deployment_task(deployment: str, confirm: bool = True):
    """Restarts a Kubernetes deployment."""

    from lvmapi.app import app

    app.state.kubernetes.restart_deployment(deployment)

    if confirm:
        for _ in range(15):
            if deployment in app.state.kubernetes.list_deployments():
                return True
            await asyncio.sleep(1)

    else:
        return True

    raise TimeoutError(f"Timed out waiting for {deployment} to start.")
