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

# Vendored llama.cpp PEFT->GGUF LoRA converter (for the LoRA library's "Convert to
# GGUF" action, so a HF adapter can be used by the llama.cpp engine). We vendor the
# scripts + gguf-py from a PINNED tag (matched to the llama-server build) rather than
# `pip install gguf`, because (a) the `conversion` package that convert_lora_to_gguf
# imports isn't on PyPI, and (b) keeping gguf out of site-packages and on a scoped
# PYTHONPATH guarantees the lib matches the scripts and can't perturb vLLM's deps.
# torch/transformers/safetensors come from the base image. See docs/mixed-engine-deployment.md.
ARG LLAMACPP_CONVERT_TAG=b9853
RUN curl -sL "https://github.com/ggml-org/llama.cpp/archive/refs/tags/${LLAMACPP_CONVERT_TAG}.tar.gz" \
      | tar xz -C /tmp \
    && mkdir -p /opt/llamacpp-convert \
    && cp -r "/tmp/llama.cpp-${LLAMACPP_CONVERT_TAG}/convert_lora_to_gguf.py" \
            "/tmp/llama.cpp-${LLAMACPP_CONVERT_TAG}/conversion" \
            "/tmp/llama.cpp-${LLAMACPP_CONVERT_TAG}/gguf-py" /opt/llamacpp-convert/ \
    && rm -rf "/tmp/llama.cpp-${LLAMACPP_CONVERT_TAG}"
ENV LLMOPS_LORA_CONVERT_DIR=/opt/llamacpp-convert

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
