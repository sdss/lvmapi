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
from functools import partial

from typing import TYPE_CHECKING

from fastapi_cache.decorator import cache


if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response


__all__ = ["valis_cache_key_builder", "lvmapi_cache"]


lvmapi_cache = partial(cache, namespace="lvmapi")


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
