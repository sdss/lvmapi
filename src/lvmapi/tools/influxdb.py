#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-19
# @Filename: influxdb.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import json
import os
import warnings

import polars

from lvmapi import config


__all__ = ["query_influxdb"]


async def query_influxdb(query: str) -> polars.DataFrame:
    """Runs a query in InfluxDB and returns a Polars dataframe."""

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

        query_results = await api.query(query)

    df = polars.DataFrame(json.loads(query_results.to_json()))

    if len(df) > 0:
        df = df.with_columns(polars.col._time.cast(polars.Datetime("ms")))

    return df
