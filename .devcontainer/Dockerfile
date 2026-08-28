FROM python:3.11-slim-bookworm

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        openssh-client \
    && groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} --create-home \
        --shell /bin/bash ${USERNAME} \
    # Docker copies this ownership into the newly-created persistent home
    # volume, so VS Code can bootstrap its server as the non-root user.
    && mkdir -p /home/${USERNAME}/.vscode-server/bin \
        /home/${USERNAME}/.vscode-server/data \
    && chown -R ${USERNAME}:${USERNAME} /home/${USERNAME} \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-dev.txt /tmp/ti84-chess-requirements.txt

RUN python -m venv /opt/ti84-chess-venv \
    && /opt/ti84-chess-venv/bin/pip install --no-cache-dir \
        -r /tmp/ti84-chess-requirements.txt \
    && rm /tmp/ti84-chess-requirements.txt

ENV VIRTUAL_ENV=/opt/ti84-chess-venv
ENV PATH="/opt/ti84-chess-venv/bin:${PATH}"
