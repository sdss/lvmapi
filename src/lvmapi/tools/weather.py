#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-03-26
# @Filename: weather.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import time

import httpx
import polars
from astropy.time import Time, TimeDelta


__all__ = ["get_weather_data"]


WEATHER_URL = "http://dataservice.lco.cl/vaisala/data"


async def get_weather_data(
    end_time: str | None = None,
    start_time: str | float = 3600,
    station="DuPont",
):
    """Returns weather data from the Vaisala weather station.

    Parameters
    ----------
    end_time
        The end time for the query. If not provided, the current time is used.
        The time can be an Astropy Time object or a string in ISO format.
    start_time
        The start time for the query. The time can be an Astropy Time object,
        a string in ISO format, or a float indicating with a time delta in seconds
        with respect to ``end_time``.

    Returns
    -------
    dataframe
        A Polars dataframe with the time series weather data.

    """

    if station not in ["DuPont", "C40", "Magellan"]:
        raise ValueError("station must be one of 'DuPont', 'C40', or 'Magellan'.")

    if end_time is None:
        end_time_ap = Time.now()
    elif isinstance(end_time, str):
        end_time_ap = Time(end_time)
    elif isinstance(end_time, Time):
        end_time_ap = end_time
    else:
        raise ValueError("end_time must be a string or an Astropy Time object.")

    if isinstance(start_time, str):
        start_time_ap = Time(start_time)
    elif isinstance(start_time, (int, float)):
        start_time_ap = end_time_ap - TimeDelta(start_time, format="sec")
    elif isinstance(start_time, Time):
        start_time_ap = start_time
    else:
        raise ValueError(
            "start_time must be a string, a time delta in seconds, "
            "or an Astropy Time object."
        )

    end_time_ap.precision = 0
    start_time_ap.precision = 0

    async with httpx.AsyncClient() as client:
        response = await client.get(
            WEATHER_URL,
            params={
                "start_ts": str(start_time_ap.iso),
                "end_ts": str(end_time_ap.iso),
                "station": station,
            },
        )

        if response.status_code != 200:
            raise ValueError(f"Failed to get weather data: {response.text}")

        data = response.json()

        if "Error" in data:
            raise ValueError(f"Failed to get weather data: {data['Error']}")
        elif "results" not in data or data["results"] is None:
            raise ValueError("Failed to get weather data: no results found.")

    results = data["results"]

    df = polars.DataFrame(results)
    df = df.with_columns(
        ts=polars.col("ts").str.to_datetime(time_unit="ms"),
        station=polars.lit(station, polars.String),
    )

    # Delete rows with all null values.
    df = df.filter(~polars.all_horizontal(polars.exclude("ts", "station").is_null()))

    # Sort by timestamp
    df = df.sort("ts")

    # Convert wind speeds to mph (the LCO API returns km/h)
    df = df.with_columns(polars.selectors.starts_with("wind_") / 1.60934)

    # Calculate rolling means for average wind speed and gusts every 5m, 10m, 30m
    window_sizes = ["5m", "10m", "30m"]
    df = df.with_columns(
        **{
            f"wind_speed_avg_{ws}": polars.col.wind_speed_avg.rolling_mean_by(
                by="ts",
                window_size=ws,
            )
            for ws in window_sizes
        },
        **{
            f"wind_gust_{ws}": polars.col.wind_speed_max.rolling_max_by(
                by="ts",
                window_size=ws,
            )
            for ws in window_sizes
        },
        **{
            f"wind_dir_avg_{ws}": polars.col.wind_dir_avg.rolling_mean_by(
                by="ts",
                window_size=ws,
            )
            for ws in window_sizes
        },
    )

    # Add simple dew point.
    df = df.with_columns(
        dew_point=polars.col.temperature
        - ((100 - polars.col.relative_humidity) / 5.0).round(2)
    )

    return df


def is_measurament_safe(
    data: polars.DataFrame,
    measurement: str,
    threshold: float,
    window: int = 30,
    rolling_average_window: int = 30,
    reopen_value: float | None = None,
):
    """Determines whether an alert should be raised for a given measurement.

    An alert will be issued if the rolling average value of the ``measurement``
    (a column in ``data``) over the last ``window`` seconds is above the
    ``threshold``. Once the alert has been raised  the value of the ``measurement``
    must fall below the ``reopen_value`` to close the alert (defaults to the same
    ``threshold`` value) in a rolling.

    ``window`` and ``rolling_average_window`` are in minutes.

    Returns
    -------
    result
        A boolean indicating whether the measurement is safe. `True` means the
        measurement is in a valid, safe range.

    """

    if measurement not in data.columns:
        raise ValueError(f"Measurement {measurement} not found in data.")

    reopen_value = reopen_value or threshold

    data = data.select(polars.col.ts, polars.col(measurement))
    data = data.with_columns(
        average=polars.col(measurement).rolling_mean_by(
            by="ts",
            window_size=f"{rolling_average_window}m",
        )
    )

    # Get data from the last window`.
    now = time.time()
    data_window = data.filter(polars.col.ts.dt.timestamp("ms") > (now - window * 60))

    # If any of the values in the last "window" is above the threshold, it's unsafe.
    if (data_window["average"] >= threshold).any():
        return False

    # If all the values in the last "window" are below the reopen threshold, it's safe.
    if (data_window["average"] < reopen_value).all():
        return True

    # The last case is if the values in the last "window" are between the reopen and
    # the threshold values. We want to avoid the returned value flipping from true
    # to false in a quick manner. We check the previous "window" minutes to see if
    # the alert was raised at any point. If so, we require the current window to
    # be below the reopen value. Otherwise, we consider it's safe.

    prev_window = data.filter(
        polars.col.ts.dt.timestamp("ms") > (now - 2 * window * 60),
        polars.col.ts.dt.timestamp("ms") < (now - window * 60),
    )
    if (prev_window["average"] >= threshold).any():
        return (data_window["average"] < reopen_value).all()

    return True
