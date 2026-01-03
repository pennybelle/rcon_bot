FROM python:3.11-bullseye AS builder-image

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/

RUN python -m pip install -r requirements.txt

COPY setup.py /app/setup.py
COPY setup.cfg /app/setup.cfg
COPY versioneer.py /app/versioneer.py
COPY pyproject.toml /app/pyproject.toml

COPY src /app/src
COPY . .

CMD [ "python", "-u", "./src/rcon/__main__.py"]