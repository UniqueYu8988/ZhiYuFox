# -*- coding: utf-8 -*-
"""CLI 和 GUI 共用的业务流程。"""

from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Callable

import audio_fallback
import bilibili_api
import config
import exporter
import groq_client
import minimax_client


ProgressCallback = Callable[[str, int], None]


@dataclass
class SaveOptions:
    generate_summary: bool = True


@dataclass
class SaveResult:
    bvid: str
    video_title: str
    publish_date: str
    output_dir: str
    markdown_path: str
    file_generated: bool
    summary: str
    has_subtitles: bool
    subtitle_group_count: int
    subtitle_entry_count: int
    ai_skipped_reason: str
    result_note: str
    subtitle_source_type: str
    subtitle_source_api: str
    subtitle_note: str
    text_source_type: str
    text_source_note: str
    page_count: int
    pages_with_subtitles: int
    missing_subtitle_pages: list[str]


def _emit(progress_callback: ProgressCallback | None, message: str, percent: int) -> None:
    if progress_callback:
        progress_callback(message, percent)
    else:
        print(message)


def _resolve_login_status() -> tuple[bool, str]:
    settings = config.get_runtime_settings()
    sessdata = settings.get("sessdata", "").strip()
    if sessdata:
        ok, message = bilibili_api.validate_sessdata(sessdata)
        return ok, message
    return True, "当前按未登录方式运行。"


def _count_subtitle_entries(subtitles: list[dict]) -> tuple[int, bool]:
    entry_count = 0
    for subtitle in subtitles:
        entry_count += len(subtitle.get("entries") or [])
    return entry_count, entry_count > 0


def _page_number_from_label(label: str) -> int:
    if not label:
        return 0
    digits = "".join(ch for ch in label.split("：", 1)[0] if ch.isdigit())
    return int(digits or 0)


def _merge_page_subtitles(base_subtitles: list[dict], extra_subtitles: list[dict]) -> list[dict]:
    if not extra_subtitles:
        return base_subtitles

    merged = [dict(item) for item in base_subtitles]
    if not merged:
        return extra_subtitles

    target = None
    for subtitle in merged:
        if bilibili_api._is_chinese_subtitle(subtitle):  # type: ignore[attr-defined]
            target = subtitle
            break
    if target is None:
        target = merged[0]

    target_segments = [dict(item) for item in (target.get("page_segments") or [])]
    if not target_segments and (target.get("entries") or []):
        target_segments.append(
            {
                "page": 1,
                "label": "P1：原始内容",
                "entries": target.get("entries") or [],
            }
        )
    existing_labels = {item.get("label", "") for item in target_segments}

    for subtitle in extra_subtitles:
        for segment in subtitle.get("page_segments") or []:
            label = segment.get("label", "")
            if label and label in existing_labels:
                continue
            target_segments.append(
                {
                    "page": segment.get("page", _page_number_from_label(label)),
                    "label": label,
                    "entries": segment.get("entries") or [],
                }
            )
            if label:
                existing_labels.add(label)

    target_segments.sort(key=lambda item: int(item.get("page") or _page_number_from_label(str(item.get("label", ""))) or 0))
    target["page_segments"] = target_segments
    target["entries"] = [entry for segment in target_segments for entry in (segment.get("entries") or [])]
    if extra_subtitles and target.get("lang"):
        target["lang"] = "中文（字幕+转写）"
        target["lan"] = "zh-hans"
    return merged


def save_bilibili_video(
    video_input: str,
    options: SaveOptions | None = None,
    progress_callback: ProgressCallback | None = None,
) -> SaveResult:
    options = options or SaveOptions()

    config.ensure_output_dir()
    bilibili_api.refresh_session_headers()

    bvid = bilibili_api.extract_bvid(video_input)
    _emit(progress_callback, f"已识别视频：{bvid}", 8)

    video_info = bilibili_api.get_video_info(bvid)
    _emit(progress_callback, f"标题：{video_info['title']}", 16)

    login_ok, login_message = _resolve_login_status()
    _emit(progress_callback, f"B站登录检测：{login_message}", 22)
    if not login_ok:
        _emit(progress_callback, "当前未使用有效登录，部分字幕接口可能受限。", 26)

    if hasattr(bilibili_api, "get_subtitles_bundle"):
        subtitle_bundle = bilibili_api.get_subtitles_bundle(video_info)
        subtitles = subtitle_bundle["subtitles"]
        subtitle_source_type = subtitle_bundle["source_type"]
        subtitle_source_api = subtitle_bundle["source_api"]
        subtitle_note = subtitle_bundle["note"]
        page_count = int(subtitle_bundle.get("page_count") or len(video_info.get("pages") or []) or 1)
        pages_with_subtitles = int(subtitle_bundle.get("pages_with_subtitles") or 0)
        missing_subtitle_pages = [item.get("label", "") for item in subtitle_bundle.get("pages_without_subtitles") or [] if item.get("label")]
    else:
        subtitles = bilibili_api.get_subtitles(video_info["aid"], video_info["cid"])
        subtitle_source_type = "已获取字幕" if subtitles else "未获取到字幕"
        subtitle_source_api = "get_subtitles"
        subtitle_note = "当前版本未提供更详细的字幕来源说明。"
        page_count = 1
        pages_with_subtitles = 1 if subtitles else 0
        missing_subtitle_pages = []

    subtitle_entry_count, has_subtitles = _count_subtitle_entries(subtitles)
    _emit(progress_callback, f"字幕获取完成，共 {len(subtitles)} 组", 34)
    _emit(progress_callback, f"字幕来源：{subtitle_source_type}（{subtitle_source_api}）。{subtitle_note}", 40)
    if missing_subtitle_pages:
        _emit(progress_callback, f"未获取到字幕的分P：{'；'.join(missing_subtitle_pages)}", 44)

    text_source_type = subtitle_source_type
    text_source_note = subtitle_note

    pages_to_transcribe: list[dict] = []
    if video_info.get("pages"):
        for page in video_info["pages"]:
            page_label = f"P{int(page.get('page') or 1)}：{str(page.get('part') or '').strip() or f'P{int(page.get('page') or 1)}'}"
            if (not has_subtitles) or (page_label in missing_subtitle_pages):
                pages_to_transcribe.append(
                    {
                        "page": int(page.get("page") or 1),
                        "part": str(page.get("part") or "").strip(),
                        "label": page_label,
                    }
                )

    if pages_to_transcribe and groq_client.has_api_key():
        _emit(progress_callback, "未获取到完整字幕，准备切换方案2：音频转写补全。", 48)
        _emit(progress_callback, "方案2 需要额外下载和转写音频，耗时会更久，请耐心等待。", 52)
        transcription_bundle = audio_fallback.transcribe_video_pages(
            video_info,
            pages_to_transcribe,
            progress_callback=progress_callback,
        )
        if transcription_bundle.subtitles:
            subtitles = _merge_page_subtitles(subtitles, transcription_bundle.subtitles)
            subtitle_entry_count, has_subtitles = _count_subtitle_entries(subtitles)
            transcribed_labels = {
                segment.get("label", "")
                for subtitle in transcription_bundle.subtitles
                for segment in (subtitle.get("page_segments") or [])
                if segment.get("label")
            }
            missing_subtitle_pages = [label for label in missing_subtitle_pages if label not in transcribed_labels]
            pages_with_subtitles = page_count - len(missing_subtitle_pages)
            text_source_type = (
                "字幕 + Groq 音频转写" if subtitle_source_type != "未获取到字幕" else transcription_bundle.source_type
            )
            text_source_note = transcription_bundle.note
            subtitle_source_type = text_source_type
            subtitle_source_api = transcription_bundle.source_api
            subtitle_note = text_source_note
            _emit(progress_callback, f"方案2 已补全 {transcription_bundle.pages_transcribed} 个分P。", 88)
        else:
            _emit(progress_callback, "方案2 未转写出可用文本，仍将按无字幕处理。", 88)
            text_source_type = "未获取到可用文本"
            text_source_note = transcription_bundle.note
    elif pages_to_transcribe and not groq_client.has_api_key():
        missing_hint = "未配置 Groq API Key，无字幕时无法启用音频转写方案。"
        _emit(progress_callback, missing_hint, 48)
        text_source_type = "仅官方字幕" if has_subtitles else "未获取到可用文本"
        text_source_note = missing_hint if has_subtitles else "未获取到字幕，且未配置 Groq API Key。"

    summary = ""
    ai_skipped_reason = ""
    result_note = ""
    if options.generate_summary and minimax_client.has_api_key():
        if has_subtitles:
            _emit(progress_callback, "正在生成 AI 视频总结...", 92)
            summary = minimax_client.generate_summary(
                {
                    "video_info": video_info,
                    "subtitles": subtitles,
                }
            )
            _emit(progress_callback, "AI 视频总结生成完成", 96)
        else:
            ai_skipped_reason = "未检测到可用字幕，已跳过 AI 视频总结。"
            _emit(progress_callback, ai_skipped_reason, 96)
    elif options.generate_summary:
        ai_skipped_reason = "未检测到 MiniMax API Key，跳过 AI 视频总结。"
        _emit(progress_callback, ai_skipped_reason, 96)

    output_dir = config.get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    publish_date = time.strftime("%Y-%m-%d", time.localtime(video_info["pubdate"]))
    markdown_path = ""

    if not has_subtitles:
        result_note = "未检测到可用字幕，未生成 Markdown 文件。"
        _emit(progress_callback, result_note, 100)
        return SaveResult(
            bvid=bvid,
            video_title=video_info["title"],
            publish_date=publish_date,
            output_dir=output_dir,
            markdown_path=markdown_path,
            file_generated=False,
            summary=summary,
            has_subtitles=has_subtitles,
            subtitle_group_count=len(subtitles),
            subtitle_entry_count=subtitle_entry_count,
            ai_skipped_reason=ai_skipped_reason,
            result_note=result_note,
            subtitle_source_type=subtitle_source_type,
            subtitle_source_api=subtitle_source_api,
            subtitle_note=subtitle_note,
            text_source_type=text_source_type,
            text_source_note=text_source_note,
            page_count=page_count,
            pages_with_subtitles=pages_with_subtitles,
            missing_subtitle_pages=missing_subtitle_pages,
        )

    full_data = {
        "video_info": video_info,
        "subtitles": subtitles,
        "summary": summary,
        "meta": {
            "tool": "BiliArchive",
            "bvid": bvid,
            "login_ok": login_ok,
            "login_message": login_message,
            "has_subtitles": has_subtitles,
            "subtitle_group_count": len(subtitles),
            "subtitle_entry_count": subtitle_entry_count,
            "ai_skipped_reason": ai_skipped_reason,
            "result_note": result_note,
            "subtitle_source_type": subtitle_source_type,
            "subtitle_source_api": subtitle_source_api,
            "subtitle_note": subtitle_note,
            "text_source_type": text_source_type,
            "text_source_note": text_source_note,
            "page_count": page_count,
            "pages_with_subtitles": pages_with_subtitles,
            "missing_subtitle_pages": missing_subtitle_pages,
        },
    }

    safe_title = config.sanitize_filename(video_info["title"])
    markdown_path = os.path.join(output_dir, f"{safe_title}_{bvid}.md")

    _emit(progress_callback, f"正在导出 Markdown 到：{output_dir}", 98)
    exporter.export_markdown(full_data, markdown_path)
    _emit(progress_callback, "Markdown 已导出", 99)

    _emit(progress_callback, "保存完成", 100)
    return SaveResult(
        bvid=bvid,
        video_title=video_info["title"],
        publish_date=publish_date,
        output_dir=output_dir,
        markdown_path=markdown_path,
        file_generated=True,
        summary=summary,
        has_subtitles=has_subtitles,
        subtitle_group_count=len(subtitles),
        subtitle_entry_count=subtitle_entry_count,
        ai_skipped_reason=ai_skipped_reason,
        result_note=result_note,
        subtitle_source_type=subtitle_source_type,
        subtitle_source_api=subtitle_source_api,
        subtitle_note=subtitle_note,
        text_source_type=text_source_type,
        text_source_note=text_source_note,
        page_count=page_count,
        pages_with_subtitles=pages_with_subtitles,
        missing_subtitle_pages=missing_subtitle_pages,
    )
