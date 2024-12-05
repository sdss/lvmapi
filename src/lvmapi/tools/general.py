#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-12-03
# @Filename: general.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import functools
import json
from datetime import datetime, timedelta, timezone

from typing import Any, Type, TypeVar

import psycopg
import psycopg.sql
from aiocache import Cache
from fastapi import HTTPException
from pydantic import BaseModel

from lvmapi import config


__all__ = [
    "timed_cache",
    "get_db_connection",
    "insert_to_database",
]


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
        next_update = datetime.now(timezone.utc) + update_delta

        # Apply @lru_cache to f with no cache size limit
        f = functools.lru_cache(None)(f)

        @functools.wraps(f)
        def _wrapped(*args, **kwargs):
            nonlocal next_update
            now = datetime.now(timezone.utc)
            if now >= next_update:
                f.cache_clear()
                next_update = now + update_delta
            return f(*args, **kwargs)

        return _wrapped

    return _wrapper


def get_db_connection():
    """Returns a connection to the database."""

    uri = config["database.uri"]

    return psycopg.AsyncConnection.connect(uri)


async def insert_to_database(
    table_name: str,
    data: list[dict[str, Any]],
    columns: list[str] | None = None,
):
    """Inserts data into the database.

    Parameters
    ----------
    table_name
        The table in the database where to insert the data. Can be in the format
        ``schema.table_name``.
    data
        The data to ingest, as a list of dictionaries in which each dictionary
        is a mapping of column name in ``table`` to the value to ingest.
    columns
        A list of table columns. If not passed, the column names are inferred from
        the first element in the data. In this case you must ensure that all the
        elements in the data contain entries for all the columns (use :obj:`None`
        to fill missing data).

    """

    if len(data) == 0:
        return

    columns = columns or list(data[0].keys())

    schema: str | None
    table: psycopg.sql.Identifier
    if "." in table_name:
        schema, table_name = table_name.split(".")
        table = psycopg.sql.Identifier(schema, table_name)
    else:
        table = psycopg.sql.Identifier(table_name)

    columns_sql = [psycopg.sql.Identifier(col) for col in columns]

    column_placeholders = ("{}, " * len(columns))[0:-2]
    values_placeholders = ("%s, " * len(columns))[0:-2]

    query = psycopg.sql.SQL(
        "INSERT INTO {} ("
        + column_placeholders
        + ") VALUES ("
        + values_placeholders
        + ");"
    ).format(
        table,
        *columns_sql,
    )

    async with await get_db_connection() as aconn:
        async with aconn.cursor() as acursor:
            for row in data:
                values = [row.get(col, None) for col in columns]
                await acursor.execute(query, values)


T = TypeVar("T", bound=BaseModel)


def cache_response(
    key: str,
    ttl: int = 60,
    namespace: str = "lvmapi",
    response_model: Type[T] | None = None,
):
    """Caching decorator for FastAPI endpoints.

    See https://dev.to/sivakumarmanoharan/caching-in-fastapi-unlocking-high-performance-development-20ej

    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{namespace}:{key}"

            assert Cache.REDIS
            cache = Cache.REDIS(
                endpoint="localhost",  # type: ignore
                port=6379,  # type: ignore
                namespace=namespace,
            )

            # Try to retrieve data from cache
            cached_value = await cache.get(cache_key)
            if cached_value:
                if response_model:
                    return response_model(**json.loads(cached_value))
                return json.loads(cached_value)

            # Call the actual function if cache is not hit
            response: T | Any = await func(*args, **kwargs)

            try:
                # Store the response in Redis with a TTL
                if response_model:
                    cacheable = response.model_dump_json()
                else:
                    cacheable = json.dumps(response)

                await cache.set(cache_key, cacheable, ttl=ttl)

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error caching data: {e}")

            return response

        return wrapper

    return decorator
