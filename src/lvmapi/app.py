#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-07-24
# @Filename: app.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from fastapi import FastAPI

from lvmapi import auth
from lvmapi.routers import (
    enclosure,
    ephemeris,
    macros,
    overwatcher,
    slack,
    spectrographs,
    telescopes,
    weather,
)


app = FastAPI()
app.include_router(auth.router)
app.include_router(telescopes.router)
app.include_router(spectrographs.router)
app.include_router(slack.router)
app.include_router(ephemeris.router)
app.include_router(overwatcher.router)
app.include_router(weather.router)
app.include_router(macros.router)
app.include_router(enclosure.router)


@app.get("/")
def root():
    return {}
