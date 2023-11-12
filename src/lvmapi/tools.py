#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-07-24
# @Filename: tools.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os
import warnings

from typing import TYPE_CHECKING

from clu import AMQPClient

from lvmapi.types import Cameras, Sensors

from . import config


if TYPE_CHECKING:
    import pandas

    from lvmapi.routers.spectrographs import Spectrographs


__all__ = [
    "CluClient",
    "get_spectrograph_temperature_label",
    "get_spectrograph_temperatures",
    "get_spectrograph_pressures",
    "get_spectrograph_mechanics",
    "query_influxdb",
]


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


def get_spectrograph_temperature_label(camera: str, sensor: str = "ccd"):
    """Returns the archon label associated with a temperature sensor."""

    if sensor == "ccd":
        if camera == "r":
            return "mod2/tempa"
        elif camera == "b":
            return "mod12/tempc"
        elif camera == "z":
            return "mod12/tempa"

    else:
        if camera == "r":
            return "mod2/tempb"
        elif camera == "b":
            return "mod2/tempc"
        elif camera == "z":
            return "mod12/tempb"


async def get_spectrograph_temperatures(spec: Spectrographs):
    """Returns a dictionary of spectrograph temperatures."""

    async with CluClient() as client:
        scp_command = await client.send_command(
            f"lvmscp.{spec}",
            "status",
            internal=True,
        )

    if scp_command.status.did_fail:
        raise ValueError("Failed retrieving status from SCP.")

    status = scp_command.replies.get("status")

    response: dict[str, float] = {}

    cameras: list[Cameras] = ["r", "b", "z"]
    sensors: list[Sensors] = ["ccd", "ln2"]

    for camera in cameras:
        for sensor in sensors:
            label = get_spectrograph_temperature_label(camera, sensor)
            if label not in status:
                raise ValueError(f"Cannot find status label {label!r}.")
            response[f"{camera}{spec[-1]}_{sensor}"] = status[label]

    return response


async def get_spectrograph_pressures(spec: Spectrographs):
    """Returns a dictionary of spectrograph pressures."""

    async with CluClient() as client:
        ieb_command = await client.send_command(
            f"lvmieb.{spec}",
            "transducer status",
            internal=True,
        )

    if ieb_command.status.did_fail:
        raise ValueError("Failed retrieving status from IEB.")

    pressures = ieb_command.replies.get("transducer")

    response: dict[str, float] = {}
    for key in pressures:
        if "pressure" in key:
            response[key] = pressures[key]

    return response


async def get_spectrograph_mechanics(spec: Spectrographs):
    """Returns a dictionary of spectrograph shutter and hartmann door status."""

    response: dict[str, str] = {}

    async with CluClient() as client:
        for device in ["shutter", "hartmann"]:
            ieb_cmd = await client.send_command(
                f"lvmieb.{spec}",
                f"{device} status",
                internal=True,
            )

            if ieb_cmd.status.did_fail:
                raise ValueError(f"Failed retrieving {device } status from IEB.")

            if device == "shutter":
                key = f"{spec}_shutter"
                response[key] = "open" if ieb_cmd.replies.get(key)["open"] else "closed"
            else:
                for door in ["left", "right"]:
                    key = f"{spec}_hartmann_{door}"
                    reply = ieb_cmd.replies.get(key)
                    response[key] = "open" if reply["open"] else "closed"

    return response


async def query_influxdb(query: str) -> pandas.DataFrame:
    """Runs a query in InfluxDB and returns a Pandas dataframe."""

    from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
    from influxdb_client.client.warnings import MissingPivotFunction

    warnings.simplefilter("ignore", MissingPivotFunction)

    host = config["influxdb.host"]
    port = config["influxdb.port"]

    token = config["influxdb.token"] or os.environ.get("INFLUXDB_V2_TOKEN")
    if token is None:
        raise ValueError("$INFLUXDB_V2_TOKEN not defined.")

    async with InfluxDBClientAsync(
        url=f"http://{host}:{port}",
        token=token,
        org=config["influxdb.org"],
    ) as client:
        if not (await client.ping()):
            raise RuntimeError("InfluxDB client failed to connect.")

        api = client.query_api()
        return await api.query_data_frame(query)
