FROM python:3.11-slim-bookworm

MAINTAINER Jose Sanchez-Gallego, gallegoj@uw.edu
LABEL org.opencontainers.image.source https://github.com/albireox/lvmapi

WORKDIR /opt

COPY . lvmapi

RUN pip3 install -U pip setuptools wheel
RUN cd lvmapi && pip3 install .
RUN rm -Rf lvmapi

ENTRYPOINT gunicorn lvmapi.app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:80
