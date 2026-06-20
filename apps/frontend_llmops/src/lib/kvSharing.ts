// Cross-instance KV-cache sharing: a single toggle in the model editor writes
// this OffloadingConnector preset onto the group's model_config, so every
// instance of the group offloads/loads KV blocks to a shared store (/kv_cache)
// and can reuse each other's prefixes. Backend launcher emits it as
// --kv-transfer-config and forces PYTHONHASHSEED=0.
// See docs/vllm-kv-cache-cross-instance-design.md.
import type { KvTransferConfig } from '@/types/api'

/** The preset written when KV sharing is enabled. cpu_bytes_to_use is sized
 *  conservatively for small boxes; tune it in config.yaml on bigger machines. */
export const KV_SHARE_PRESET: KvTransferConfig = {
  kv_connector: 'OffloadingConnector',
  kv_role: 'kv_both',
  kv_connector_extra_config: {
    spec_name: 'TieringOffloadingSpec',
    cpu_bytes_to_use: 268435456, // 256MB CPU L1 tier
    block_size: 16,
    eviction_policy: 'lru',
    secondary_tiers: [
      { type: 'fs', root_dir: '/kv_cache', n_read_threads: 8, n_write_threads: 4 },
    ],
  },
}

/** True when a group's model_config enables cross-instance KV sharing. */
export function isKvShared(
  settings: Record<string, unknown> | null | undefined,
): boolean {
  const c = settings?.kv_transfer_config as KvTransferConfig | null | undefined
  return !!c && typeof c === 'object' && !!c.kv_connector
}
