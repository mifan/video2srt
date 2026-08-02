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

建议使用 NVIDIA GPU（显存容量须满足单个 ASR 或 ForcedAligner 模型的加载需求）以及已正确安装的 NVIDIA 驱动和 CUDA 兼容版 PyTorch。两个模型不会同时驻留显存。

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

   language: auto

   output:
     directory: null
     overwrite: false

   chunk:
     seconds: 300
     overlap_seconds: 2

   subtitle:
     max_chars: 24
     max_duration_seconds: 6.0
     max_cps: 15
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

   language: auto

   output:
     directory: null
     overwrite: false

   chunk:
     seconds: 300
     overlap_seconds: 2

   subtitle:
     max_chars: 24
     max_duration_seconds: 6.0
     max_cps: 15
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

指定输出文件：

```bash
python run.py /path/to/input.mp4 --output /path/to/output.srt
```

默认不会覆盖已有字幕。确认需要替换时，显式传入：

```bash
python run.py /path/to/input.mp4 --overwrite
```

成功后，字幕会写入与视频相同的目录，文件名为：

```text
输入：/path/to/demo.mp4
输出：/path/to/demo.srt
```

也可在配置中指定默认输出目录与覆盖策略：

```yaml
output:
  directory: null  # null 表示与输入视频同目录
  overwrite: false
```

运行期间还会在当前工作目录生成：

- `temp/`：提取的 WAV 音频与分块音频；
- `logs/video2srt.log`：运行日志。

## 字幕质量

- 文本与标点：字幕直接采用 Qwen3-ASR 的原始文本；`。！？!?；;…` 被视为句子边界，因此每个 ASR 句子对应一条 SRT 字幕。
- 时间戳：Qwen3 ForcedAligner 只负责映射每句的起止时间，不会改写字幕文本。映射时按顺序匹配 ASR 文本与对齐文本，而不是只按字符数推算。
- 边界保护：音频块默认有 2 秒重叠；完全相同且时间重叠的字幕会自动去重，以降低跨块重复或截断的概率。
- 差异处理：若 ASR 与对齐文本存在局部差异，程序会记录警告，并以已匹配字符计算时间；完全无法匹配时才会使用比例估算。
- 长句切分：当一句 ASR 文本超过 `subtitle.max_chars` 或 `subtitle.max_duration_seconds` 时，会优先在逗号、顿号、冒号或空格处进行二级切分，并使用 ForcedAligner 的条目时间为子句定位。
- 语言：`language: auto` 时优先使用 Qwen3-ASR 返回的语言字段；也可设为如 `Chinese` 或 `English`，同时约束 ASR 与 ForcedAligner。

二级切分会尽量满足长度和时长限制。CPS 反映原始说话速度，单纯拆分不能从根本降低它；当字幕超过 `subtitle.max_cps` 时，程序会记录警告，便于后续针对静音区扩展显示时间或人工复核。

## 当前代码限制

- 音频分块会记录真实起始时间，并默认提供 2 秒相邻重叠；完全相同且时间重叠的字幕会去重。识别文本存在差异时，边界附近仍可能出现相近的重复字幕。
- ASR 与 ForcedAligner 采用惰性加载：先完成全部 ASR 并释放其显存，再加载 ForcedAligner 完成对齐。单个模型仍须能独立装入显存。
- `subtitle.format` 配置项当前未接入，输出格式固定为 SRT。

## SRT 输出校验

- 写入前会清理空文本、按时间排序，并拒绝负时间、非有限时间、缺失时间或 `end <= start` 的字幕。
- 相邻字幕重叠时，后一个字幕的开始时间会裁剪到前一条结束时间；若裁剪后没有有效时长，则跳过该条字幕并记录警告。
- 写入采用临时文件后原子替换，避免中途失败留下半成品 SRT。

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
    ├── segmenter.py           # ASR 句子边界与对齐时间映射
    └── subtitle.py            # SRT 写入
```
