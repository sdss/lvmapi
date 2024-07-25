#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-07-24
# @Filename: app.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import taskiq_fastapi
from fastapi import FastAPI

from lvmapi import auth
from lvmapi.broker import broker, broker_shutdown, broker_startup
from lvmapi.routers import (
    alerts,
    enclosure,
    ephemeris,
    macros,
    overwatcher,
    slack,
    spectrographs,
    tasks,
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
app.include_router(alerts.router)
app.include_router(tasks.router)


# Lifecycle events for the broker.
app.add_event_handler("startup", broker_startup)
app.add_event_handler("shutdown", broker_shutdown)

# Integration with FastAPI.
taskiq_fastapi.init(broker, "lvmapi.app:app")


@app.get("/")
def root():
    return {}
