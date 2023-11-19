#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-19
# @Filename: influxdb.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os
import warnings

from typing import TYPE_CHECKING

from lvmapi import config


if TYPE_CHECKING:
    import pandas


__all__ = ["query_influxdb"]


async def query_influxdb(query: str) -> pandas.DataFrame:
    """Runs a query in InfluxDB and returns a Pandas dataframe."""

    from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
    from influxdb_client.client.warnings import MissingPivotFunction

    warnings.simplefilter("ignore", MissingPivotFunction)  # noqa: F821

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
