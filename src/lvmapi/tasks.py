#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-24
# @Filename: tasks.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import pathlib

from typing import Literal, Sequence

import httpx

from lvmapi import config
from lvmapi.app import broker
from lvmapi.tools import get_fill_list
from lvmapi.tools.gort import get_gort_client
from lvmapi.tools.rabbitmq import CluClient


@broker.task()
async def move_dome_task(direction: Literal["open", "close"], force: bool = False):
    """Opens/closes the dome.

    Uses GORT to ensure that the telescopes are parked before moving the dome.

    """

    async with get_gort_client() as gort:
        if direction == "open":
            await gort.enclosure.open()
        else:
            await gort.enclosure.close(force=force)

    return True


@broker.task()
async def shutdown_task(disable_overwatcher: bool = False):
    """Shuts down the system."""

    async with get_gort_client() as gort:
        await gort.emergency_shutdown()

    return True


@broker.task()
async def cleanup_task(readout: bool = True):
    """Shuts down the system."""

    async with get_gort_client() as gort:
        await gort.cleanup(readout=readout)

    return True


@broker.task()
async def restart_kubernetes_deployment_task(deployment: str, confirm: bool = True):
    """Restarts a Kubernetes deployment."""

    from lvmapi.app import app

    await app.state.kubernetes.restart_deployment(deployment)

    if confirm:
        for _ in range(15):
            if deployment in app.state.kubernetes.list_deployments():
                return True
            await asyncio.sleep(1)

    else:
        return True

    raise TimeoutError(f"Timed out waiting for {deployment} to start.")


@broker.task()
async def get_exposure_data_task(mjd: int):
    """Returns the list of exposures for a given MJD."""

    from lvmapi.tools.logs import get_exposure_data

    exposure_data = get_exposure_data(mjd)

    return exposure_data


@broker.task()
async def get_gort_log_task(logfile: str, n_lines: int | None = None):
    """Returns the log for a given MJD."""

    if not logfile.endswith(".log"):
        logfile += ".log"

    PATH = pathlib.Path("/data/logs/lvmgort/")

    if not (PATH / logfile).exists():
        return ""

    with open(PATH / logfile, "r") as file:
        if n_lines is None:
            return file.read()

        data = file.read().splitlines()[-n_lines:]
        return "\n".join(data)


@broker.task()
async def park_telescopes_task():
    """Parks all telescopes."""

    async with get_gort_client() as gort:
        await gort.telescopes.home()
        await gort.telescopes.park(disable=True)

    return True


@broker.task()
async def power_cycle_ag_cameras(
    cameras: Sequence[str] | None = None,
    reconnect: bool = True,
):
    """Power cycles the AG cameras."""

    from lvmopstools.devices.ags import power_cycle_ag_camera

    VALID_CAMERAS = [
        "sci-east",
        "sci-west",
        "skye-east",
        "skye-west",
        "skyw-east",
        "skyw-west",
        "spec-east",
    ]

    if cameras is None:
        cameras = VALID_CAMERAS

    errors: list[str] = []
    telescopes: set[str] = set()

    # The cameras for each telescope are connected to the same PDU port.
    # We only need to power cycle one camera per telescope.
    # WARNING: if we ever go back to having one or more cameras powered over PoE
    # we will need to change this logic and go back to power cycling each camera
    # individually.
    for camera in cameras:
        if camera == "":
            continue

        if camera not in VALID_CAMERAS:
            raise ValueError("invalid camera")

        telescope = camera.split("-")[0]
        telescopes.add(telescope)

    tasks = []
    for telescope in telescopes:
        camera = f"{telescope}-east"  # There is an east camera for each telescope.
        tasks.append(asyncio.create_task(power_cycle_ag_camera(camera, verbose=False)))

    await asyncio.gather(*tasks, return_exceptions=True)

    for task in tasks:
        if isinstance(task.result(), Exception):
            errors.append(f"{camera}: {task.result()}")

    # It takes a while for the cameras to come back online.
    await asyncio.sleep(30)

    if reconnect:
        # Force the instance of the overwatcher to reload all its actors.
        async with CluClient() as clu:
            await clu.send_command("lvm.overwatcher", "reset", time_limit=60)

        # Force the camera to reconnect.
        async with get_gort_client() as gort:
            await gort.ags.reconnect()

    return {"result": len(errors) == 0, "errors": errors}


@broker.task()
async def ln2_manual_fill(password: str | None, clear_lock: bool = True):
    """Starts a manual LN2 fill.

    Returns after the fill has started, which is defined as the moment when the
    new DB entry is created.

    Parameters
    ----------
    password
        The password to authorize the manual fill.
    clear_lock
        Whether to clear any existing fill lock before starting the fill.

    """

    # Get initial number of DB entries
    fills_db_before = await get_fill_list()

    lvmcryo_server_config = config["lvmcryo_server"]
    host = lvmcryo_server_config["host"]
    port = lvmcryo_server_config["port"]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://{host}:{port}/manual-fill?clear_lock={int(clear_lock)}",
                json={"password": password},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as err:
        return {"result": False, "pk": None, "error": str(err)}

    if not data.get("result", False):
        return {
            "result": False,
            "pk": None,
            "error": data.get("error", "Unknown error"),
        }

    elapsed: float = 0
    while True:
        fills_db_after = await get_fill_list()
        if len(fills_db_after) > len(fills_db_before):
            break

        await asyncio.sleep(5)
        elapsed += 5

        if elapsed > 120:
            return {
                "result": False,
                "pk": None,
                "error": "Timeout waiting for fill to start",
            }

    await asyncio.sleep(3)

    db_data = await get_fill_list()
    pk = max(db_data.keys())

    return {"result": True, "pk": pk, "error": None}
