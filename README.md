# LLM-Router-Server-Dashboard
![範例圖片](assets/image0.png)
![範例圖片](assets/image1.png)
## 前端
1. 建立 container
```bash
cd frontend/docker
docker build -t LLM-Router-Server-Dashboard .
```
建立 image 後
```bash
docker-compose -f docker-compose.yaml up
```
進路 container
```bash
cd LLM-Router-Server-Dashboard/frontend
npm install
npm run dev
```
可以透過`vite.config.js`修改啟動`host`, `port`
```js
import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    host: '0.0.0.0', 
    port: 5111
  }
})
```

## 後端
**因為後端需要監聽 LLM 狀態(未暴露)，因此要跟 LLM-Router-Server 在同一個 container 內**
**因此原本 container 只需要開 8887，現在要多開一個讓 frontend fetch**
```yaml
version: "3.9"

services:
    llm-router:
        image: llm-router-server:latest
        container_name: llm-router-container
        command: tail -f /dev/null
        environment:
            - NVIDIA_VISIBLE_DEVICES=all
        volumes:
            - /etc/localtime:/etc/localtime:ro
            - /home/kuo/max:/app
        working_dir: /app
        ports:
            - "8887:8887"
            - "5000:5000"
        deploy:
            resources:
                reservations:    
                    devices:
                        - driver: nvidia
                          capabilities: [gpu]
        restart: unless-stopped
```
```bash
cd LLM-Router-Server-Dashboard/backend
uvicorn main:app --reload --host 0.0.0.0 --port 5000
```
要記得去`./LLM-Router-Server-Dashboard/frontend/.env.local`修改
```bash
VITE_API_BASE_URL=http://localhost:5000
```

## LLM-Router-Server
**最後只需要開啟路由 Server 就好**
**模型 config 會統一放在後端**
```bash
cd LLM-Router-Server-Dashboard/LLM-Router-Server
sh start_router_server.sh /app/backend/config.yaml
```