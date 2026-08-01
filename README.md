# video2srt

使用 **Qwen3-ASR-1.7B** 进行语音识别，并使用 **Qwen3 ForcedAligner** 为识别文本生成精确时间戳，最终将视频转换为 SRT 字幕。

当前处理流程如下：

```text
视频文件 → FFmpeg 提取 16 kHz 单声道 WAV → 音频分块
         → Qwen3-ASR 识别 → Qwen3 ForcedAligner 强制对齐
         → 按 ASR 句子边界生成字幕 → SRT 文件
```

> 当前仓库仍处于原型阶段。开始前请阅读本文的“当前代码限制”，尤其是 macOS 推理限制。

## 环境要求

- Python 3.10 或更高版本（建议 3.10/3.11）
- [FFmpeg](https://ffmpeg.org/)：须可由配置指定，或可在系统 `PATH` 中找到
- Qwen3-ASR-1.7B 本地模型目录
- Qwen3-ForcedAligner 本地模型目录
- Python 依赖见 `requirements.txt`

GPU 推理建议使用 NVIDIA CUDA。`device: auto` 会依次选择 CUDA、Apple Silicon MPS、CPU，并按设备选择安全的推理精度：CUDA 使用 BF16（支持时）或 FP16，MPS 使用 FP16，CPU 使用 FP32。

## Mac 开发环境

macOS 适合进行代码开发、静态检查和 FFmpeg 流程验证。

1. 安装 Homebrew（如尚未安装），然后安装 Python 与 FFmpeg：

   ```bash
   brew install python@3.11 ffmpeg
   ```

2. 创建并激活虚拟环境：

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. 复制或下载两个模型到本机目录，并在配置文件中填写其绝对路径。

4. 确认 FFmpeg 可用：

   ```bash
   ffmpeg -version
   ```

### macOS 推理说明

当前代码会自动尝试 Apple Silicon 的 MPS，并使用 FP16 推理。由于 Qwen3-ASR 与相关依赖在不同 Mac/PyTorch 版本上的兼容性可能不同，建议先用短视频验证；长视频推理仍推荐使用 Windows + NVIDIA CUDA 环境。

推荐将 macOS 用作开发环境，把长视频推理放到下述 Windows + NVIDIA CUDA 环境执行。

## Windows CUDA 推理环境

建议使用 NVIDIA GPU（显存容量须同时满足 ASR 与 ForcedAligner 的模型加载需求）以及已正确安装的 NVIDIA 驱动和 CUDA 兼容版 PyTorch。

1. 安装 Python 3.10 或 3.11，以及包含 `ffmpeg.exe` 的 FFmpeg 发行版。

2. 创建虚拟环境并安装依赖：

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. 根据你的 CUDA 与 PyTorch 版本安装 CUDA 版 PyTorch。请以 PyTorch 官方安装页面提供的命令为准；安装后验证：

   ```powershell
   python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
   ```

   输出第一个值应为 `True`。

4. 下载或准备本地模型目录，并配置模型、FFmpeg 路径及设备：

   ```yaml
   models:
     asr: 'C:\Models\Qwen3-ASR-1.7B'
     aligner: 'C:\Models\Qwen3-ForcedAligner'

   ffmpeg:
     path: 'C:\ffmpeg\bin\ffmpeg.exe'

   device: auto

   chunk:
     seconds: 300
     overlap_seconds: 2
   ```

   若只在 GPU 机器上运行，也可以把 `device` 设为 `cuda:0`。

## 安装步骤

以下步骤适用于已准备好 Python、FFmpeg 与模型的环境。

1. 克隆或进入项目目录：

   ```bash
   cd /path/to/video2srt
   ```

2. 创建虚拟环境并安装依赖（命令请按 macOS 或 Windows 章节选择）。

3. 以 `config/config.example.yaml` 为基础创建或编辑配置文件，填写本机模型和 FFmpeg 路径。Windows CUDA 环境可直接复制并修改 `config/config.windows.yaml`。

4. 核对配置键名。当前 `Pipeline` 实际读取的是：

   ```yaml
   models:
     asr: /absolute/path/to/Qwen3-ASR-1.7B
     aligner: /absolute/path/to/Qwen3-ForcedAligner

   ffmpeg:
     path: /absolute/path/to/ffmpeg

   device: auto

   chunk:
     seconds: 300
     overlap_seconds: 2
   ```

   推荐使用上述规范键名。为兼容既有 `config/config.yaml`，配置加载器也接受旧的 `model` 和 `ffmpeg.exe` 键名，并自动转换为 `models` 和 `ffmpeg.path`。

## 使用方法

基础命令：

```bash
python run.py /path/to/input.mp4
```

指定配置文件：

```bash
python run.py /path/to/input.mp4 --config /path/to/config.yaml
```

成功后，字幕会写入与视频相同的目录，文件名为：

```text
输入：/path/to/demo.mp4
输出：/path/to/demo.srt
```

运行期间还会在当前工作目录生成：

- `temp/`：提取的 WAV 音频与分块音频；
- `logs/video2srt.log`：运行日志。

## 字幕生成规则

- Qwen3-ASR 输出的 `。！？!?；;…` 被视为句子边界；每个 ASR 句子对应一条 SRT 字幕。
- 字幕文本直接保留 Qwen3-ASR 识别出的原始标点，不再根据 ForcedAligner 结果补标点。
- Qwen3 ForcedAligner 只负责为每个句子映射起止时间。
- 若 ASR 文本与强制对齐文本存在差异，程序会记录警告，并尽可能保留可用的时间范围。

## 当前代码限制

- 音频分块会记录真实起始时间，并默认提供 2 秒相邻重叠；完全相同且时间重叠的字幕会去重。识别文本存在差异时，边界附近仍可能出现相近的重复字幕。
- 当前以 ASR 句子边界直接生成字幕，不会因字符数、时长或阅读速度再次拆分；特别长的 ASR 句子可能形成较长字幕。
- ASR 和 ForcedAligner 会在任务启动时同时加载；显存不足时可能失败。
- `subtitle.format` 配置项当前未接入，输出格式固定为 SRT。

## 项目结构

```text
video2srt/
├── README.md
├── requirements.txt           # Python 依赖
├── run.py                     # 命令行入口
├── config/
│   └── config.yaml            # 模型、FFmpeg、设备和分块配置
└── src/
    ├── config.py              # YAML 配置读取
    ├── logger.py              # 控制台与文件日志
    ├── pipeline.py            # 主处理流程编排
    ├── ffmpeg_util.py         # 视频音频提取
    ├── audio_splitter.py      # WAV 音频分块
    ├── qwen3_asr.py           # Qwen3-ASR 模型封装
    ├── aligner.py             # Qwen3 ForcedAligner 封装
    ├── punctuation.py         # 旧版标点恢复实现（当前主流程不使用）
    ├── segmenter.py           # ASR 句子边界与对齐时间映射
    └── subtitle.py            # SRT 写入
```
