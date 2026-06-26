# vLLM 最新版 Server 啟動寫法整理

更新日期：2026-06-26

本文整理的是 vLLM 官方 stable 文件目前對 `embedding model`、`reranker model`、`pooling model` 的 server 啟動方式，重點放在「現在建議怎麼啟動」，不展開 client 呼叫細節。

## 適用版本重點

這份整理以 vLLM 官方 stable 文件為準。根據文件，`v0.21+` 有幾個和 pooling 很相關的變化：

- `score` task 已移除，不再建議用它作為 task 名稱。
- 如果模型的預設 pooling task 不是你要的，應改用 `--pooler-config.task <task>` 指定。
- `pooling multitask support` 已移除，不要再假設同一個 server 會自動替你切換成你心裡想的 pooling task。

## 一句話先講結論

- `embedding model`：直接 `vllm serve <embedding-model>`
- `reranker model`：直接 `vllm serve <reranker-model>`
- 要明確用 pooling 模式：加上 `--runner pooling`
- 非原生 pooling / classification 架構，需要時用 `--convert embed` 或 `--convert classify`
- 在 `v0.21+`，若要強制指定 pooling task，用 `--pooler-config.task ...`，不要再用舊觀念的 `score task`

## 1. Embedding Model 的最新版啟動方式

如果模型本身就是 embedding model，最新版最直接的寫法是：

```bash
vllm serve intfloat/e5-small
```

這種啟動方式對應的主要 API 是：

- `/v1/embeddings`
- `/v2/embed`
- `/pooling`

如果你希望把它寫得更明確，尤其是在你想清楚表達這是一個 pooling 類模型時，可以寫成：

```bash
vllm serve intfloat/e5-small --runner pooling
```

官方文件也提到，多數情況下不一定要手動加 `--runner pooling`，因為 `--runner auto` 通常可以自動判斷。

## 2. Reranker Model 的最新版啟動方式

如果模型本身就是 cross-encoder reranker，最直接的啟動方式通常也是：

```bash
vllm serve cross-encoder/ms-marco-MiniLM-L-6-v2
```

這類模型常用的 server API 是：

- `/score`
- `/v1/score`
- `/rerank`
- `/v1/rerank`
- `/v2/rerank`

要注意的是，最新版文件裡雖然還保留 `/score` API 與 `/rerank` API，但 `score` 已不再是建議拿來設定的 task 名稱。從 `v0.21+` 開始，如果你需要指定任務概念，應以 `classify` 為主。

## 3. Pooling 類模型的通用最新版寫法

如果你要的是一個明確、可讀性高、較不容易和一般生成模型混淆的 server 啟動方式，最新版推薦可以這樣寫：

```bash
vllm serve <model> --runner pooling
```

例如：

```bash
vllm serve BAAI/bge-m3 --runner pooling
```

這種寫法的意思是直接要求 vLLM 以 pooling runner 來啟動該模型。

## 4. 模型不是原生 pooling 模型時的最新版寫法

如果模型不是原生 pooling model，但你想把它轉成 embedding 或 classification 來提供服務，最新版寫法是用 `--convert`：

轉成 embedding：

```bash
vllm serve <model> --runner pooling --convert embed
```

轉成 classification：

```bash
vllm serve <model> --runner pooling --convert classify
```

官方文件說明的重點是：

- `--convert embed`：把模型轉成 embedding 類使用方式
- `--convert classify`：把模型轉成 sequence classification 類使用方式

這在某些 reranker、分類模型、或非原生 pooling 架構上很有用。

## 5. v0.21+ 應該怎麼指定 pooling task

這是最新版最重要的地方之一。

如果你要指定該 server 的 pooling task，應使用：

```bash
vllm serve <model> --runner pooling --pooler-config.task embed
```

或：

```bash
vllm serve <model> --runner pooling --pooler-config.task classify
```

也支援 token 級任務：

```bash
vllm serve <model> --runner pooling --pooler-config.task token_embed
vllm serve <model> --runner pooling --pooler-config.task token_classify
```

最新版語意可這樣理解：

- `embed`：輸出 sequence-level embedding
- `classify`：輸出 sequence-level classification 結果
- `token_embed`：輸出 token-level embeddings
- `token_classify`：輸出 token-level classification 結果

## 6. 最新版不建議再怎麼寫

以下是現在不建議再沿用的觀念：

- 不要再把 `score` 當成可設定的 task 名稱
- 不要假設 pooling server 會自動做你想要的 task 切換
- 不要在需要明確 task 的情況下只靠模型名稱猜測

在 `v0.21+`，如果預設 task 不是你要的，最穩定的方式就是明確加上：

```bash
--pooler-config.task <task>
```

## 7. 官方文件中特別給出的 reranker 啟動例子

### BAAI bge-reranker-v2-gemma

```bash
vllm serve BAAI/bge-reranker-v2-gemma --hf_overrides '{"architectures": ["GemmaForSequenceClassification"],"classifier_from_token": ["Yes"],"method": "no_post_processing"}'
```

### mixedbread mxbai-rerank-base-v2

```bash
vllm serve mixedbread-ai/mxbai-rerank-base-v2 --hf_overrides '{"architectures": ["Qwen2ForSequenceClassification"],"classifier_from_token": ["0", "1"], "method": "from_2_way_softmax"}'
```

### Qwen3-Reranker

```bash
vllm serve Qwen/Qwen3-Reranker-0.6B --hf_overrides '{"architectures": ["Qwen3ForSequenceClassification"],"classifier_from_token": ["no", "yes"],"is_original_qwen3_reranker": true}'
```

這幾個例子代表一件事：有些官方原始 reranker checkpoint 不是直接用標準 sequence-classification 形式提供，因此需要 `--hf_overrides` 才能用 vLLM 正確掛成 reranker server。

## 8. 實務上建議的最新版模板

### 模板 A：原生 embedding model

```bash
vllm serve <embedding-model>
```

### 模板 B：想明確表示這是 pooling server

```bash
vllm serve <model> --runner pooling
```

### 模板 C：把模型強制當 embedding 用

```bash
vllm serve <model> --runner pooling --convert embed --pooler-config.task embed
```

### 模板 D：把模型強制當 reranker / classify 用

```bash
vllm serve <model> --runner pooling --convert classify --pooler-config.task classify
```

### 模板 E：原始官方 reranker checkpoint 需要 overrides

```bash
vllm serve <reranker-model> --hf_overrides '<json>'
```

## 9. 最推薦的簡化記法

如果你只是想記最新版規則，可以直接記這組：

```bash
# embedding
vllm serve <embedding-model>

# reranker
vllm serve <reranker-model>

# 明確 pooling
vllm serve <model> --runner pooling

# 非原生模型轉 embedding
vllm serve <model> --runner pooling --convert embed --pooler-config.task embed

# 非原生模型轉 reranker / classify
vllm serve <model> --runner pooling --convert classify --pooler-config.task classify
```

## 10. 補充：endpoint 對應關係

最新版文件中的 server endpoint 可簡單對照如下：

- embedding：`/v1/embeddings`、`/v2/embed`
- classification：`/classify`
- reranker / scoring：`/score`、`/v1/score`、`/rerank`、`/v1/rerank`、`/v2/rerank`
- generic pooling：`/pooling`

## 11. 建議結論

如果你現在要寫「最新版 vLLM server 啟動方式」，最穩妥的寫法是：

1. 原生 embedding / reranker 模型先直接 `vllm serve <model>`
2. 需要明確聲明 pooling 時加 `--runner pooling`
3. 需要改變模型用途時用 `--convert embed` 或 `--convert classify`
4. 在 `v0.21+` 需要指定任務時，統一用 `--pooler-config.task ...`
5. 對某些官方原始 reranker checkpoint，要補 `--hf_overrides`

## 參考資料

- vLLM Online Serving
  - https://docs.vllm.ai/en/stable/serving/online_serving/
- vLLM Pooling Models
  - https://docs.vllm.ai/en/stable/models/pooling_models/
- vLLM Classification Usages
  - https://docs.vllm.ai/en/stable/models/pooling_models/classify/
- vLLM Scoring Usages
  - https://docs.vllm.ai/en/latest/models/pooling_models/scoring/
- vLLM Specific Model Examples
  - https://docs.vllm.ai/en/latest/models/pooling_models/specific_models/
