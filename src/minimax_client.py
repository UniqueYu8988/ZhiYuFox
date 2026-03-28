# -*- coding: utf-8 -*-
"""MiniMax OpenAI 兼容接口客户端。"""

from __future__ import annotations

import json
import re
import time

import requests

import config


AD_MARKERS = (
    "本期视频由",
    "本视频由",
    "感谢",
    "赞助播出",
    "合作推广",
    "广告",
    "恰饭",
    "下单",
    "购买",
    "优惠",
    "折扣",
    "券",
    "链接",
    "点击",
    "种草",
    "安利",
    "推荐给大家",
    "推荐大家",
    "入手",
    "开箱",
    "体验一下",
    "戴上",
    "佩戴",
    "智能手表",
    "无感",
    "风险评估",
    "趋势监测",
    "预警提示",
    "PPG",
    "IMU",
)

AD_BRANDS = (
    "OPPO",
    "小米",
    "华为",
    "vivo",
    "荣耀",
    "Apple",
    "iPhone",
    "京东",
    "淘宝",
    "天猫",
    "拼多多",
)


def has_api_key() -> bool:
    return bool(config.MINIMAX_API_KEY.strip())


def validate_api_key(api_key: str, model: str) -> tuple[bool, str]:
    api_key = (api_key or "").strip()
    model = (model or "MiniMax-M2.7").strip()
    if not api_key:
        return True, "未填写 MiniMax API Key，将跳过 AI 总结。"

    url = config.MINIMAX_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "请回复：ok"}],
        "temperature": 0.1,
        "max_tokens": 8,
    }

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        if resp.status_code == 401:
            return False, "MiniMax API Key 无效，返回 401。"
        if resp.status_code == 403:
            return False, "MiniMax API Key 无权限，返回 403。"
        if resp.status_code >= 400:
            try:
                payload = resp.json()
                message = payload.get("error", {}).get("message") or payload.get("message")
            except Exception:
                message = resp.text[:200]
            return False, f"MiniMax 检测失败：{message or ('HTTP ' + str(resp.status_code))}"

        payload = resp.json()
        if payload.get("choices"):
            return True, f"MiniMax API Key 有效，模型：{model}"
        return False, "MiniMax 返回结果异常，未发现 choices。"
    except Exception as exc:
        return False, f"MiniMax 检测失败：{exc}"


def _clip(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n...[已截断]"


def _looks_like_ad_line(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return False

    marker_hits = sum(1 for marker in AD_MARKERS if marker in normalized)
    brand_hits = sum(1 for brand in AD_BRANDS if brand.lower() in normalized.lower())

    if marker_hits >= 2:
        return True
    if marker_hits >= 1 and brand_hits >= 1:
        return True
    if brand_hits >= 1 and ("手表" in normalized or "watch" in normalized.lower()):
        return True
    if "手表" in normalized and marker_hits >= 1:
        return True
    return False


def _filter_subtitle_entries(entries: list[dict]) -> list[dict]:
    filtered: list[dict] = []
    skip_until = -1.0

    for entry in entries:
        start = float(entry.get("from", 0.0))
        end = float(entry.get("to", start))
        content = str(entry.get("content", "")).strip()

        if start < skip_until:
            continue

        if _looks_like_ad_line(content):
            # 广告口播通常连续出现在一小段区间里，命中后顺带跳过后续约 25 秒。
            skip_until = end + 25.0
            continue

        filtered.append(entry)

    return filtered


def _build_prompt(data: dict) -> str:
    video = data["video_info"]
    subtitles = data["subtitles"]

    subtitle_chunks: list[str] = []
    for sub in subtitles[:2]:
        filtered_entries = _filter_subtitle_entries(sub["entries"])
        lines = [
            f"[{entry['from']:.1f}-{entry['to']:.1f}] {entry['content']}"
            for entry in filtered_entries[:160]
        ]
        subtitle_chunks.append(f"语言: {sub['lang']}\n" + "\n".join(lines))

    payload = {
        "title": video["title"],
        "publish_date": time.strftime("%Y-%m-%d", time.localtime(video.get("pubdate", 0))),
        "desc": video.get("desc", ""),
        "subtitles_excerpt": _clip("\n\n".join(subtitle_chunks), 14000),
    }

    return (
        "请基于以下 Bilibili 视频标题、发布日期、简介和字幕片段，写一段只围绕视频内容本身的中文 Markdown 分析，"
        "用于整理视频笔记。不要分析评论，不要讨论观众反馈、舆情、热度或互动表现，不要输出代码块。\n\n"
        "请严格使用以下结构：\n"
        "## 🧭 视频主题\n"
        "## 💡 核心内容\n\n"
        "要求：\n"
        "1. 只围绕视频本身讲了什么来写，不要写成空泛的摘要模板。\n"
        "2. “视频主题”要直接说明这个视频主要在讨论什么问题、对象或现象。\n"
        "3. “核心内容”必须按条列出视频具体讲了哪些内容、论点或展开，每一条都尽量补充它使用了什么论据、案例、类比、场景、数据或例子来支撑这些内容。\n"
        "4. 如果字幕里出现了具体人物、事件、产品、案例、实验、对比、数字或原话，请尽量保留这些关键信息，而不是把它们抽象化。\n"
        "5. 如果信息不足，请明确说明是基于有限字幕或简介得出的判断，不要编造细节。\n"
        "6. “核心内容”部分优先使用有层次的条目式写法，可以使用加粗小标题或编号，让结构更清晰。\n"
        "7. 不要输出“总结”或任何额外章节，只保留上面两个标题。\n"
        "8. 明显属于广告、赞助、带货、产品植入、购买引导、功能推荐的内容一律忽略，不要写入“视频主题”或“核心内容”。\n"
        "9. 如果视频中穿插了品牌推荐、硬广、软广、工具推广或口播赞助，请将其视为与主内容无关的噪音，除非视频主题本身就是在评测该产品。\n"
        "10. 不要专门说明你忽略了广告，也不要写出“此处为广告”“此处已忽略”等提示语，直接像它不存在一样处理。\n"
        "11. 语言要具体、朴素、信息密度高，少用空泛评价词，不要拔高，不要重复改写同一个意思。\n\n"
        f"原始材料：\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def generate_summary(data: dict) -> str:
    if not has_api_key():
        return ""

    url = config.MINIMAX_BASE_URL.rstrip("/") + "/chat/completions"
    body = {
        "model": config.MINIMAX_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一个擅长提炼视频具体内容的中文助手。你的任务是忽略广告、赞助、带货和产品植入，只讲清视频主体到底说了什么、用了什么例子和论据，而不是写空泛摘要。",
            },
            {
                "role": "user",
                "content": _build_prompt(data),
            },
        ],
        "temperature": 0.25,
    }
    headers = {
        "Authorization": f"Bearer {config.MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    payload = resp.json()
    content = payload["choices"][0]["message"]["content"].strip()
    content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL)
    content = re.sub(r"^##\s*💡\s*核心观点", "## 💡 核心内容", content, flags=re.MULTILINE)
    content = re.sub(r"^##\s*核心观点", "## 💡 核心内容", content, flags=re.MULTILINE)
    return content.strip()
