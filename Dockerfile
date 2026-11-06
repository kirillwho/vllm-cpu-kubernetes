ARG PYTHON_BASE
FROM ${PYTHON_BASE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libnuma1 libtcmalloc-minimal4 && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -m pip check
RUN groupadd -g 10001 app && useradd -u 10001 -g 10001 -m app
WORKDIR /app
COPY --chown=10001:10001 app/ /app/
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/tmp/hf \
    XDG_CACHE_HOME=/tmp/cache VLLM_CACHE_ROOT=/tmp/vllm \
    VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 \
    VLLM_LOGGING_CONFIG_PATH=/app/logging.json
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "/app/launch.py"]
