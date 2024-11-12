#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-11
# @Filename: transparency.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import polars

from lvmapi.tools.influxdb import query_influxdb


async def get_transparency(start_time: float, end_time: float):
    """Returns transparency measurements."""

    query = rf"""
from(bucket: "actors")
  |> range(start: {int(start_time)}, stop: {int(end_time)})
  |> filter(fn: (r) => (r["_measurement"] =~ /lvm\.[a-z]+\.guider/) and
                        (r["_field"] == "measured_pointing.zero_point"))
  |> yield(name: "mean")
"""

    data = await query_influxdb(query)

    # Clean up the dataframe.
    data = data.select(
        time=polars.col._time,
        telescope=polars.col._measurement.str.extract(r"lvm\.([a-z]+)\.guider"),
        zero_point=polars.col._value,
    )

    return data
