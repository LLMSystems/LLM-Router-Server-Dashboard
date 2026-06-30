# vLLMux Helm chart

Deploys the vLLMux control plane on Kubernetes — the HA backend (model lifecycle +
leader-elected scheduler), the stateless OpenAI/Anthropic **router** (horizontally
scalable), and an optional bundled **Postgres** shared store. Packages HA Phase 3:
shared-DB state, leader election, observed-state fan-out, cross-node placement,
router scale-out and routable vLLM binding.

> Requires a cluster with GPU nodes (NVIDIA device plugin) and a registry holding
> the `llmops-engine` image (build it from `deploy/Dockerfile` and push).

## Install

```bash
# simplest: one backend, one router, bundled Postgres
helm install vllmux ./deploy/helm/vllmux \
  -f ./deploy/helm/vllmux/values-collapsed.yaml \
  --set image.repository=YOUR_REGISTRY/llmops-engine \
  --set secrets.adminToken=$(openssl rand -hex 16) \
  --set postgres.password=$(openssl rand -hex 16) \
  --set secrets.hfToken=hf_xxx

# HA: warm-standby backend pair + 3 stateless routers + Ingress
helm install vllmux ./deploy/helm/vllmux \
  -f ./deploy/helm/vllmux/values-split.yaml \
  --set image.repository=YOUR_REGISTRY/llmops-engine \
  --set secrets.adminToken=$(openssl rand -hex 16) \
  --set postgres.password=$(openssl rand -hex 16) \
  --set ingress.host=vllmux.example.com
```

Put your fleet in `config.inline` (a `config.yaml`), or mount your own with
`config.existingConfigMap`. Models added at runtime through the dashboard live in
the shared DB overlay, so they survive pod restarts and are seen by every replica.

## What you get

| Component | Kind | Scaling |
|---|---|---|
| backend | StatefulSet | stable per-pod id; `replicas>1` = control-plane HA (warm standby) |
| router | Deployment | **stateless horizontal scale** — `replicas`/`workers` freely |
| postgres | StatefulSet | bundled shared store (or `postgres.enabled=false` + `externalDbUrl`) |

- **Probes**: backend `/healthz` (liveness), router `/health` + `/ready`
  (readiness gates the rolling update). 
- **Routable vLLM**: `backend.bindAll=true` binds spawned vLLMs to `0.0.0.0` and
  advertises the pod IP, so router pods reach them across the pod network.
- **Stable identity**: each backend pod's name is its `LLMOPS_INSTANCE_ID` (leader
  lease / node registry / assignments), avoiding the ephemeral `hostname:pid`.

## Scale the router (anytime, stateless)

```bash
kubectl scale deploy/vllmux-router --replicas=5
```

## Known limitation

`backend.replicas>1` is **control-plane HA (failover)**, not parallel GPU workers:
every replica serves the read API from the shared DB, but only the **leader** runs
the control loops and spawns models. True multi-GPU-node spread (each backend pod
running its own share of the fleet) needs per-node actuation, which is future work.
See `docs/ha-phase3-design_zh-CN.md`.

⚠️ `bindAll` exposes vLLM beyond localhost — only on a trusted cluster network.
