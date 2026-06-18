# wx_video2subtitles

一款集 **网络资源嗅探下载** + **一键 ASR 语音转字幕** 于一体的桌面工具。

在 [res-downloader](https://github.com/putyy/res-downloader)（Go + Wails 跨平台资源下载器）的基础上，集成了基于 [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 的本地语音识别：下载视频号 / 小程序 / 抖音 / 快手 / 小红书等平台的视频后，可直接在软件里把视频转成 `.srt` / `.txt` 字幕，支持 GPU 加速。

> 仅供学习与研究用途，请勿用于商业或违法用途。

---

## ✨ 功能

- 🎬 资源嗅探下载：视频 / 音频 / 图片 / m3u8 / 直播流等
- 📝 **一键转录字幕**：下载后右键「转录字幕」或多选「批量转录」，可选 SRT / TXT
- ⚡ **GPU 加速**：有 NVIDIA 显卡时自动用显卡（CTranslate2/CUDA），无显卡自动回退 CPU
- 📊 实时进度条、串行队列（一次转一个，不会卡机）
- ⚙️ 可配置：模型、语言、字幕保存目录、Python 路径（仅源码模式需要）

---

## 🚀 使用方式一：整合包直接解压运行（推荐，免配置）

适合**普通用户 / 想直接用的人**，无需安装 Python、Go、Node 等任何环境。

1. 到本仓库 [Releases](../../releases) 下载整合包：
   - `res-downloader-portable-cpu.zip` —— **任何 Windows 电脑可用**（无需显卡）
   - `res-downloader-portable-gpu.zip` —— 有 **NVIDIA 显卡**时自动加速（无卡也能回退 CPU，体积更大）
2. **整包解压**到任意目录（路径尽量别带特殊字符）。
3. 双击文件夹里的 `res-downloader.exe` 启动。
4. 首次启动按提示 **允许安装证书** 并 **允许网络访问**。
5. 首页左上角点「启动抓取」，去对应 App / 网页播放要下载的视频，回到软件即可看到资源列表。
6. 点资源的下载按钮（或勾选多条后「批量下载」）。
7. 下载完成后，点该行操作菜单 →「转录字幕」，或勾选多条后「批量转录」，选格式即可。字幕默认生成在视频所在目录的 `subtitles` 子文件夹。

> ⚠️ **整包必须保持完整**：`res-downloader.exe` 旁边必须有 `transcriber\` 文件夹（内置 Python 引擎与模型），不能只把 exe 单独拷出来用，否则转录会失败。

目录结构（请勿拆散）：

```
res-downloader-portable-xxx/
├── res-downloader.exe        主程序（双击这个）
├── transcriber/              内置转录引擎（Python + faster-whisper，免环境）
│   └── models/               内置语音模型
└── 使用说明.txt
```

---

## 🧑‍💻 使用方式二：源码运行（开发 / 自行编译）

### 1. 环境依赖

| 工具 | 版本 | 用途 |
|------|------|------|
| [Go](https://go.dev/dl/) | 1.22+ | 后端 |
| [Node.js](https://nodejs.org/) | 16+ | 前端构建 |
| [Wails CLI](https://wails.io/) | v2 | 桌面应用框架 |
| [Python](https://www.python.org/) | 3.8+ | 语音识别（转录） |

安装 Wails CLI：

```bash
go install github.com/wailsapp/wails/v2/cmd/wails@latest
```

### 2. 拉取代码

```bash
git clone https://github.com/No1dry/wx_video2subtitles.git
cd wx_video2subtitles
```

### 3. 安装 Python 依赖（转录用）

```bash
# 建议 Python 3.8+，如旧版 pip 报错先升级： python -m pip install --upgrade pip
pip install -r res-downloader/python/requirements.txt
```

### 4. 下载语音模型（必需，模型不在仓库里）

模型不随仓库发布，请自行下载（任选其一）：

```bash
cd res-downloader/python
python download_model.py small        # 推荐，约 480MB，使用国内镜像下载
# 想更准可下载更大的： python download_model.py large-v3   （约 3GB）
```

下载后模型会放到 `res-downloader/python/models/faster-whisper-<名字>/`。

也可手动下载（放到上面的目录即可）：

| 模型 | 下载地址（HuggingFace / 国内镜像） |
|------|--------------------------------------|
| small | https://huggingface.co/Systran/faster-whisper-small ｜ 镜像 https://hf-mirror.com/Systran/faster-whisper-small |
| medium | https://huggingface.co/Systran/faster-whisper-medium |
| large-v3 | https://huggingface.co/Systran/faster-whisper-large-v3 |

> faster-whisper 通过内置 PyAV 解码音频，**无需单独安装 ffmpeg**。

### 5. 运行 / 编译

```bash
cd res-downloader

# 开发模式（热重载）
wails dev

# 编译生产版 exe（输出 build/bin/res-downloader.exe）
wails build -platform windows/amd64
```

> 源码模式下，软件通过系统 `python` 调用 `res-downloader/python/transcribe.py` 转录。
> 如果系统里有多个 Python，或 `python` 指向的环境没装 faster-whisper，请在
> **设置 → 转录设置 → Python 路径** 填写正确的解释器（如 `D:\Python\python.exe`）。

### 6. 打包整合包（可选）

生成「免环境整合包」（CPU 版 + GPU 版）：

```powershell
# 需先装好 PyInstaller： pip install pyinstaller
cd res-downloader/packaging
powershell -ExecutionPolicy Bypass -File build-windows.ps1
```

产物在 `res-downloader/packaging/dist/` 下（GPU 版需本机有 CUDA 12 的 cublas/cudnn 库，脚本里可调整路径）。

---

## 🎚️ 命令行单独转录（不开软件）

`res-downloader/python/transcribe.py` 也可独立批量转录一个目录：

```bash
python transcribe.py -i <视频目录> --model small --language zh --format both
# 详见 python transcribe.py -h
```

---

## ⚙️ 转录相关设置（软件内：设置 → 转录设置）

| 设置 | 说明 |
|------|------|
| 识别模型 | `small` / `medium` / `large-v3` 等，越大越准越慢 |
| 默认字幕格式 | SRT / TXT / 两者 |
| 默认语言 | 中文建议 `zh`；`auto` 自动检测 |
| 字幕保存目录 | 留空 = 视频同级 `subtitles` 子文件夹；也可指定固定文件夹 |
| Python 路径 | **仅源码模式生效**；整合包会优先用内置引擎，无需配置 |

---

## ❓ 常见问题

- **转录提示「找不到转录引擎」**：整合包请确认 `transcriber` 文件夹与 exe 在同一目录；源码模式请装好 Python + faster-whisper，或在设置里配置 Python 路径。
- **转录很慢**：未使用 GPU。CPU 版本来就慢；有 NVIDIA 显卡请用 GPU 整合包，或源码模式用 GPU 环境。
- **关闭软件后无法上网**：到系统代理设置里手动关闭代理。
- **下载慢 / 大文件失败**：可复制链接用专门的下载工具。

---

## 🙏 致谢

- [res-downloader](https://github.com/putyy/res-downloader) —— 资源嗅探下载的基础项目（MIT）
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) —— 高性能语音识别
- [Wails](https://github.com/wailsapp/wails) —— Go 桌面应用框架

## 📄 许可

本项目基于 res-downloader 二次开发，遵循其开源许可（见 `res-downloader/LICENSE`）。仅供学习研究使用。
