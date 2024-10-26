#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-03-24
# @Filename: schedule.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import pathlib

import astroplan
import numpy
import polars
from astropy import units as uu
from astropy.time import Time
from cachetools import TTLCache, cached

from sdsstools import get_sjd


EPHEMERIS_FILE = pathlib.Path(__file__).parent / "../data/ephemeris.parquet"


@cached(TTLCache(maxsize=3, ttl=3600))
def get_ephemeris_data(filename: pathlib.Path | str) -> polars.DataFrame:
    """Returns and caches the data from the ephemeris file."""

    return polars.read_parquet(filename)


def sjd_ephemeris(sjd: int, twilight_horizon: float = -15) -> polars.DataFrame:
    """Returns the ephemeris for a given SJD."""

    observer = astroplan.Observer.at_site("Las Campanas Observatory")
    observer.pressure = 0.76 * uu.bar

    # Calculate Elevation of True Horizon. Astroplan does not provide this directly.
    # See https://github.com/astropy/astroplan/issues/242
    h_observer = observer.elevation
    R_earth = 6378100.0 * uu.m
    dd = numpy.sqrt(h_observer * (2 * R_earth + h_observer))
    phi = (numpy.arccos((dd / R_earth).value) * uu.radian).to(uu.deg)
    hzel = phi - 90 * uu.deg

    # Calculate time at ~15UT, which corresponds to about noon at LCO, so always
    # before the beginning of the night.
    time = Time(sjd - 0.35, format="mjd", scale="utc")

    sunset = observer.sun_set_time(
        time,
        which="next",
        horizon=hzel - 0.5 * uu.deg,  # Apparent size of the Sun.
    )
    sunset_twilight = observer.sun_set_time(
        time,
        which="next",
        horizon=twilight_horizon * uu.deg,
    )

    sunrise = observer.sun_rise_time(
        time,
        which="next",
        horizon=hzel - 0.5 * uu.deg,
    )
    sunrise_twilight = observer.sun_rise_time(
        time,
        which="next",
        horizon=twilight_horizon * uu.deg,
    )

    moon_illumination = observer.moon_illumination(time)

    df = polars.DataFrame(
        [
            (
                sjd,
                time.isot.split("T")[0],
                sunset.jd,
                sunset_twilight.jd,
                sunrise_twilight.jd,
                sunrise.jd,
                moon_illumination,
            )
        ],
        schema={
            "SJD": polars.Int32,
            "date": polars.String,
            "sunset": polars.Float64,
            "twilight_end": polars.Float64,
            "twilight_start": polars.Float64,
            "sunrise": polars.Float64,
            "moon_illumination": polars.Float32,
        },
        orient="row",
    )

    return df


def create_schedule(
    start_sjd: int,
    end_sjd: int,
    twilight_horizon: float = -15,
) -> polars.DataFrame:
    """Creates a schedule for the given time range.

    Parameters
    ----------
    start_sjd
        The initial SJD.
    end_sjd
        The final SJD of the schedule.

    Returns
    -------
    schedule
        The schedule as a Polars dataframe.

    """

    start_sjd = start_sjd or get_sjd("LCO")

    ephemeris: list[polars.DataFrame] = []
    for sjd in range(start_sjd, end_sjd + 1):
        sjd_eph = sjd_ephemeris(sjd, twilight_horizon=twilight_horizon)
        ephemeris.append(sjd_eph)

    return polars.concat(ephemeris)


def get_ephemeris_summary(sjd: int | None = None) -> dict:
    """Returns a summary of the ephemeris for a given SJD."""

    sjd = sjd or get_sjd("LCO")

    from_file = True
    eph = get_ephemeris_data(EPHEMERIS_FILE)

    data = eph.filter(polars.col("SJD") == sjd)
    if len(data) == 0:
        data = sjd_ephemeris(sjd)
        from_file = False

    sunset = Time(data["sunset"][0], format="jd")
    sunrise = Time(data["sunrise"][0], format="jd")
    twilight_end = Time(data["twilight_end"][0], format="jd")
    twilight_start = Time(data["twilight_start"][0], format="jd")

    time_to_sunset = (sunset - Time.now()).to(uu.h).value
    time_to_sunrise = (sunrise - Time.now()).to(uu.h).value

    is_twilight_evening = (
        Time(data["sunset"][0], format="jd")
        < Time.now()
        < Time(data["twilight_end"][0], format="jd")
    )

    is_twilight_morning = (
        Time(data["twilight_start"][0], format="jd")
        < Time.now()
        < Time(data["sunrise"][0], format="jd")
    )

    is_night = (
        Time(data["twilight_end"][0], format="jd")
        < Time.now()
        < Time(data["twilight_start"][0], format="jd")
    )

    return {
        "SJD": int(sjd),
        "request_jd": float(Time.now().jd),
        "date": data["date"][0],
        "sunset": float(sunset.jd),
        "twilight_end": float(twilight_end.jd),
        "twilight_start": float(twilight_start.jd),
        "sunrise": float(sunrise.jd),
        "is_night": bool(is_night),
        "is_twilight": bool(is_twilight_evening or is_twilight_morning),
        "time_to_sunset": round(float(time_to_sunset), 3),
        "time_to_sunrise": round(float(time_to_sunrise), 3),
        "moon_illumination": round(float(data["moon_illumination"][0]), 3),
        "from_file": from_file,
    }
