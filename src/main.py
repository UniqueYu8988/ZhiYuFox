# -*- coding: utf-8 -*-
"""CLI / GUI 入口。"""

from __future__ import annotations

import argparse
import json
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="知语狸：Bilibili 内容归档工具")
    parser.add_argument("video", nargs="?", help="BV 号或视频链接")
    parser.add_argument("--no-ai", action="store_true", help="不生成 AI 总结")
    parser.add_argument("--gui", action="store_true", help="启动图形界面")
    parser.add_argument("--result-json", action="store_true", help=argparse.SUPPRESS)
    return parser


def launch_gui() -> int:
    from gui_qt import run_gui

    run_gui()
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.gui:
        return launch_gui()

    if not args.video:
        parser.error("请提供 BV 号或视频链接，或者使用 --gui。")

    from app_service import SaveOptions, save_bilibili_video

    result = save_bilibili_video(
        args.video,
        options=SaveOptions(
            generate_summary=not args.no_ai,
        ),
    )

    print("=" * 60)
    print(f"标题: {result.video_title}")
    print(f"日期: {result.publish_date}")
    print(f"输出目录: {result.output_dir}")
    print(f"Markdown: {result.markdown_path}")
    if args.result_json:
        print(
            "__BILIARCHIVE_RESULT__="
            + json.dumps(
                {
                    "videoTitle": result.video_title,
                    "publishDate": result.publish_date,
                    "outputDir": result.output_dir,
                    "markdownPath": result.markdown_path,
                },
                ensure_ascii=False,
            )
        )
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
