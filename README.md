# GPUREDIS - 分布式 GPU 任务调度与负载均衡系统

GPUREDIS 是一个轻量级、高性能的分布式 GPU 任务调度系统，基于 FastAPI 和 Redis 构建。它能够自动监控多台机器上的 GPU 资源，并根据显存占用情况自动分发任务（如 AI 推理、视频转码等），支持同步和异步轮询模式。

## 核心特性

- **🚀 智能负载均衡**：根据实时显存占用、权重和任务类型，自动选择最优显卡，解决 OOM 问题。
- **💾 本地持久化**：配置信息（显卡、渠道）和任务记录自动保存到本地 `data/` 目录，即便 Redis 重启数据也不丢失。
- **🐳 一体化部署**：支持 Docker 一键部署，镜像内置 Redis 服务，零配置上手。
- **🕒 异步支持**：支持同步请求和异步轮询模式，完美适配长耗时 AI 任务（如 ComfyUI、Whisper）。
- **📊 实时监控**：响应式管理后台，可视化管理显卡状态和任务队列。

## 快速开始

### 1. 使用 Docker 镜像直接部署 (推荐)

您可以直接拉取我在 GitHub Packages 构建好的镜像进行部署：

```bash
# 1. 拉取镜像
docker pull ghcr.io/zerohiz/newgpu:latest

# 2. 运行容器 (映射 8000 端口，并挂载数据目录)
docker run -d \
  --name gpu-redis \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --restart always \
  ghcr.io/zerohiz/newgpu:latest
```

访问 `http://服务器IP:8000` 即可进入管理后台。

### 2. 使用 Docker Compose 一键部署

1. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

2. **启动 Redis**：
   确保本地已运行 Redis 服务（默认端口 6379）。

3. **运行应用**：
   ```bash
   uvicorn api.main:app --host 0.0.0.0 --port 8000
   ```

## 目录结构

- `api/`：FastAPI 接口与路由逻辑。
- `core/`：核心模块（Redis 客户端、配置加载、持久化层）。
- `worker/`：GPU Agent 逻辑，负责监控资源和执行任务转发。
- `web/`：管理后台前端模板（HTML/JS）。
- `data/`：本地 JSON 存储目录（显卡、渠道信息持久化）。
- `config.yaml`：Redis 与服务器基础配置。

## API 调用示例

### 1. 提交普通 JSON 任务
```bash
curl -X POST "http://localhost:8000/api/tasks" \
     -H "Content-Type: application/json" \
     -d '{
       "service_type": "whisper",
       "payload": {"audio_url": "http://example.com/test.mp3"}
     }'
```

### 2. 提交包含文件上传的穿透中转任务 (以 VoxCPM2 / ComfyUI 等为例)
当您的上游 AI 推理接口需要通过 **Multipart 表单**上传文件，且不同的服务所需的表单字段名（Key）不同时（例如 Whisper 表单键为 `file`，语音合成表单键为 `audio`，图片生成表单键为 `image`），调度系统提供了一套**纯粹无侵入的单键穿透传输设计**。

您只需在 `payload` 载荷中传入需要上传的文件路径（支持网络 HTTP 链接或本地路径），并通过 **`_file_path_key`** 指定文件所在的键名：

```bash
curl -X POST "http://localhost:8000/api/tasks" \
     -H "Content-Type: application/json" \
     -d '{
       "service_type": "voxcpm",
       "payload": {
         "audio": "http://网关IP:8000/uploads/input_ref.wav",
         "model": "openbmb/VoxCPM2",
         "_file_path_key": "audio"
       }
     }'
```

**💡 工作流原理：**
1. **远程自动下载**：Agent 检测到 `payload` 中有 `_file_path_key` 为 `"audio"`。若对应的值是 HTTP/HTTPS 远程链接，Agent 将全自动将其安全流式下载并缓存在节点本地。
2. **表单键名穿透**：Agent 构造 Multipart 转发给本地 AI 服务时，**上传的文件字段名（Key）将自动穿透为 `"audio"`**，同时系统级元参数 `_file_path_key` 会被自动从 Form 字段中抹除，保持上游接口百分之百的纯净和兼容性。
3. **二进制流响应智能落地**：若上游服务返回了音频或图像等直接的二进制流响应（HTTP 200，例如直接返回 WAV 音频），Agent 也会自动检测其 `Content-Type`（以 `audio/` 开头），绕过可能引发崩溃的 JSON 解析，智能将音频落地保存到网关的静态服务目录 `data/uploads/tts_{task_id}.wav`，并将生成的本地静态下载 URL 包入任务的 `result` 传回：
   ```json
   {
     "status": "completed",
     "result": {
       "type": "audio",
       "filename": "tts_xxxx.wav",
       "url": "/uploads/tts_xxxx.wav"
     }
   }
   ```

## 故障排除
- **UI 刷新问题**：如果修改配置后前端未生效，请按下 `Ctrl + F5` 强制刷新浏览器缓存。
- **显存上报**：Agent 默认每 5 秒上报一次显存，若部署在非本地机器，请确保 API 地址可达。

## License
MIT License
