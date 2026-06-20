# 七種路由策略的實現說明

更新日期：2026-06-20 · 對應程式：[apps/router-server/src/llm_router/routing_strategies.py](../apps/router-server/src/llm_router/routing_strategies.py)

本文說明 router 內建的 **7 種負載平衡策略各自怎麼實作**。設計取捨與背景見
[routing-strategies.md](routing-strategies.md)(英文設計文件);vLLM 各類路由方法的
分類見 [vllm-model-serving-load-balancing.md](vllm-model-serving-load-balancing.md)。

---

## 0. 共用骨架

每個策略只回答一件事:**「在目前還能用的實例裡,挑哪一個?」**。所有「容錯」相關的機制
——進行中請求計數(inflight)、失效轉移(failover)、後端冷卻(cooldown)——都留在
proxy（[router.py](../apps/router-server/src/llm_router/router.py)）裡,由 7 種策略共用。
所以策略本身都很短、沒有副作用。

### 0.1 負載分數 `score_instance`

`least_load` / `least_inflight` / `p2c` / 兩個 affinity 的逃生判斷,全部建立在同一個
評分函式上(從舊版 selector 原樣抽出,保證 `least_load` 行為不變):

```python
def score_instance(app, model_key, instance) -> float:
    metric = app.state.metrics_cache.get(model_key, {}).get(instance_id)
    base = 0.0 if metric is None else metric.compute_load_score()
    base += get_inflight(app, model_key, instance_id) * INFLIGHT_WEIGHT      # = 5
    base += FAIL_OPEN_PENALTY if is_backend_in_cooldown(...) else 0.0        # = 1e9
    return base
```

- `compute_load_score()` 來自 [vllm_metrics_client.py](../apps/router-server/src/llm_router/vllm_metrics_client.py):
  `waiting×10 + running×3 + kv_cache_usage_perc×100`,資料由 metrics poller 每 ~1s 抓一次。
- **冷啟動**:某實例還沒被抓到 metrics(剛啟動 / 剛 reload)時 `metric is None`,當成 idle（0），
  靠 inflight penalty 先分散流量,而不是直接 500。
- **inflight penalty**:補上 ~1s scrape 空窗——本機正在處理的請求即時可見。
- **cooldown penalty**:失敗進冷卻的後端加 `1e9`,等於排到最後(fail-open,不是硬排除)。

`_least_by(score, candidates)` 是「回傳分數最小者、平手取第一個」的小工具(語意跟舊版
strict `<` 一致)。

### 0.2 選擇上下文 `SelectContext`

策略拿到的全部資訊:

```python
@dataclass
class SelectContext:
    app                       # 取 state.metrics_cache / backend_inflight / backend_health / rr_counters
    model_key: str
    candidates: list[dict]    # 這次請求還能用的實例(已扣掉 failover 試過的)
    all_instances: list[dict] # 整個群組的完整名單(affinity 雜湊用,集合穩定)
    session_key: str | None   # session_affinity 用
    prompt_prefix: str | None # prefix_affinity 用
```

### 0.3 分派器 `select_instance`

公開入口。先處理共通邊界,再把決定交給對應策略:

```python
instances = model_cfg["instances"]
if not instances: -> 500
candidates = [扣掉 exclude 的]
if not candidates: -> 503
if len(candidates) == 1: return candidates[0]      # 單實例直接回,不經策略
fn = STRATEGIES.get(name) or STRATEGIES["least_load"]  # 未知名稱 -> 退回預設
return fn(ctx) or candidates[0]
```

`exclude` 是「這次請求已經試過的實例 id」,讓 proxy 的 failover 不會重選到同一台死掉的。

---

## 1. `round_robin`（輪詢）

**訊號**:無。**做法**:每個群組一個游標,依序輪流。

```python
def _round_robin(ctx):
    counters = ctx.app.state.rr_counters          # 啟動時初始化的 dict
    n = counters.get(ctx.model_key, 0)
    counters[ctx.model_key] = n + 1
    return ctx.candidates[n % len(ctx.candidates)]
```

- 游標存在 `app.state.rr_counters`,key 是群組名,跨請求累加。
- 對 `candidates` 取模,所以 failover 縮小候選集時也不會越界。
- 完全不看負載,適合同質 GPU、請求差異不大、或當 baseline。

## 2. `random`（隨機）

**訊號**:無。**做法**:候選裡隨機挑一個。

```python
def _random(ctx):
    return random.choice(ctx.candidates)
```

最低決策成本、無狀態。大量短請求時,期望上也接近均分。

## 3. `least_inflight`（最少進行中）

**訊號**:只看本機 inflight + cooldown,**不看 metrics scrape**。

```python
def _least_inflight(ctx):
    return _least_by(lambda i: inflight_score(ctx.app, ctx.model_key, i), ctx.candidates)

# inflight_score = inflight×5 + (cooldown ? 1e9 : 0)
```

不依賴 ~1s 的 metrics,決策即時。適合請求耗時相近、不想被 scrape 延遲影響的場景。
是 `least_load` 的輕量子集。

## 4. `least_load`（最低負載,預設）

**訊號**:完整 `score_instance`(waiting/running/kv + inflight + cooldown)。

```python
def _least_load(ctx):
    return _least_by(lambda i: score_instance(ctx.app, ctx.model_key, i), ctx.candidates)
```

掃過所有候選挑分數最低者。這是 router 一直以來的預設行為,逐位元不變。適合請求長短差異
大、要平均各副本飽和度的情況。

## 5. `p2c`（Power-of-Two-Choices,二選一取優）

**訊號**:同 `least_load`,但**只隨機抽 2 個來比**。

```python
def _p2c(ctx):
    picks = random.sample(ctx.candidates, 2)   # 分派器已保證 len >= 2
    return _least_by(lambda i: score_instance(ctx.app, ctx.model_key, i), picks)
```

為什麼不直接全域挑最低?因為在 ~1s 的 scrape 盲區 + 突發流量下,大家會同時看到同一個
「目前最低分」的副本,一窩蜂衝過去造成 herd。隨機抽 2 個比較,能在幾乎不犧牲品質的前提下
打散這種震盪。已用 inflight penalty 部分緩解時,這是更進一步的抗震版。

## 6. `session_affinity`（會話黏性)

**訊號**:`session_key`(來源見 §8)。**做法**:把 key 一致性雜湊到一台「home」實例黏住,
但保留「負載逃生門檻」。

```python
def _affinity(ctx, key):
    if not key:
        return _least_load(ctx)                       # 沒 key -> 退回 least_load

    ring = sorted(ctx.all_instances, key=lambda i: i["id"])   # 穩定排序
    home = ring[ _hash_key(key) % len(ring) ]                 # 同 key -> 永遠同一台

    best = _least_by(score_instance, ctx.candidates)
    if home 還在候選集 and home 不在 cooldown:
        if score(home) <= score(best) + AFFINITY_LOAD_MARGIN:  # 門檻內
            return home                                        # 黏住
    return best                                                # 否則散開 = least_load
```

關鍵設計:

- **一致性雜湊用 `hashlib.sha1`**,不是內建 `hash()`——內建 hash 每個行程有隨機 salt,
  會讓同一個 key 在不同 worker / 重啟後黏到不同台。sha1 跨行程穩定。
- **雜湊範圍是 `all_instances`(完整名單)**,不是會因 failover 縮小的 `candidates`,
  這樣同一 key 的 home 才不會因為別台暫時失效就跳掉。
- **逃生門檻 `AFFINITY_LOAD_MARGIN`**(預設 50,環境變數 `LLMOPS_AFFINITY_LOAD_MARGIN`
  可調):home 的負載分數只要不超過「最閒的候選 + 門檻」就繼續黏;超過了就放棄 cache 重用、
  改散開,避免熱門 session 把單一副本壓垮。
- home 若**不在候選集**(被 failover 排除)或**正在 cooldown**,直接走 `least_load`。
- **沒有 key 時退回 `least_load`**——所以開啟黏性「永遠不會比預設差」,只是多了在有 key
  時的黏性。

適合多輪對話、playground —— 同一段對話回同一台,提升 KV cache 命中、降低重算 prefill。

## 7. `prefix_affinity`（前綴黏性)

**訊號**:`prompt_prefix`。**做法**:跟 `session_affinity` 完全共用同一個 `_affinity`
框架,只是把 key 換成 prompt 前綴的雜湊。

```python
def _prefix_affinity(ctx):
    return _affinity(ctx, ctx.prompt_prefix)
```

前綴由 proxy 擷取(§8),所以**不需要客戶端配合傳任何 id**。對「固定 system prompt、
RAG 模板、few-shot 模板」這種高前綴重複率的工作負載,能把同模板的請求黏到同一台、吃到
prefix cache。

---

## 8. Key 怎麼來(proxy 側擷取)

`session_affinity` / `prefix_affinity` 需要的 key 由 proxy 每次請求算一次(其他策略不算,
省成本),程式在 [router.py](../apps/router-server/src/llm_router/router.py):

- **session_key**:先取 HTTP header `X-Session-Id`;沒有則取 OpenAI body 的 `user` 欄位。
  **兩者都沒有 → key 為 None → 該策略退回 `least_load`(等於沒黏)。**
- **prompt_prefix**:聊天取前幾則訊息的 `role:content`、completions 取 `prompt`,截到
  512 字元(有界,不拖慢熱路徑)。

> 實務提醒:要讓 `session_affinity` 真的黏,客戶端對同一對話要帶同一個 `X-Session-Id`
> 或 `user`。playground / 前端聊天若沒帶,行為就跟 `least_load` 一樣。

---

## 9. 註冊表與選擇方式

```python
STRATEGIES = {
    "round_robin": _round_robin,   "random": _random,
    "least_inflight": _least_inflight, "least_load": _least_load,
    "p2c": _p2c,
    "session_affinity": _session_affinity, "prefix_affinity": _prefix_affinity,
}
```

選擇優先序(先命中者贏,每次請求重算,`/reload` 即時生效):

1. **每群組**:該群組 `config.yaml` 的 `model_config.routing_strategy`(走 schema 的
   `extra="allow"`,免改 schema)。
2. **全域**:環境變數 `LLMOPS_ROUTING_STRATEGY`(啟動時讀進 `app.state.routing_strategy`,
   前端「流量」頁下拉可即時熱切換)。
3. **預設**:`least_load`。

未知名稱會記 warning 並退回 `least_load`,不會讓請求失敗。

## 10. 可調參數總覽

| 參數 | 位置 | 預設 | 作用 |
|---|---|---|---|
| `INFLIGHT_WEIGHT` | backend_runtime_state.py | 5 | inflight 在分數裡的權重 |
| `FAIL_OPEN_PENALTY` | backend_runtime_state.py | 1e9 | cooldown 後端的排序懲罰 |
| `waiting/running/kv 權重` | vllm_metrics_client.py | 10/3/100 | 負載分數的組成 |
| `LLMOPS_AFFINITY_LOAD_MARGIN` | 環境變數 | 50 | affinity 的負載逃生門檻 |
| `LLMOPS_ROUTING_STRATEGY` | 環境變數 | least_load | 全域預設策略 |
| `model_config.routing_strategy` | config.yaml | （無） | 單一群組覆寫 |
