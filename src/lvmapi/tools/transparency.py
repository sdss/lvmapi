#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-11
# @Filename: transparency.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from lvmapi.tools.influxdb import query_influxdb


async def get_transparency(start_time: float, end_time: float):
    """Returns transparency measurements."""

    query = rf"""
from(bucket: "actors")
  |> range(start: {start_time*1000}, stop: {end_time*1000})
  |> filter(fn: (r) => (r["_measurement"] =~ /lvm\.[a-z]+\.guider/) and
                        (r["_field"] == "measured_pointing.zero_point"))
  |> yield(name: "mean")
"""

    data = await query_influxdb(query)

    return data
