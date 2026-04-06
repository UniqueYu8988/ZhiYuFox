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


def _format_yaml_tag(tag: str) -> str:
    clean = (tag or "").strip()
    if not clean:
        return ""
    if any(char in clean for char in [":", "[", "]", "{", "}", ",", "#", '"', "'"]):
        return json.dumps(clean, ensure_ascii=False)
    return clean


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
        formatted_tags = [_format_yaml_tag(tag) for tag in tags if _format_yaml_tag(tag)]
        lines.append(f"tags: [{', '.join(formatted_tags)}]" if formatted_tags else "tags: []")
    else:
        lines.append("tags: []")
    lines.append("---")
    lines.append("")

    meta = data.get("meta") or {}
    text_source_type = str(meta.get("text_source_type") or meta.get("subtitle_source_type") or "").strip()
    text_source_note = str(meta.get("text_source_note") or meta.get("subtitle_note") or "").strip()
    missing_pages = meta.get("missing_subtitle_pages") or []
    show_text_note = bool(missing_pages)
    if show_text_note and (text_source_type or missing_pages):
        lines.append("> [!note] 文本说明")
        if text_source_type:
            lines.append(f"> 文本来源：{text_source_type}")
        if text_source_note:
            lines.append(f"> {text_source_note}")
        if missing_pages:
            lines.append(
                f"> 本次仍有 {len(missing_pages)} 个分P未参与总结："
            )
            for label in missing_pages:
                lines.append(f"> - {label}")
        lines.append("")

    lines.append(body or "🪄 未生成内容摘要。若要启用，请先配置 MiniMax API Key。")

    with open(filepath, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))
    _log(f"Markdown 已保存: {filepath}")
