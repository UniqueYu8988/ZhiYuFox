# -*- coding: utf-8 -*-
"""CLI 和 GUI 共用的业务流程。"""

from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Callable

import bilibili_api
import config
import exporter
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


def save_bilibili_video(
    video_input: str,
    options: SaveOptions | None = None,
    progress_callback: ProgressCallback | None = None,
) -> SaveResult:
    options = options or SaveOptions()

    config.ensure_output_dir()
    bilibili_api.refresh_session_headers()

    bvid = bilibili_api.extract_bvid(video_input)
    _emit(progress_callback, f"已识别视频：{bvid}", 5)

    video_info = bilibili_api.get_video_info(bvid)
    _emit(progress_callback, f"标题：{video_info['title']}", 12)

    login_ok, login_message = _resolve_login_status()
    _emit(progress_callback, f"B站登录检测：{login_message}", 18)
    if not login_ok:
        _emit(progress_callback, "当前未使用有效登录，部分字幕接口可能受限。", 24)

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
    _emit(progress_callback, f"字幕获取完成，共 {len(subtitles)} 组", 35)
    _emit(progress_callback, f"字幕来源：{subtitle_source_type}（{subtitle_source_api}）。{subtitle_note}", 42)
    if missing_subtitle_pages:
        _emit(progress_callback, f"未获取到字幕的分P：{'；'.join(missing_subtitle_pages)}", 46)

    summary = ""
    ai_skipped_reason = ""
    result_note = ""
    if options.generate_summary and minimax_client.has_api_key():
        if has_subtitles:
            _emit(progress_callback, "正在生成 AI 视频总结...", 60)
            summary = minimax_client.generate_summary(
                {
                    "video_info": video_info,
                    "subtitles": subtitles,
                }
            )
            _emit(progress_callback, "AI 视频总结生成完成", 82)
        else:
            ai_skipped_reason = "未检测到可用字幕，已跳过 AI 视频总结。"
            _emit(progress_callback, ai_skipped_reason, 82)
    elif options.generate_summary:
        ai_skipped_reason = "未检测到 MiniMax API Key，跳过 AI 视频总结。"
        _emit(progress_callback, ai_skipped_reason, 82)

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
            "page_count": page_count,
            "pages_with_subtitles": pages_with_subtitles,
            "missing_subtitle_pages": missing_subtitle_pages,
        },
    }

    safe_title = config.sanitize_filename(video_info["title"])
    markdown_path = os.path.join(output_dir, f"{safe_title}_{bvid}.md")

    _emit(progress_callback, f"正在导出 Markdown 到：{output_dir}", 90)
    exporter.export_markdown(full_data, markdown_path)
    _emit(progress_callback, "Markdown 已导出", 96)

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
        page_count=page_count,
        pages_with_subtitles=pages_with_subtitles,
        missing_subtitle_pages=missing_subtitle_pages,
    )
