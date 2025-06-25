<template>
  <div class="container">
    <h1 class="title">LLM Router Server 模型啟動控制面板</h1>
    <el-card v-if="server.host" class="system-info-card" shadow="hover" style="max-width: 600px;">
      <template #header>
        <strong>系統設定</strong>
      </template>

      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="Host">{{ server.host }}</el-descriptions-item>
        <el-descriptions-item label="Port">{{ server.port }}</el-descriptions-item>
        <el-descriptions-item label="Log Level">{{ server.uvicorn_log_level }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
      <el-card v-if="resources" class="resource-info-card" shadow="hover">
        <template #header>
          <strong>系統資源監控</strong>
        </template>

        <!-- CPU 使用率 -->
        <div class="mb-4">
          <el-divider content-position="left">CPU</el-divider>
          <p>
            CPU 使用率：
            <el-progress
              :percentage="resources.cpu"
              :text-inside="true"
              stroke-width="20"
              status="success"
            />
          </p>
        </div>

        <!-- 記憶體使用 -->
        <div class="mb-4">
          <el-divider content-position="left">記憶體</el-divider>
          <p>
            使用量：
            <el-tag type="info">
              {{ formatGB(resources.memory.used) }} / {{ formatGB(resources.memory.total) }} GB
            </el-tag>
            <el-progress
              :percentage="resources.memory.percent"
              :text-inside="true"
              stroke-width="20"
              status="warning"
            />
          </p>
        </div>

        <!-- GPU 狀態 -->
        <div v-if="resources.gpus.length > 0">
          <el-divider content-position="left">GPU 狀態</el-divider>
          <el-collapse>
            <el-collapse-item
              v-for="gpu in resources.gpus"
              :key="gpu.index"
              :title="`GPU ${gpu.index} - ${gpu.name}`"
            >
              <p>使用率：{{ gpu.gpu_util }}%</p>
              <p>
                記憶體使用：{{ gpu.memory_used }} / {{ gpu.memory_total }} MiB
                <el-progress
                  :percentage="(gpu.memory_used / gpu.memory_total) * 100"
                  :text-inside="true"
                  stroke-width="20"
                  status="exception"
                />
              </p>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-card>
    <!-- GPU 占用程序清單 -->
    <div v-if="gpuProcesses.length > 0" class="mt-4">
      <el-divider content-position="left">GPU 占用程序</el-divider>
      <el-table :data="gpuProcesses" stripe style="width: 100%" size="small">
        <el-table-column prop="pid" label="PID" width="80" />
        <el-table-column prop="username" label="使用者" width="100" />
        <el-table-column prop="nvidia_smi_name" label="nvidia-smi 名稱" width="150" />
        <el-table-column prop="name" label="處理程序名稱" width="120" />
        <el-table-column prop="used_memory_mib" label="顯存 (GB)" width="120">
          <template #default="scope">
            {{ (scope.row.used_memory_mib / 1024).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="指令行">
          <template #default="scope">
          <el-tooltip 
            v-if="Array.isArray(scope.row.cmdline)" 
            :content="scope.row.cmdline.join(' ')" 
            placement="top-start"
          >
            <span 
              style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; max-width: 300px;"
            >
              {{ scope.row.cmdline.join(' ').slice(0, 60) }}...
            </span>
          </el-tooltip>
          <span v-else>
            無命令列資訊
          </span>
        </template>
        </el-table-column>
      </el-table>
    </div>


    <ModelGroup
      v-if="llmModels.length > 0"
      title="LLM 模型"
      :models="llmModels"
      @start="startLLM"
      @stop="stopLLM"
    />

    <ModelGroup
      v-if="embeddingServer.name"
      title="Embedding & reranking 模型"
      :models="[embeddingServer]"
      @start="startEmbedding"
      @stop="stopEmbedding"
    />

  </div>
</template>

<script setup>
import ModelGroup from '../components/ModelGroup.vue'
import { ref, onMounted } from 'vue'
// 頁面切換或隱藏時暫停輪詢（省資源）

const server = ref({})
const llmModels = ref([])
const embeddingServer = ref({})
const resources = ref(null)
const gpuProcesses = ref([])

async function pollGpuProcesses () {
  const fetchProcesses = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/gpu/processes`)
      const data = await res.json()
      gpuProcesses.value = Array.isArray(data) ? data : []
    } catch (err) {
      console.error('無法取得 GPU 占用程序資訊', err)
    }
  }
  await fetchProcesses()
  setInterval(fetchProcesses, 5000)
}


function formatGB(bytes) {
  return (bytes / (1024 ** 3)).toFixed(1)
}

onMounted(async () => {
  const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/config`)
  const config = await res.json()

  server.value = config.server

  llmModels.value = Object.entries(config.LLM_engines).map(([name, cfg]) => ({
    name,
    port: cfg.port,
    cuda_device: cfg.cuda_device,
    max_model_len: cfg.max_model_len,
    gpu_memory_utilization: cfg.gpu_memory_utilization,
    tool_parser: cfg['tool_parser'] || cfg['reasoning_parser'] || 'unknown',
    status: '未啟動'
  }))

  embeddingServer.value = {
    name: 'Embedding & reranking Server',
    port: config.embedding_server.port,
    cuda_device: config.embedding_server.cuda_device,
    embedding_models: config.embedding_server.embedding_models,
    reranking_models: config.embedding_server.reranking_models,
    status: '未啟動'
  }


  pollModelStatus()
  pollResources()
  pollGpuProcesses()
})

function pollResources() {
  const fetchResources = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/resources`)
      resources.value = await res.json()
    } catch (err) {
      console.warn('無法取得系統資源資訊', err)
    }
  }
  fetchResources()
  setInterval(fetchResources, 1000)
}

async function pollModelStatus() {
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/status/all`)
      const data = await res.json()
      const statusMap = Object.fromEntries(data.models.map(m => [m.name, m.status]))

      llmModels.value.forEach(model => {
        if (statusMap[model.name]) {
          model.status = statusMap[model.name]
        }
      })
      if (statusMap["Embedding & reranking Server"]) {
        embeddingServer.value.status = statusMap["Embedding & reranking Server"]
      }
    } catch (error) {
      console.error('Error fetching model status:', error)
    }
  }
  await fetchStatus()
  setInterval(fetchStatus, 5000)
}

const startLLM = async (name) => {
  const model = llmModels.value.find(m => m.name === name)
  if (!model) return
  model.status = '啟動中'

  try {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/llm/start/${name}`, {
      method: 'POST',
    })
    const data = await res.json()
    model.status = data.status || '啟動中'
  } catch (err) {
    model.status = '啟動失敗'
    console.error('啟動失敗', err)
  }
}



const stopLLM = async (name) => {
  const model = llmModels.value.find(m => m.name === name)
  if (!model) return
  model.status = '關閉中'

  try {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/llm/stop/${name}`, {
      method: 'POST'
    })
    const data = await res.json()
    model.status = data.status || '未啟動'
  } catch (err) {
    model.status = '未知錯誤'
    console.error('關閉失敗', err)
  }
}

const startEmbedding = async () => {
  embeddingServer.value.status = '啟動中'

  try {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/embedding/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: embeddingServer.value.name })
    })
    const data = await res.json()
    embeddingServer.value.status = data.status || '啟動中'
  } catch (err) {
    embeddingServer.value.status = '啟動失敗'
    console.error('啟動失敗', err)
  }
}

const stopEmbedding = async () => {
  embeddingServer.value.status = '關閉中'

  try {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/embedding/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: "embeddingServer.value.name" })
    })
    const data = await res.json()
    embeddingServer.value.status = data.status || '未啟動'
  } catch (err) {
    embeddingServer.value.status = '未知錯誤'
    console.error('關閉失敗', err)
  }
}

</script>

<style scoped>
.system-info-card {
  margin-bottom: 1rem;
}
.resource-info-card {
  width: 100%;
  max-width: 600px;
  margin-bottom: 1.5rem;
}


.mb-4 {
  margin-bottom: 1rem;
}

.container {
  margin: 0 auto;
  padding: 2rem;
}
.title {
  font-size: 2rem;
  margin-bottom: 1rem;
  text-align: center;
}
.section-title {
  font-size: 1.5rem;
  margin-top: 2rem;
  margin-bottom: 1rem;
}
.card {
  width: 300px;
  border-radius: 10px;
  padding: 1rem;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid #eee;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.card-header {
  font-size: 1.2rem;
  font-weight: bold;
  margin-bottom: 0.5rem;
}

.card-body p {
  margin: 4px 0;
}

</style>
