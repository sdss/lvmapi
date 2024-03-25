#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-03-25
# @Filename: redis.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import redis


__all__ = ["get_redis_connection"]


def get_redis_connection() -> redis.Redis:
    """Returns a connection to the Redis server."""

    return redis.Redis(host="10.8.38.26", port=6379, db=0, decode_responses=True)
