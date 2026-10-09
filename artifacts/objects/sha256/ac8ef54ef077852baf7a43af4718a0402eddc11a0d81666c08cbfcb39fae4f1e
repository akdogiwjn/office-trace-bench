# Runtime for REAL Agent trace generation. No frozen replay recipes.
ARG BASE_IMAGE=ubuntu-openclaw-chromium:24.04-linuxarm64
FROM ${BASE_IMAGE}
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates fonts-dejavu-core libreoffice-calc poppler-utils procps \
    python3 python3-pip python3-venv && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/office-runtime-requirements.txt
COPY vendor/wheels /tmp/office-runtime-wheels
RUN python3 -m pip install --break-system-packages --no-cache-dir --no-index \
    --find-links /tmp/office-runtime-wheels -r /tmp/office-runtime-requirements.txt && \
    rm -rf /tmp/office-runtime-wheels && openclaw --version && node --version
WORKDIR /project
CMD ["bash"]
