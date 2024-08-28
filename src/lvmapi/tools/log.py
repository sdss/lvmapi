#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-08-06
# @Filename: log.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import json
import pathlib

import polars
from pydantic import BaseModel

from lvmapi import config


class ExposureDataDict(BaseModel):
    """A dictionary of exposure data."""

    exposure_no: int
    mjd: int
    obstime: str = ""
    image_type: str = ""
    exposure_time: float | None = None
    ra: float | None = None
    dec: float | None = None
    airmass: float | None = None
    lamps: dict[str, bool] = {}
    n_standards: int = 0
    n_cameras: int = 0
    object: str = ""


def get_spectro_mjds():
    """Returns a list of MJDs with spectrograph data (or at least a folder)."""

    uri = config["database.uri"]
    table = config["database.tables.exposures"]

    df = polars.read_database_uri(
        f"SELECT DISTINCT(mjd) AS mjd FROM {table}",
        uri,
        engine="adbc",
    )

    return sorted(df["mjd"].unique().to_list())


def get_exposures(mjd: int):
    """Returns a list of spectrograph exposures for an MJD."""

    files = pathlib.Path(f"/data/spectro/{mjd}/").glob("*.fits.gz")

    return files


def get_exposure_data(mjd: int):
    """Returns the data for the exposures from a given MJD."""

    uri = config["database.uri"]
    table = config["database.tables.exposures"]

    df = polars.read_database_uri(
        f"""SELECT  exposure_no, image_type, spec, ccd, tile_id,
                    jsonb_path_query("header", '$')::TEXT as header
            FROM {table} WHERE mjd = {mjd}
        """,
        uri,
        engine="adbc",
    ).sort(["exposure_no", "spec", "ccd"])

    data: dict[int, ExposureDataDict] = {}
    exposure_nos = df["exposure_no"].unique().to_list()

    for exposure_no in exposure_nos:
        exp_data = df.filter(polars.col.exposure_no == exposure_no)
        n_cameras = len(exp_data)

        if n_cameras == 0:
            data[exposure_no] = ExposureDataDict(
                exposure_no=exposure_no,
                mjd=mjd,
                n_cameras=0,
            )
            continue

        header = json.loads(exp_data["header"][0])

        obstime = header.get("OBSTIME", "")
        image_type = header.get("IMAGETYP", "")
        exposure_time = header.get("EXPTIME", None)
        ra = header.get("TESCIRA", None)
        dec = header.get("TESCIDE", None)
        airmass = header.get("TESCIAM", None)
        std_acq = [header.get(f"STD{nn}ACQ", None) for nn in range(1, 13)]
        n_standards = sum([std for std in std_acq if std is not None])
        object = header.get("OBJECT", "")

        lamps = {
            lamp_name: header.get(lamp_header, None) == "ON"
            for lamp_header, lamp_name in [
                ("ARGON", "Argon"),
                ("NEON", "Neon"),
                ("LDLS", "LDLS"),
                ("QUARTZ", "Quartz"),
                ("HGNE", "HgNe"),
                ("XENON", "Xenon"),
            ]
        }

        data[exposure_no] = ExposureDataDict(
            exposure_no=exposure_no,
            mjd=mjd,
            obstime=obstime,
            image_type=image_type,
            exposure_time=exposure_time,
            ra=ra,
            dec=dec,
            airmass=airmass if airmass < 100 else -1,
            lamps=lamps,
            n_standards=n_standards,
            n_cameras=n_cameras,
            object=object,
        )

    return data
