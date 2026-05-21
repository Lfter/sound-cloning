# Voice Patch Studio

本地语音克隆剪辑工具 V1。它面向剪辑补素材：导入授权参考音频，维护声音库，按中文脚本文本批量生成独立 WAV，并保留每个片段的参数与导出清单。

## 当前实现

- macOS 桌面目标：Tauri 2 + React/TypeScript。
- 本地服务：Python + FastAPI + SQLite。
- 模型适配：`Qwen3TTSAdapter` 优先尝试 Apple Silicon/MLX 的 Qwen3-TTS Base 模型，找不到模型或依赖时会生成本地预览 WAV，保证工作流可以先试用。
- 输出：每句脚本生成多候选 WAV，导出为 `48kHz 24-bit WAV`，并生成 CSV manifest。

## 运行

项目已经按本地优先方式准备好运行组件：

- Python 3.12 虚拟环境：`.venv/`
- 本地 Node.js 与 npm 包装脚本：`.tools/` 与 `scripts/npm-local.sh`
- 本地 Rust/Cargo：`.cargo/` 与 `.rustup/`
- 本地 ffmpeg：`.venv/bin/ffmpeg`

开发运行：

```bash
scripts/npm-local.sh run dev
```

只跑本地后端：

```bash
scripts/npm-local.sh run backend
```

已验证可以构建 macOS App，构建产物位于：

```text
src-tauri/target/release/bundle/macos/Voice Patch Studio.app
```

## Qwen3-TTS 模型

将 MLX/8-bit 模型放在项目根目录的 `models/` 下，优先级如下：

```text
models/
  Qwen3-TTS-12Hz-1.7B-Base-8bit/
  Qwen3-TTS-12Hz-1.7B-Base/
  Qwen3-TTS-12Hz-0.6B-Base-8bit/
  Qwen3-TTS-12Hz-0.6B-Base/
```

安装 MLX 相关依赖可参考：

```bash
.venv/bin/python -m pip install -r backend/requirements-macos-mlx.txt
```

第一版默认不自动下载模型，避免在剪辑机上静默占用几十 GB 空间。

## 测试

```bash
scripts/npm-local.sh run test
```

只跑后端单元测试：

```bash
scripts/npm-local.sh run test:backend
```

后端测试使用临时目录，不会写入项目根目录的 `data/`；模型不可用时会走预览 WAV 生成路径。
