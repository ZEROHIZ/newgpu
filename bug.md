# GPUREDIS 经验总结与 BUG 记录

## 2026-05-16
### BUG: Jinja2 TemplateResponse `TypeError: unhashable type: 'dict'`
- **现象**：访问 `/` 首页时，FastAPI 报错 `TypeError: unhashable type: 'dict'`，堆栈指向 `jinja2\environment.py` 和 `starlette\templating.py`。
- **原因**：在较新版本的 FastAPI/Starlette 中，`TemplateResponse` 的调用参数顺序或方式发生了变化，或者环境中安装的 Jinja2/Starlette 版本不匹配。
- **解决方案**：将 `return templates.TemplateResponse("index.html", {"request": request})` 显式改为使用关键字参数：`return templates.TemplateResponse(request=request, name="index.html", context={})`。这是新版 Starlette 推荐的写法。
- **预防**：在使用模板渲染时，尽量使用关键字参数以增强版本兼容性。

### BUG: 添加显卡/渠道功能失效 & 404 错误
- **现象**：用户反馈“添加渠道和显卡用不了”。浏览器控制台报错：`GET /css/modules/laydate/default/laydate.css` 等 404。后台日志显示有 Layui 资源的请求，但项目中并未使用 Layui。
- **原因**：`index.html` 中缺少 `gpu-form` 的提交处理逻辑。404 错误是由于浏览器缓存或旧代码残留导致的 Layui 资源请求，而 `web/static` 为空。`index.html` 存在大量的冗余重复代码，导致逻辑混乱。
- **解决方案**：补全 `gpu-form` 的 JavaScript 提交逻辑。清理 `index.html` 中的冗余代码（重复的模态框和脚本）。为所有 API 操作增加 `try-catch` 错误处理和 `showToast` 成功反馈。建议用户强制刷新浏览器（Ctrl+F5）以解决 404 缓存问题。

### BUG: Python f-string `SyntaxError` 与控制台乱码
- **现象**：在 f-string 表达式中直接使用反斜杠（如 `.replace('\n', ' ')`）导致 `SyntaxError`；Windows 环境下控制台输出中文出现乱码。
- **原因**：Python 3.12 以前版本不支持在 f-string 的表达式部分使用反斜杠；Windows 默认控制台编码（如 GBK）与 Python 脚本编码（UTF-8）不一致。
- **解决方案**：
  1. 将包含反斜杠的操作移出 f-string 表达式，先定义变量再引用。
  2. 在脚本开头使用 `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')` 强制指定输出编码。
- **预防**：编写跨平台或 Windows 脚本时，始终注意输出编码设置，并避免在 f-string 中进行复杂转义操作。

### BUG: Artifact 保存路径错误
- **现象**：尝试将 `implementation_plan.md` 保存到项目根目录而非指定的对话 Artifact 目录时报错。
- **原因**：违反了系统关于 Artifact 存放位置的限制（必须在对话 ID 对应的子目录下）。
- **解决方案**：修正路径为正确的系统 Artifact 路径。
- **预防**：所有生成的 Artifact 必须严格遵守系统规定的路径限制。

### BUG: Agent 任务阻塞 (Task Stuck in Pending)
- **现象**：通过 API 提交任务后，任务状态始终为 `pending`，且上游服务（如 Whisper）没有收到任何请求。
- **原因**：`worker/agent.py` 中的 `task_loop` 逻辑为空，没有从 Redis 队列中提取任务并转发。
- **解决方案**：补全 Agent 的任务提取与 HTTP 转发逻辑，实现从 `queue:channel:*` 取出任务并请求上游 `service_url`。
- **预防**：在分布式系统中，确保生产者（API）和消费者（Agent）的逻辑链路完整，并增加消费者的消费日志。

## 2026-05-18
### BUG: Agent 中转二进制媒体响应 (音频/图像等) 抛出 JSONDecodeError 报错
- **现象**：当接入如 VoxCPM2 等语音合成、ComfyUI 等绘图服务作为上游时，Agent 转发请求成功（HTTP 200），但最终任务状态在调度网关中却被标记为 `failed`（失败），并伴有 `requests/json()` 解码异常。
- **原因**：`worker/agent.py` 原代码中在获得上游 200 响应后，硬编码了 `task_data["result"] = response.json()`。由于音频流、图片等为二进制文件流，无法被解析为 JSON，导致程序崩溃抛出异常。
- **解决方案**：
  1. 在 `worker/agent.py` 中引入 `Content-Type` 判断。若检测到响应内容类型为 `"audio/"`（音频），自动将其落地保存至网关静态资源目录 `data/uploads/tts_{task_id}.[ext]`，并将生成的本地静态下载 URL 作为中转结果返回。
  2. 对其余非音频响应，在调用 `response.json()` 时增加 `try-except` 容错层，若解析失败则退回将普通文本存入 `result`，防止系统崩溃。
- **预防**：编写任务调度或中转网关时，应充分考虑 AI 服务可能返回非 JSON（如二进制媒体流）的多样化场景，保持 Agent 的通用数据格式兼容性。

- **最佳实践**：在 `payload` 载荷中引入单键穿透控制字 `_file_path_key`。客户端仅需指定该字段（如 `_file_path_key: "audio"`），Agent 就会自动从该键提取路径进行跨机器下载，并在以 Multipart 上传给上游时，将该表单文件字段名直接透传为 `"audio"`，从而在调度层用最精简的控制项，实现了完全动态的文件键位穿透中转。

### BUG: Windows 终端 gbk 编码下多线程打印 Emoji 抛出 UnicodeEncodeError 崩溃
- **现象**：在 Windows PowerShell 终端中，并发运行测试脚本时，子线程（`threading.Thread`）内执行 `print` 带有 Emoji（如 🚀, 📤 等）的日志时，抛出 `UnicodeEncodeError: 'gbk' codec can't encode character...` 致命异常导致线程中途崩溃退栈。
- **原因**：Windows 控制台默认使用 `gbk` 编码页（Code Page 936），而 Python 的默认标准输出流（`sys.stdout`）在 `gbk` 环境下试图对含有 Unicode 特殊 Emoji 字符进行编码打印时，因该字符超出 `gbk` 字符集范围而直接报错崩溃。
- **解决方案**：
  在多线程脚本文件的最头部，强行将 `sys.stdout` 的输出流用全局的 `utf-8` 文本流进行重新包裹和重设（Wrapper）：
  ```python
  import sys
  if sys.stdout.encoding != 'utf-8':
      import io
      sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
  ```
- **预防**：编写在 Windows 环境运行、特别是输出含有 Emoji 或特殊 Unicode 日志的脚本时，务必在最头部通过重裹 `sys.stdout` 流来锁定控制台输出为 `utf-8` 编码，以保证多线程打印的绝对鲁棒性和中文不乱码。


