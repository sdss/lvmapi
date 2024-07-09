#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-19
# @Filename: auth.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

# Mostly adapted from https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/

from __future__ import annotations

import os
from datetime import datetime, timedelta

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel


__all__ = ["validate_token", "Token", "TokenDepends"]


# To get a string like this run: openssl rand -hex 32
# Secret key and password are expected to be in environment variables.
# For production deployment in Kubernetes with use an opaque secret.
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


class Token(BaseModel):
    access_token: str
    token_type: str


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter(tags=["auth"])


def verify_password(plain_password: str):
    """Verifies that the password passed matches the hashed one stored in the envvar."""

    PASSWORD = os.getenv("LVMAPI_PASSWORD")  # Already hashed.
    if not PASSWORD:
        return False

    return pwd_context.verify(plain_password, PASSWORD)


def authenticate(password: str):
    """Authenticates the user."""

    if not verify_password(password):
        return False

    return True


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Creates an access token with expiration date."""

    if SECRET_KEY is None:
        raise CREDENTIALS_EXCEPTION

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


async def validate_token(token: Annotated[str, Depends(oauth2_scheme)]):
    """Validates a token."""

    if SECRET_KEY is None:
        raise CREDENTIALS_EXCEPTION

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        authorised: str | None = payload.get("authorised")
        if authorised is None:
            raise CREDENTIALS_EXCEPTION
    except JWTError:
        raise CREDENTIALS_EXCEPTION

    return {"authorised": True}


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    """Validates the password and generates a temporary token.

    The OAuth2 standard requires an ``username`` and ``password`` but
    here only the password is used. The username string is required but
    ignored.

    """

    if not authenticate(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"authorised": True},
        expires_delta=access_token_expires,
    )

    return {"access_token": access_token, "token_type": "bearer"}


TokenDepends = Annotated[str, Depends(validate_token)]
