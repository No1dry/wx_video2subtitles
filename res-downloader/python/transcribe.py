# -*- coding: utf-8 -*-
"""
批量视频转录工具 —— 基于 faster-whisper (ASR) 提取字幕。

把目录下的视频批量转录为 .srt 字幕文件和 / 或 .txt 纯文本。

用法示例:
    # 转录 wx 目录下所有视频，输出 srt + txt 到 wx/subtitles
    python transcribe.py

    # 指定目录、模型、只输出 srt
    python transcribe.py -i wx -o output --model large-v3 --format srt

    # 强制中文、用 GPU
    python transcribe.py --language zh --device cuda

参数说明见 `python transcribe.py -h`。
"""

import argparse
import os
import sys
import time

# 支持的视频 / 音频扩展名
MEDIA_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".ts", ".m4v",
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma",
}


def find_media(inputs):
    """收集所有待转录的媒体文件。inputs 可以是目录或文件路径列表。"""
    files = []
    for item in inputs:
        if os.path.isdir(item):
            for name in sorted(os.listdir(item)):
                path = os.path.join(item, name)
                if os.path.isfile(path) and os.path.splitext(name)[1].lower() in MEDIA_EXTS:
                    files.append(path)
        elif os.path.isfile(item):
            files.append(item)
        else:
            print("  [警告] 路径不存在，已跳过: %s" % item)
    return files


def fmt_timestamp(seconds):
    """秒 -> SRT 时间戳 HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000.0))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def write_srt(segments, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            text = seg["text"].strip()
            if not text:
                continue
            f.write("%d\n" % i)
            f.write("%s --> %s\n" % (fmt_timestamp(seg["start"]), fmt_timestamp(seg["end"])))
            f.write("%s\n\n" % text)


def write_txt(segments, path):
    with open(path, "w", encoding="utf-8") as f:
        for seg in segments:
            text = seg["text"].strip()
            if text:
                f.write(text + "\n")


def resolve_model(model_name, model_dir=None):
    """若 model_name 是裸名 (如 small/large-v3)，在若干 models 根目录里找已下载的本地模型。

    查找顺序: --model-dir 参数 -> 环境变量 WHISPER_MODEL_DIR -> 脚本同级 models/。
    都找不到则原样返回 (交给 faster-whisper 自动从 HuggingFace 下载)。
    """
    if os.path.sep in model_name or "/" in model_name or os.path.isdir(model_name):
        return model_name
    roots = []
    if model_dir:
        roots.append(model_dir)
    if os.environ.get("WHISPER_MODEL_DIR"):
        roots.append(os.environ["WHISPER_MODEL_DIR"])
    roots.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "models"))
    for root in roots:
        local = os.path.join(root, "faster-whisper-" + model_name)
        if os.path.isfile(os.path.join(local, "model.bin")):
            return local
    return model_name  # 交给 faster-whisper 自动从 HuggingFace 下载


def load_model(model_name, device, compute_type, model_dir=None):
    """加载 faster-whisper 模型。device='auto' 时优先 GPU，失败回退 CPU。"""
    from faster_whisper import WhisperModel

    model_name = resolve_model(model_name, model_dir)

    tried = []
    if device == "auto":
        order = [("cuda", compute_type or "float16"), ("cpu", "int8")]
    else:
        order = [(device, compute_type or ("float16" if device == "cuda" else "int8"))]

    last_err = None
    for dev, ct in order:
        try:
            print("加载模型: %s  (device=%s, compute_type=%s) ..." % (model_name, dev, ct))
            model = WhisperModel(model_name, device=dev, compute_type=ct)
            print("模型加载成功，使用 %s。\n" % dev.upper())
            return model
        except Exception as e:  # noqa
            tried.append(dev)
            last_err = e
            print("  [提示] 在 %s 上加载失败: %s" % (dev, e))
            if dev == "cuda":
                print("  改为尝试 CPU ...")
    raise RuntimeError("模型加载失败 (尝试过: %s): %s" % (tried, last_err))


def emit_progress(pct):
    """打印机器可读进度标记，供宿主程序 (res-downloader) 解析显示进度条。"""
    print("__PROGRESS__ %.1f" % pct, flush=True)


def transcribe_file(model, path, language, beam_size, vad, progress=False):
    """转录单个文件，返回 (segments_list, info)。progress=True 时输出进度标记。"""
    segments_iter, info = model.transcribe(
        path,
        language=language,            # None = 自动检测
        beam_size=beam_size,
        vad_filter=vad,               # 语音活动检测，过滤静音
        vad_parameters={"min_silence_duration_ms": 500} if vad else None,
    )
    total = getattr(info, "duration", 0.0) or 0.0
    segments = []
    last_pct = -5.0
    if progress:
        emit_progress(0.0)
    for seg in segments_iter:
        segments.append({"start": seg.start, "end": seg.end, "text": seg.text})
        if progress and total > 0:
            pct = min(99.0, seg.end / total * 100.0)
            if pct - last_pct >= 2.0:   # 每涨 2% 上报一次，避免刷屏
                emit_progress(pct)
                last_pct = pct
    if progress:
        emit_progress(100.0)
    return segments, info


def main():
    # 让输出实时刷新且为 UTF-8，便于宿主程序 (res-downloader) 逐行读取进度
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:  # noqa  (Python<3.7 或非常规流)
        pass

    parser = argparse.ArgumentParser(
        description="批量视频转录 -> SRT / TXT 字幕 (基于 faster-whisper ASR)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-i", "--input", nargs="+", default=["wx"],
                        help="输入目录或文件 (可多个)")
    parser.add_argument("-o", "--output", default=None,
                        help="输出目录 (默认: 每个视频同目录下的 subtitles 子文件夹)")
    parser.add_argument("--model", default="medium",
                        help="模型: tiny/base/small/medium/large-v3 等。越大越准但越慢")
    parser.add_argument("--model-dir", default=None,
                        help="本地模型根目录 (内含 faster-whisper-<名字> 文件夹)")
    parser.add_argument("--language", default=None,
                        help="语言代码如 zh/en。默认自动检测；中文内容建议设为 zh")
    parser.add_argument("--format", default="both", choices=["srt", "txt", "both"],
                        help="输出格式")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"],
                        help="计算设备")
    parser.add_argument("--compute-type", default=None,
                        help="计算精度 (float16/int8_float16/int8 等)，留空自动选择")
    parser.add_argument("--beam-size", type=int, default=5, help="beam search 大小")
    parser.add_argument("--no-vad", action="store_true", help="关闭静音过滤 (VAD)")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的字幕文件")
    parser.add_argument("--progress", action="store_true",
                        help="输出机器可读进度标记 (__PROGRESS__/__SUBTITLE__)，供宿主程序解析")
    args = parser.parse_args()

    files = find_media(args.input)
    if not files:
        print("未找到任何媒体文件。检查输入路径: %s" % args.input)
        sys.exit(1)

    print("共找到 %d 个媒体文件待转录。\n" % len(files))

    model = load_model(args.model, args.device, args.compute_type, args.model_dir)

    total_start = time.time()
    ok, skipped, failed = 0, 0, 0

    for idx, path in enumerate(files, 1):
        base = os.path.splitext(os.path.basename(path))[0]
        out_dir = args.output or os.path.join(os.path.dirname(path) or ".", "subtitles")
        os.makedirs(out_dir, exist_ok=True)
        srt_path = os.path.join(out_dir, base + ".srt")
        txt_path = os.path.join(out_dir, base + ".txt")

        want_srt = args.format in ("srt", "both")
        want_txt = args.format in ("txt", "both")

        # 跳过已存在
        if not args.overwrite:
            exists = (not want_srt or os.path.exists(srt_path)) and \
                     (not want_txt or os.path.exists(txt_path))
            if exists:
                print("[%d/%d] 已存在，跳过: %s" % (idx, len(files), base))
                skipped += 1
                continue

        print("[%d/%d] 转录中: %s" % (idx, len(files), os.path.basename(path)))
        t0 = time.time()
        try:
            segments, info = transcribe_file(
                model, path, args.language, args.beam_size, not args.no_vad, args.progress
            )
        except Exception as e:  # noqa
            print("    [失败] %s\n" % e)
            failed += 1
            continue

        if want_srt:
            write_srt(segments, srt_path)
            if args.progress:
                print("__SUBTITLE__ " + os.path.abspath(srt_path), flush=True)
        if want_txt:
            write_txt(segments, txt_path)
            if args.progress:
                print("__SUBTITLE__ " + os.path.abspath(txt_path), flush=True)

        dur = time.time() - t0
        lang = getattr(info, "language", "?")
        prob = getattr(info, "language_probability", 0.0) or 0.0
        print("    完成: %d 段, 检测语言=%s(%.0f%%), 耗时 %.1fs -> %s\n"
              % (len(segments), lang, prob * 100, dur, out_dir))
        ok += 1

    print("=" * 50)
    print("全部完成: 成功 %d, 跳过 %d, 失败 %d, 总耗时 %.1fs"
          % (ok, skipped, failed, time.time() - total_start))


if __name__ == "__main__":
    main()
