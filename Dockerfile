FROM python:3.11-slim-bookworm

MAINTAINER Jose Sanchez-Gallego, gallegoj@uw.edu
LABEL org.opencontainers.image.source https://github.com/albireox/lvmapi

WORKDIR /opt

COPY . lvmapi

RUN pip3 install -U pip setuptools wheel
RUN cd lvmapi && pip3 install .

CMD ["uvicorn", "lvmapi.app:app", "--host", "0.0.0.0", "--port", "80"]
