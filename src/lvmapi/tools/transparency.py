#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-11
# @Filename: transparency.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import polars

from lvmopstools.influxdb import query_influxdb

from lvmapi import config


async def get_transparency(start_time: float, end_time: float):
    """Returns transparency measurements."""

    query = rf"""
from(bucket: "actors")
  |> range(start: {int(start_time)}, stop: {int(end_time)})
  |> filter(fn: (r) => (r["_measurement"] =~ /lvm\.[a-z]+\.guider/) and
                        (r["_field"] == "measured_pointing.zero_point"))
  |> yield(name: "mean")
"""

    DT_TYPE = polars.Datetime(time_unit="ms", time_zone="UTC")
    SCHEMA: dict[str, polars.DataType] = {
        "date": DT_TYPE,
        "timestamp": polars.Float64(),
        "telescope": polars.String(),
        "zero_point": polars.Float32(),
    }

    data = await query_influxdb(
        config["influxdb.url"],
        query,
        org=config["influxdb.org"],
    )

    if len(data) == 0:
        return polars.DataFrame(None, schema=SCHEMA)

    # Clean up the dataframe.
    data = data.select(
        date=polars.col._time,
        timestamp=polars.col._time.cast(DT_TYPE).dt.timestamp("ms").truediv(1_000),
        telescope=polars.col._measurement.str.extract(r"lvm\.([a-z]+)\.guider"),
        zero_point=polars.col._value,
    ).cast(SCHEMA)  # type: ignore

    return data
