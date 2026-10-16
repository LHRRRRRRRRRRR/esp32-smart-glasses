# 更新记录

本文件记录项目所有值得留存的变更。

---

## [2.0.0] - 2026-10-16

本次更新把 AI 后端从硅基流动迁移到 DeepSeek 官方 API，修复 4 个真实缺陷，并重做了 Web 界面。

### AI 后端

- **更换服务商**：硅基流动（SiliconFlow）→ DeepSeek 官方 API
  - 原因：原配置的 4 个模型中有 3 个已在硅基流动下架
    （`Qwen/Qwen-VL-Chat`、`Qwen/Qwen2-VL-7B-Instruct`、`internlm/internlm-xcomposer2-vl-7b`）
  - 新模型 `deepseek-flash`（DeepSeek-V4.1-Flash），支持图片输入
  - 注意：`deepseek-v4-pro` **不支持**视觉，不能用于本项目
- **新增思考模式开关**：`THINKING_ENABLED` / `THINKING_EFFORT`（默认开启，强度 high）
- **修复识别结果为空**：`max_tokens` 原为硬编码的 150，而思考模式的「推理内容」同样占用该额度。
  推理吃掉约 120 个 token 后最终答案被截断，表现为返回空字符串或 `"SC"` 这类半截输出。
  改为可配置的 `MAX_OUTPUT_TOKENS = 1024`
- **API Key 持久化**：网页 API Config 里填写的密钥会写入 `runtime_config.json`，重启后无需重填
  - 读取优先级：环境变量 `DEEPSEEK_API_KEY` > 网页填写 > `local_config.py`

### ESP32 固件

- **修复未定义行为**：`camera_config_t config;` 是未初始化的栈变量，
  `grab_mode` 与 `fb_location` 两个字段从未被赋值
- **修复拍照拿到陈旧画面**：`grab_mode` 设为 `CAMERA_GRAB_LATEST`，并在拍照前丢弃队列中的旧帧。
  此前使用默认的 `CAMERA_GRAB_WHEN_EMPTY`，加上程序只在按键时才取帧，
  按快门拿到的可能是开机时或上一次按快门时的画面
- **改善暗光拍摄**：`gainceiling` 由 `(gainceiling_t)2`（即 `GAINCEILING_8X`）改为 `GAINCEILING_32X`；
  `ae_level` 由 0 改为 1。原值下自动曝光撞到 8 倍增益上限后无法继续提亮，实测拍出接近全黑的照片
- **`fb_location` 显式设为 `CAMERA_FB_IN_PSRAM`**（经核对与 OpenGlass 官方固件一致）

### Web 界面

- 重做视觉：光晕背景、品牌区、卡片化布局、统一的动效曲线
- API Config 与 Prompt Settings 改为可折叠面板，减少表单堆叠
- 照片卡片固定 4:3 比例，网格整齐对齐；新照片带双层光环动画
- 新增照片计数徽章
- 图片查看器加入背景模糊与缩放动画
- 响应式断点重做，支持 `prefers-reduced-motion`

### 文档与配置

- README 更新技术栈与密钥配置说明
- `esp32/include/config.h.example` 补充端口一致性与 `http://` 格式提醒
- 流程图同步更新
- 新增本更新记录

### 修复的其它问题

- `esp32/include/config.h` 中 `SERVER_URL` 写成 `"http://http://...:8080/upload"`
  （协议重复、端口与 `app.py` 的 5000 不一致），会导致 `HTTPClient.begin()` 直接失败
- 清理 10 条孤儿记录：数据库中存在记录但图片文件已丢失，导致界面显示空白图框

### 安全说明

以下文件均在 `.gitignore` 中，不会进入版本库：

```
server/local_config.py          # API 密钥
server/runtime_config.json      # 网页填写的 API 密钥
server/smart_glasses.db         # 数据库
server/photos/*.jpg             # 拍摄的照片
esp32/include/config.h          # WiFi 名称与密码
```

---

## [1.0.0] - 2026-09-18

首个版本。

### ESP32 端
- 摄像头初始化（VGA，失败自动降级 QVGA）
- WiFi 连接、超时重启与自动重连
- 按键触发拍照（松开触发），HTTP POST 上传图片
- LED 状态指示：待机呼吸、连接闪烁、成功双闪、错误快闪

### 服务端
- Flask 应用，SQLAlchemy + SQLite 存储
- SSE 实时推送（含轮询降级）
- 接口：上传、照片列表、新增检测、图片获取、删除、
  获取/设置/重置配置、获取/设置/重置提示词
- AI 调用失败时自动清理已保存的图片，避免产生孤儿文件
- 路径穿越防护

### 前端
- 暗色模式（跟随系统 + localStorage 记忆）
- 照片卡片列表、大图查看、OCR 文字一键复制
- 提示词预设：OCR 识别 / 场景识别 / 详细描述 / 问答模式

### 硬件与文档
- OpenGlass 眼镜外壳 `openglass_case.stl`（经 SHA256 核对与官方文件一致）
- README 与项目结构流程图
