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
    summary: str
    subtitle_source_type: str
    subtitle_source_api: str
    subtitle_note: str


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
        subtitle_bundle = bilibili_api.get_subtitles_bundle(video_info["aid"], video_info["cid"])
        subtitles = subtitle_bundle["subtitles"]
        subtitle_source_type = subtitle_bundle["source_type"]
        subtitle_source_api = subtitle_bundle["source_api"]
        subtitle_note = subtitle_bundle["note"]
    else:
        subtitles = bilibili_api.get_subtitles(video_info["aid"], video_info["cid"])
        subtitle_source_type = "已获取字幕" if subtitles else "未获取到字幕"
        subtitle_source_api = "get_subtitles"
        subtitle_note = "当前版本未提供更详细的字幕来源说明。"
    _emit(progress_callback, f"字幕获取完成，共 {len(subtitles)} 组", 35)
    _emit(progress_callback, f"字幕来源：{subtitle_source_type}（{subtitle_source_api}）。{subtitle_note}", 42)

    summary = ""
    if options.generate_summary and minimax_client.has_api_key():
        _emit(progress_callback, "正在生成 AI 视频总结...", 60)
        summary = minimax_client.generate_summary(
            {
                "video_info": video_info,
                "subtitles": subtitles,
            }
        )
        _emit(progress_callback, "AI 视频总结生成完成", 82)
    elif options.generate_summary:
        _emit(progress_callback, "未检测到 MiniMax API Key，跳过 AI 视频总结", 82)

    full_data = {
        "video_info": video_info,
        "subtitles": subtitles,
        "summary": summary,
        "meta": {
            "tool": "BiliArchive",
            "bvid": bvid,
            "login_ok": login_ok,
            "login_message": login_message,
            "subtitle_source_type": subtitle_source_type,
            "subtitle_source_api": subtitle_source_api,
            "subtitle_note": subtitle_note,
        },
    }

    safe_title = config.sanitize_filename(video_info["title"])
    output_dir = config.get_output_dir()
    os.makedirs(output_dir, exist_ok=True)

    markdown_path = os.path.join(output_dir, f"{safe_title}_{bvid}.md")
    publish_date = time.strftime("%Y-%m-%d", time.localtime(video_info["pubdate"]))

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
        summary=summary,
        subtitle_source_type=subtitle_source_type,
        subtitle_source_api=subtitle_source_api,
        subtitle_note=subtitle_note,
    )
