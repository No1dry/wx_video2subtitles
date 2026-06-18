# res-downloader（集成转录字幕版）

这是本项目的资源嗅探下载内核，基于开源项目 [res-downloader](https://github.com/putyy/res-downloader)（Go + Wails，MIT）二次开发，并在其上集成了本地 ASR 语音转字幕功能。

完整使用说明（整合包运行 / 源码运行 / 打包）见仓库根目录的 [README](../README.md)。

- 转录脚本与依赖：`python/`
- 打包脚本（生成免环境整合包）：`packaging/build-windows.ps1`

> 基础下载能力来自 res-downloader，遵循其开源许可（见 `LICENSE`）。本项目仅供学习研究使用。
