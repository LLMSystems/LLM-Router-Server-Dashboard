<div align="center">

# LLM-Router-Server-Dashboard
**一站式 LLM 模型管理與監控平台**

</div>

---

## 專案簡介

**LLM-Router-Server-Dashboard** 是一個針對大型語言模型（LLM）部署與管理的解決方案，提供直觀的 Web 界面來管理、監控和操作多個 LLM 模型實例。

本專案結合路由伺服器（LLM-Router-Server）與易用的管理界面，讓您能夠：
- **視覺化管理**：透過 Web 界面輕鬆管理多個模型
- **動態啟停**：即時啟動、停止模型，無需重啟服務
- **即時監控**：監控模型狀態、GPU 使用率、系統資訊
- **配置管理**：透過 YAML 配置文件靈活管理模型參數

---

## 功能特色

### 核心功能

- **多模型管理**
  - 支援同時管理多個 LLM 模型（基於 vLLM）
  - 支援 Embedding 模型和 Reranking 模型
  - 獨立的模型生命週期管理（啟動/停止）

- **視覺化控制台**
  - 實時顯示模型運行狀態
  - GPU 資源監控
  - 系統資源使用率統計
  - 模型配置查看與編輯

- **資源管理**
  - GPU 設備分配與管理
  - 記憶體使用率監控
  - 多卡並行支援（Tensor Parallel）

---

## 環境需求

### 硬體需求
- **GPU**: NVIDIA GPU（建議 CUDA 12.1+）
- **記憶體**: 16GB+ RAM（依模型大小而定）
- **硬碟**: 50GB+ 可用空間
---

## 快速開始

### 前端部署

#### 1. 使用 Docker 建立前端容器

```bash
cd frontend/docker
docker build -t llm-router-server-dashboard .
docker-compose -f docker-compose.yaml up -d
```

#### 2. 本地開發模式

```bash
cd frontend
npm install
npm run dev
```

#### 3. 生產環境建置

```bash
cd frontend
npm install
npm run build
```

#### 4. 配置前端 API 端點

編輯 `frontend/.env.local`：
```env
VITE_API_BASE_URL=http://localhost:5000
VITE_MODEL_CONTROL_PASSWORD=123
```

#### 5. 自訂服務器配置

編輯 `frontend/vite.config.js`：
```javascript
export default defineConfig({
  server: {
    host: '0.0.0.0',  // 允許外部訪問
    port: 5111        // 自訂端口
  }
})
```

### 後端部署

**重要提醒**：後端需要監聽 LLM 模型狀態（進程管理），因此必須與 LLM-Router-Server 在同一個容器內運行。

#### 1. 建立容器

```bash
cd LLM-Router-Server/docker
docker build -t cuda121-cudnn8-python311 .
docker-compose -f docker-compose.yaml up -d
```

**確保 docker-compose.yaml 中暴露了必要的端口**：
- `8887`: LLM-Router-Server API
- `5000`: Dashboard 後端 API
- 其他模型端口（如 8002, 8003 等）

#### 2. 在容器內啟動後端

```bash
# 進入容器
docker exec -it <container_id> bash

# 啟動後端
cd /app/backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

### LLM-Router-Server 部署

#### 1. 在容器內啟動路由服務器

```bash
cd /app/LLM-Router-Server
pip install -r requirements.txt
sh start_router_server.sh /app/backend/config.yaml
```

**注意**：配置文件統一使用 `/app/backend/config.yaml`，確保前後端配置一致。

#### 2. 驗證服務狀態

```bash
# 檢查路由服務器
curl http://localhost:8887/health

# 檢查後端 API
curl http://localhost:5000/api/status
```

---

## 配置說明

### config.yaml 結構

配置文件位於 `backend/config.yaml`，控制所有模型的啟動參數。

```yaml
# 路由服務器配置
server:
  host: "0.0.0.0"
  port: 8887
  uvicorn_log_level: "info"

# LLM 模型配置
LLM_engines:
  Qwen3-0.6B:                          # 模型名稱（唯一識別符）
    model_tag: "Qwen/Qwen3-0.6B"       # HuggingFace 模型路徑或本地路徑
    host: "localhost"                   # 服務監聽地址
    port: 8002                          # 服務端口
    dtype: "float16"                    # 數據類型（float16/bfloat16/auto）
    max_model_len: 1000                 # 最大序列長度
    gpu_memory_utilization: 0.6         # GPU 記憶體使用率（0.0-1.0）
    tensor_parallel_size: 1             # Tensor 並行大小（多卡）
    cuda_device: 0                      # 指定 GPU 設備

# Embedding 服務器配置（可選）
embedding_server:
  host: "localhost"
  port: 8005
  cuda_device: 1
  
  embedding_models:
    m3e-base:
      model_name: "moka-ai/m3e-base"
      model_path: "./models/embedding_engine/model/embedding_model/m3e-base-model"
      tokenizer_path: "./models/embedding_engine/model/embedding_model/m3e-base-tokenizer"
      max_length: 512
      use_gpu: true
      use_float16: true
  
  reranking_models:
    bge-reranker-large:
      model_name: "BAAI/bge-reranker-large"
      model_path: "./models/embedding_engine/model/reranking_model/bge-reranker-large-model"
      tokenizer_path: "./models/embedding_engine/model/reranking_model/bge-reranker-large-tokenizer"
      max_length: 512
      use_gpu: true
      use_float16: true
```

### 關鍵參數說明

| 參數 | 說明 | 建議值 |
|------|------|--------|
| `gpu_memory_utilization` | GPU 記憶體使用比例 | 0.6-0.9 |
| `max_model_len` | 最大上下文長度 | 依模型能力 |
| `tensor_parallel_size` | 多 GPU 並行數 | GPU 數量 |
| `dtype` | 推理精度 | float16（速度快） / bfloat16（更穩定） |
| `cuda_device` | GPU 設備編號 | 0, 1, 2... |

---

## API 文檔

### 後端管理 API (Port 5000)

#### 1. 配置管理

**取得完整配置**
```http
GET /api/config
```

**更新配置**
```http
PUT /api/config
Content-Type: application/json

{
  "server": {...},
  "LLM_engines": {...}
}
```

#### 2. 模型狀態

**取得所有模型狀態**
```http
GET /api/status
```

回應範例：
```json
{
  "Qwen3-0.6B": {
    "status": "running",
    "port": 8002,
    "pid": 12345,
    "gpu": 0
  }
}
```

#### 3. LLM 管理

**啟動 LLM 模型**
```http
POST /api/llm/start/{model_name}
```

**停止 LLM 模型**
```http
POST /api/llm/stop/{model_name}
```

#### 4. 系統信息

**取得 GPU 資訊**
```http
GET /api/system/gpu
```

**取得系統資源**
```http
GET /api/system/resources
```

### LLM-Router-Server API

完整兼容 OpenAI API 格式。

**聊天完成（Chat Completions）**
```http
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "Qwen3-0.6B",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true
}
```

**文本完成（Completions）**
```http
POST /v1/completions
Content-Type: application/json

{
  "model": "Qwen3-0.6B",
  "prompt": "Once upon a time",
  "max_tokens": 100
}
```

**向量嵌入（Embeddings）**
```http
POST /v1/embeddings
Content-Type: application/json

{
  "model": "m3e-base",
  "input": "Hello world"
}
```

---

## 截圖展示

### 主控台界面
![主控台](assets/image0.png)

### 模型管理
![模型管理](assets/image1.png)

---

### Q4: 為什麼不能同時啟動多個模型？

**設計限制**：當前版本必須逐一啟動模型，以確保：
- GPU 資源正確分配
- 避免記憶體溢出
- 進程管理穩定性

未來版本將優化並行啟動支援。