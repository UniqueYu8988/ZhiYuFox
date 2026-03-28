# -*- coding: utf-8 -*-
"""导出精简 Markdown。"""

from __future__ import annotations

import os
import sys
import time


def _log(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write((message + "\n").encode("gbk", errors="replace"))
        else:
            print(message.encode("ascii", errors="replace").decode("ascii"))


def export_markdown(data: dict, filepath: str) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    video = data["video_info"]
    summary = data.get("summary", "").strip()

    lines: list[str] = []
    lines.append(f"# {video['title']}")
    lines.append("")
    lines.append(f"📅 日期：{time.strftime('%Y-%m-%d', time.localtime(video['pubdate']))}")
    lines.append("")
    lines.append(summary or "🪄 未生成内容摘要。若要启用，请先配置 MiniMax API Key。")

    with open(filepath, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))
    _log(f"Markdown 已保存: {filepath}")
