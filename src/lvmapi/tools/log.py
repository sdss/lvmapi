#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-08-06
# @Filename: log.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import pathlib
import re

from astropy.io import fits
from pydantic import BaseModel


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


def get_mjds():
    """Returns a list of MJDs with spectrograph data (or at least a folder)."""

    paths = list(pathlib.Path("/data/spectro/").glob("*"))
    mjds: list[int] = []
    for path in paths:
        try:
            mjd = int(path.parts[-1])
            mjds.append(mjd)
        except ValueError:
            continue

    return sorted(mjds)


def get_exposures(mjd: int):
    """Returns a list of spectrograph exposures for an MJD."""

    files = pathlib.Path(f"/data/spectro/{mjd}/").glob("*.fits.gz")

    return files


def get_exposure_no(file_: pathlib.Path | str):
    """Returns the exposure number from a file path."""

    file_ = pathlib.Path(file_)
    name = file_.name

    match = re.match(r"sdR-s-[brz][1-3]-(\d+).fits.gz", name)
    if not match:
        return None

    return int(match.group(1))


def get_exposure_paths(mjd: int, exposure_no: int):
    """Returns the path to the exposure file."""

    return pathlib.Path(f"/data/spectro/{mjd}/").glob(f"*{exposure_no}.fits.gz")


def get_exposure_data(mjd: int):
    """Returns the data for the exposures from a given MJD."""

    data: dict[int, ExposureDataDict] = {}
    files = list(get_exposures(mjd))

    exposure_nos = [get_exposure_no(file_) for file_ in files]
    exposure_nos_set = set([e_no for e_no in exposure_nos if e_no is not None])

    for exposure_no in sorted(exposure_nos_set):
        exposure_paths = list(get_exposure_paths(mjd, exposure_no))

        if len(exposure_paths) == 0:
            data[exposure_no] = ExposureDataDict(
                exposure_no=exposure_no,
                mjd=mjd,
                n_cameras=0,
            )
            continue

        with fits.open(exposure_paths[0]) as hdul:
            header = hdul[0].header

        obstime = header.get("OBSTIME", "")
        image_type = header.get("IMAGETYP", "")
        exposure_time = header.get("EXPTIME", None)
        ra = header.get("TESCIRA", None)
        dec = header.get("TESCIDE", None)
        airmass = header.get("TESCIAM", None)
        n_standards = sum([header[f"STD{nn}ACQ"] for nn in range(1, 13)])
        n_cameras = len(exposure_paths)
        object = header.get("OBJECT", "")

        lamps = {
            lamp_name: header[lamp_header] == "ON"
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
            airmass=airmass,
            lamps=lamps,
            n_standards=n_standards,
            n_cameras=n_cameras,
            object=object,
        )

    return data
