#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-12-03
# @Filename: general.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import functools
from datetime import datetime, timedelta


__all__ = ["timed_cache"]


def timed_cache(seconds: float):
    """A cache decorator that expires after a certain time.

    Modified from https://gist.github.com/Morreski/c1d08a3afa4040815eafd3891e16b945

    This only works for synchronous functions. For asynchronous functions, use
    ``aiocache.cached``.

    Parameters
    ----------
    seconds
        Number of seconds after which the cache is cleared.

    """

    def _wrapper(f):
        update_delta = timedelta(seconds=seconds)
        next_update = datetime.utcnow() + update_delta

        # Apply @lru_cache to f with no cache size limit
        f = functools.lru_cache(None)(f)

        @functools.wraps(f)
        def _wrapped(*args, **kwargs):
            nonlocal next_update
            now = datetime.utcnow()
            if now >= next_update:
                f.cache_clear()
                next_update = now + update_delta
            return f(*args, **kwargs)

        return _wrapped

    return _wrapper
