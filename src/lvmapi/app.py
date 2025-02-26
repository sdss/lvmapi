#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-07-24
# @Filename: app.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from typing import AsyncIterator

import sentry_sdk
import taskiq_fastapi
from fastapi import FastAPI, HTTPException, Request
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis.asyncio.client import Redis

from lvmopstools.kubernetes import Kubernetes

from lvmapi import __version__, auth, config
from lvmapi.broker import broker, broker_shutdown, broker_startup
from lvmapi.cache import valis_cache_key_builder
from lvmapi.routers import (
    actors,
    alerts,
    enclosure,
    ephemeris,
    kubernetes,
    logs,
    macros,
    notifications,
    overwatcher,
    slack,
    spectrographs,
    system,
    tasks,
    telescopes,
    transparency,
    weather,
)


logger = logging.getLogger("uvicorn.error")

if config._CONFIG_FILE is not None:
    logger.info(f"Using configuration from {config._CONFIG_FILE}.")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Start cache backend.
    redis = Redis.from_url("redis://localhost")
    FastAPICache.init(
        RedisBackend(redis),
        prefix="fastapi-cache",
        key_builder=valis_cache_key_builder,
    )

    # Start task broker.
    await broker_startup()

    yield

    # Shutdown cache backend.
    await broker_shutdown()


sentry_sdk.init(
    dsn=os.getenv("LVMAPI_SENTRY_DSN", None),
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    _experiments={
        # Set continuous_profiling_auto_start to True
        # to automatically start the profiler on when
        # possible.
        "continuous_profiling_auto_start": True,
    },
    release=f"lvmapi@{__version__}",
    environment=os.getenv("LVMAPI_ENVIRONMENT", "production"),
)

app = FastAPI(swagger_ui_parameters={"tagsSorter": "alpha"}, lifespan=lifespan)

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
app.include_router(kubernetes.router)
app.include_router(actors.router)
app.include_router(logs.router)
app.include_router(notifications.router)
app.include_router(transparency.router)
app.include_router(system.router)


@app.get("/id")
async def get_id_route(request: Request):
    """Returns the ID of the FastAPI app."""

    return id(request.app)


# Integration with FastAPI.
taskiq_fastapi.init(broker, "lvmapi.app:app")

# Add kubernetes API instance to state. Ignore when running tests in GitHub Actions.
if not os.getenv("GITHUB_ACTIONS", False):
    app.state.kubernetes = Kubernetes(
        deployments_path=config["kubernetes.deployments_path"]
    )

# Fake states for testing.
app.state.use_fake_states = os.environ.get("LVM_USE_FAKE_STATES", "0") != "0"
app.state.fake_states = {
    "wind_alert": False,
    "humidity_alert": False,
    "rain_alert": False,
    "door_alert": False,
    "is_day": False,
}


@app.get("/fake-states/enable", include_in_schema=False)
async def route_get_enable_states():
    """Enable fake states."""

    app.state.use_fake_states = True

    return {"use_fake_states": app.state.use_fake_states}


@app.get("/fake-states/disable", include_in_schema=False)
async def route_get_disable_states():
    """Disable fake states."""

    app.state.use_fake_states = False

    return {"use_fake_states": app.state.use_fake_states}


@app.get("/fake-states/set/{state}/{value}", include_in_schema=False)
async def route_get_set_fake_state(state: str, value: bool):
    """Sets a fake state."""

    if state not in app.state.fake_states:
        raise HTTPException(400, f"Invalid state {state!r}")

    app.state.fake_states[state] = value

    return {"state": state, "value": app.state.fake_states[state]}


@app.get("/fake-states/get", include_in_schema=False)
async def route_get_get_fake_state_all():
    """Queries the value of all fake states."""

    return {
        "use_fake_states": app.state.use_fake_states,
        "fake_States": app.state.fake_states,
    }


@app.get("/fake-states/get/{state}", include_in_schema=False)
async def route_get_get_fake_state(state: str):
    """Queries the value of a fake state."""

    if state not in app.state.fake_states:
        raise HTTPException(400, f"Invalid state {state!r}")

    return {
        "use_fake_states": app.state.use_fake_states,
        "state": state,
        "value": app.state.fake_states[state],
    }


@app.get("/")
def root():
    return {}


@app.get("/test")
def test():
    return {"result": True}


@app.get("/sentry-debug")
async def trigger_error():
    return 1 / 0
