# syntax=docker/dockerfile:1
# Repository context; only these two public metadata files are copied.
FROM --platform=linux/amd64 ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852

COPY packaging/linux/toolchain.json /opt/toolchain.json
COPY pyproject.toml /opt/pyproject.toml

# CPython headers, ELF inspection/PyInstaller, then Qt XCB/Wayland and Chromium.
# Apt versions are recorded, not locked; no claim of byte-reproducible images.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates curl xz-utils build-essential pkg-config \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
    libffi-dev liblzma-dev libncurses-dev libgdbm-dev libgdbm-compat-dev \
    libexpat1-dev libuuid1 uuid-dev tk-dev \
    binutils file patchelf \
    libglib2.0-0t64 libdbus-1-3 libnss3 libnspr4 \
    libatk1.0-0t64 libatk-bridge2.0-0t64 libatspi2.0-0t64 \
    libcups2t64 libdrm2 libgbm1 libasound2t64 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 libxext6 \
    libxfixes3 libxrandr2 libxrender1 libxkbcommon0 libxkbcommon-x11-0 \
    libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xfixes0 \
    libxcb-xinerama0 libxcb-xkb1 libxcb-sync1 libxcb-render0 libxcb-shm0 \
    libwayland-client0 libwayland-cursor0 libwayland-egl1 \
    libegl1 libgl1 libopengl0 libfontconfig1 libfreetype6 \
    libpango-1.0-0 libcairo2 fonts-liberation xvfb xauth \
    && useradd --create-home --uid 10001 --shell /bin/bash builder \
    && mkdir -p /opt/provenance /work \
    && cp /opt/toolchain.json /opt/pyproject.toml /opt/provenance/ \
    && dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > /opt/provenance/apt.tsv \
    && ldd --version > /opt/provenance/glibc.txt \
    && chown -R builder:builder /opt/provenance /work

ENV PYTHON_VERSION=3.13.5 \
    PYTHON_URL=https://www.python.org/ftp/python/3.13.5/Python-3.13.5.tar.xz \
    PYTHON_SHA256=93e583f243454e6e9e4588ca2c2662206ad961659863277afcdb96801647d640 \
    PATH=/home/builder/venv/bin:/home/builder/python/bin:$PATH \
    LD_LIBRARY_PATH=/home/builder/python/lib \
    PLAYWRIGHT_BROWSERS_PATH=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
USER builder
WORKDIR /home/builder

# Fail closed on digest mismatch BEFORE parsing the archive. Compilation and
# all Python/package/browser operations run without root privileges.
RUN curl --fail --location --retry 3 "$PYTHON_URL" -o Python.tar.xz \
    && printf '%s  Python.tar.xz\n' "$PYTHON_SHA256" | sha256sum -c - \
    && tar -xJf Python.tar.xz \
    && cd "Python-$PYTHON_VERSION" \
    && ./configure --prefix=/home/builder/python --enable-shared --with-ensurepip=install \
    && make -j2 && make install \
    && python3.13 -m venv /home/builder/venv

# Fail image construction if required stdlib extensions were silently omitted.
RUN python - <<'CHECK_PYTHON'
import bz2, ctypes, curses, dbm.gnu, hashlib, lzma, multiprocessing
import readline, sqlite3, ssl, tkinter, uuid, venv, zlib
import sys
assert sys.version_info[:3] == (3, 13, 5)
CHECK_PYTHON

# Install precisely the existing .[build] requirement set, without installing
# the application or copying src/, .git/, a host venv, or local records.
RUN python - <<'INSTALL_DEPS'
from pathlib import Path
import subprocess
import sys
import tomllib

metadata = tomllib.loads(Path('/opt/pyproject.toml').read_text(encoding='utf-8'))
requirements = list(dict.fromkeys(
    metadata['project']['dependencies']
    + metadata['project']['optional-dependencies']['build']
    + metadata['build-system']['requires']
))
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', *requirements])
INSTALL_DEPS

RUN python -m playwright install chromium \
    && python -VV > /opt/provenance/python.txt \
    && python -m pip freeze --all > /opt/provenance/python-packages.txt \
    && python -m pip inspect > /opt/provenance/python-packages.json \
    && python -m playwright --version > /opt/provenance/playwright.txt \
    && cp /home/builder/venv/lib/python3.13/site-packages/playwright/driver/package/browsers.json /opt/provenance/browsers.json \
    && gcc --version > /opt/provenance/compiler.txt \
    && python -m PyInstaller --version > /opt/provenance/pyinstaller.txt

WORKDIR /work
CMD ["python", "--version"]
