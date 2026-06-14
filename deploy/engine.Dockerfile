# syntax=docker/dockerfile:1
#
# The "engine" image runs both the dashboard backend AND the LLM router. It's
# built once and started as two compose services that share a network namespace,
# so the router can reach the vLLM subprocesses the backend spawns on localhost.
#
# Base ships CUDA + torch + vLLM (and the `vllm` CLI the backend shells out to in
# apps/backend/app/llmops/launchers.py), so we only layer on the Python deps the
# two FastAPI apps need.
FROM vllm/vllm-openai:latest

WORKDIR /app

COPY apps/backend/requirements.txt /tmp/backend-req.txt
COPY apps/router-server/requirements.txt /tmp/router-req.txt
# vllm is already in the base image; pytest* are dev-only. Dropping them avoids
# reinstalling a multi-GB wheel and keeps test deps out of the runtime image.
RUN sed -i -E '/^(vllm|pytest.*)$/d' /tmp/router-req.txt \
    && pip install --no-cache-dir -r /tmp/backend-req.txt -r /tmp/router-req.txt

# App code + shared packages + the gunicorn conf the router boots from. The paths
# mirror the repo so the in-code sys.path bootstrap (repo root = 4 levels up from
# the module) and the config/overlay/db default paths still resolve to /app.
COPY apps/backend ./apps/backend
COPY apps/router-server ./apps/router-server
COPY packages ./packages

# The base image's ENTRYPOINT launches the vLLM OpenAI server; clear it so the
# compose `command:` (uvicorn for backend, gunicorn for router) runs verbatim.
ENTRYPOINT []
CMD ["bash"]
