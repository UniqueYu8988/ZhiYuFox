# -*- coding: utf-8 -*-
"""导出精简 Markdown。"""

from __future__ import annotations

import json
import os
import re
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


def _extract_tags_and_body(summary: str) -> tuple[list[str], str]:
    text = (summary or "").strip()
    if not text:
        return [], ""

    lines = text.splitlines()
    first_nonempty_index = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first_nonempty_index is None:
        return [], ""

    first_line = lines[first_nonempty_index].strip()
    match = re.match(r"^\[TAGS\]\s*(.+)$", first_line, flags=re.IGNORECASE)
    if not match:
        return [], text

    raw_tags = re.split(r"[，,、/\|]+", match.group(1))
    tags: list[str] = []
    for tag in raw_tags:
        clean = tag.strip().strip("#").strip()
        if clean and clean not in tags:
            tags.append(clean)
        if len(tags) >= 2:
            break

    body_lines = lines[:first_nonempty_index] + lines[first_nonempty_index + 1 :]
    body = "\n".join(body_lines).strip()
    return tags, body


def export_markdown(data: dict, filepath: str) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    video = data["video_info"]
    summary = data.get("summary", "").strip()
    tags, body = _extract_tags_and_body(summary)

    lines: list[str] = []
    lines.append("---")
    lines.append(f"title: {json.dumps(video['title'], ensure_ascii=False)}")
    lines.append(f"date: {time.strftime('%Y-%m-%d', time.localtime(video['pubdate']))}")
    if tags:
        lines.append(f"tags: [{', '.join(json.dumps(tag, ensure_ascii=False) for tag in tags)}]")
    else:
        lines.append("tags: []")
    lines.append("---")
    lines.append("")

    meta = data.get("meta") or {}
    missing_pages = meta.get("missing_subtitle_pages") or []
    if missing_pages:
        lines.append("> [!note] 字幕说明")
        lines.append(
            f"> 本次仅获取到 {meta.get('pages_with_subtitles', 0)}/{meta.get('page_count', len(missing_pages))} 个分P的字幕。"
        )
        lines.append("> 未参与总结的分P：")
        for label in missing_pages:
            lines.append(f"> - {label}")
        lines.append("")

    lines.append(body or "🪄 未生成内容摘要。若要启用，请先配置 MiniMax API Key。")

    with open(filepath, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))
    _log(f"Markdown 已保存: {filepath}")
