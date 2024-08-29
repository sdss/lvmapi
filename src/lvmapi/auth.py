#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-19
# @Filename: auth.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

# Mostly adapted from https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/

from __future__ import annotations

import ipaddress
import os
from datetime import UTC, datetime, timedelta

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel


__all__ = ["validate_token", "Token", "AuthDependency"]


# Adapted from https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/

# To get a string like this run: openssl rand -hex 32
# Secret key and password are expected to be in environment variables.
# For production deployment in Kubernetes with use an opaque secret.
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 180  # 180 days

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

# The subnet_or_token allows requests from this domain to bypass the token validation.
ALLOW_SUBNET: str = "10.8.38.0/24"


class Token(BaseModel):
    access_token: str
    token_type: str


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter(prefix="/auth", tags=["auth"])


def verify_password(plain_password: str):
    """Verifies that the password passed matches the hashed one stored in the envvar."""

    PASSWORD = os.getenv("LVMAPI_PASSWORD")  # Already hashed.
    if not PASSWORD:
        return False

    return pwd_context.verify(plain_password, PASSWORD)


def get_password_hash(password: str):
    """Creates a hashed password."""

    return pwd_context.hash(password)


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
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)

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


async def subnet_or_token(request: Request):
    """Validates a token or allows localhost."""

    if request.client:
        host = request.client.host
        if ipaddress.ip_address(host) in ipaddress.ip_network(ALLOW_SUBNET):
            return {"authorised": True}

    token = await oauth2_scheme(request)
    if not token:
        raise CREDENTIALS_EXCEPTION

    return await validate_token(token)


@router.post("/login", response_model=Token)
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


@router.get("/test", dependencies=[Depends(validate_token)])
async def route_get_test():
    """A simple route to test validation."""

    return True


AuthDependency = Depends(validate_token)
