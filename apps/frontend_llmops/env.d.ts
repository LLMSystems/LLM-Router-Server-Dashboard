/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Dashboard Backend base URL (model lifecycle, resources, telemetry). */
  readonly VITE_API_BASE_URL: string
  /** LLM Router base URL (OpenAI-compatible inference + /metrics). */
  readonly VITE_ROUTER_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
