# 字幕转录模块 (集成到 res-downloader)

本目录是 res-downloader 的「一键转录字幕」功能依赖的 Python 模块，基于
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) 语音识别 (ASR)，
支持 GPU 加速，可把下载下来的音视频转成 `.srt` / `.txt` 字幕。

## 工作原理

1. 在软件里下载好一个视频/音频后，点该行的操作菜单 → **转录字幕**（或多选后「批量转录」）。
2. 弹窗选择字幕格式（SRT / TXT / 两者）和语言，点「开始转录」。
3. Go 后端调用本目录的 `transcribe.py` 子进程完成识别，字幕输出到**媒体文件所在目录**。
4. 完成后软件弹出提示并给出字幕路径，可在操作菜单点「打开字幕」。

## 首次使用：安装依赖

软件本身不含 Python。请在本机安装 Python 3.8+，然后：

```bash
pip install -r requirements.txt
```

如果 `python` 不在系统 PATH，请到软件「设置 → 转录设置 → Python 路径」填写完整路径，
例如 `D:\Python3.8\python.exe`。

## 模型

- 已内置 `small` 模型于 `python/models/faster-whisper-small/`，开箱即用。
- 想要更高准确率（中文长视频推荐），下载更大的模型：

  ```bash
  python download_model.py large-v3      # 约 3GB
  ```

  然后在「设置 → 转录设置 → 识别模型」把模型名改成 `large-v3`。

## 设置项说明（软件内：设置 → 转录设置）

| 设置 | 说明 |
|------|------|
| 识别模型 | 模型名 `tiny/base/small/medium/large-v3` 或本地路径，越大越准越慢 |
| 默认字幕格式 | SRT / TXT / 两者 |
| 默认语言 | 中文建议 `zh`；`auto` 为自动检测 |
| Python 路径 | python 可执行文件，默认 `python` |
| 模型目录 | 本地模型根目录，留空用 `python/models` |
| 转录脚本路径 | 留空自动查找 `python/transcribe.py` |

## 命令行单独使用

`transcribe.py` 也可独立批量转录一个目录：

```bash
python transcribe.py -i <视频目录> --model small --language zh --format both
```

详见 `python transcribe.py -h`。

> 说明：faster-whisper 通过内置的 PyAV 解码音频，无需额外安装 ffmpeg。
