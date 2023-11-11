#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-07-24
# @Filename: app.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from fastapi import FastAPI

from lvmapi.routers import telescopes


app = FastAPI()
app.include_router(telescopes.router)


@app.get("/")
def root():
    return {}
