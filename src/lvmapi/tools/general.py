#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-12-03
# @Filename: general.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Any

import psycopg
import psycopg.sql

from lvmapi import config


__all__ = ["get_db_connection", "insert_to_database"]


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
