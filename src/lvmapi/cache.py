#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-12-10
# @Filename: cache.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from functools import partial

from typing import TYPE_CHECKING, AsyncIterator

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from redis.asyncio.client import Redis

from lvmapi.broker import broker_shutdown, broker_startup


if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.requests import Request
    from starlette.responses import Response


__all__ = ["cache_lifespan", "valis_cache_key_builder", "lvmapi_cache"]


lvmapi_cache = partial(cache, namespace="lvmapi")


@asynccontextmanager
async def cache_lifespan(_: FastAPI) -> AsyncIterator[None]:
    redis = Redis.from_url("redis://localhost")
    FastAPICache.init(
        RedisBackend(redis),
        prefix="fastapi-cache",
        key_builder=valis_cache_key_builder,
    )

    await broker_startup()

    yield

    await broker_shutdown()


async def valis_cache_key_builder(
    func,
    namespace: str = "",
    request: Request | None = None,
    _: Response | None = None,
    *args,
    **kwargs,
):
    """A custom cache key builder for fastapi_cache that supports POST requests."""

    query_params = request.query_params.items() if request else []
    body = []

    if request:
        try:
            body_json = await request.json()
            body = sorted(body_json.items()) if body_json else []
        except json.JSONDecodeError:
            pass

    hash = hashlib.new("md5")
    for param, value in list(query_params) + body:
        hash.update(param.encode())
        hash.update(str(value).encode())

    params_hash = hash.hexdigest()[0:8]

    url = request.url.path.replace("/", "_") if request else ""
    if url.startswith("_"):
        url = url[1:]

    chunks = [
        namespace,
        request.method.lower() if request else "",
        url,
        params_hash,
    ]

    return ":".join(chunks)
