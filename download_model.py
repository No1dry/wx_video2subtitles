# -*- coding: utf-8 -*-
"""
下载 faster-whisper 模型到本地 models/ 目录 (直连 HTTP + 自动重试)。

适用于 huggingface_hub 自动下载不稳定 / 被墙的网络环境，默认使用
hf-mirror.com 镜像。

用法:
    python download_model.py small
    python download_model.py large-v3
    python download_model.py medium --mirror https://hf-mirror.com

下载完成后即可:
    python transcribe.py --model large-v3   # 会自动找到 models/faster-whisper-large-v3
"""

import argparse
import os
import sys
import time

import requests

# 模型名 -> HuggingFace 仓库
REPOS = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
}

# 需要下载的文件 (部分模型没有 preprocessor_config.json，404 时跳过)
FILES = ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt",
         "vocabulary.json", "preprocessor_config.json"]


def download(model, mirror, out_root):
    if model not in REPOS:
        print("未知模型: %s。可选: %s" % (model, ", ".join(REPOS)))
        sys.exit(1)
    repo = REPOS[model]
    base = "%s/%s/resolve/main/" % (mirror.rstrip("/"), repo)
    dst = os.path.join(out_root, "faster-whisper-" + model)
    os.makedirs(dst, exist_ok=True)
    print("下载 %s -> %s\n" % (repo, dst))

    got_any = False
    for fn in FILES:
        out = os.path.join(dst, fn)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            print("  已存在，跳过: %s" % fn)
            got_any = True
            continue
        for attempt in range(1, 9):
            try:
                r = requests.get(base + fn, allow_redirects=True, timeout=120, stream=True)
                if r.status_code == 404:
                    print("  跳过 (该模型无此文件): %s" % fn)
                    break
                r.raise_for_status()
                size = 0
                with open(out, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                        size += len(chunk)
                print("  完成: %s (%.1f MB)" % (fn, size / 1e6))
                got_any = True
                break
            except Exception as e:  # noqa
                print("    重试 %s (%d/8): %s" % (fn, attempt, type(e).__name__))
                if os.path.exists(out):
                    os.remove(out)
                time.sleep(2)
        else:
            print("  [失败] %s —— 请检查网络后重跑本脚本 (已下载文件会跳过)" % fn)

    if got_any and os.path.exists(os.path.join(dst, "model.bin")):
        print("\n下载完成。现在可运行: python transcribe.py --model %s" % model)
    else:
        print("\n下载未完成 (缺 model.bin)，请重跑本脚本。")


def main():
    p = argparse.ArgumentParser(description="下载 faster-whisper 模型到本地")
    p.add_argument("model", help="模型名: " + ", ".join(REPOS))
    p.add_argument("--mirror", default="https://hf-mirror.com",
                   help="镜像地址 (默认 hf-mirror.com，可改为 https://huggingface.co)")
    p.add_argument("--out", default="models", help="模型保存根目录")
    args = p.parse_args()
    download(args.model, args.mirror, args.out)


if __name__ == "__main__":
    main()
