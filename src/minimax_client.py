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

MAX_SUBTITLE_TRACKS = 2


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


def _subtitle_priority(subtitle: dict) -> tuple[int, str]:
    lang = str(subtitle.get("lang") or "").lower()
    land = str(subtitle.get("land") or "").lower()
    joined = f"{lang} {land}"

    if any(keyword in joined for keyword in ("zh", "中文", "汉语", "国语", "简体", "繁體", "繁体")):
        return (0, joined)
    if "en" in joined or "english" in joined:
        return (1, joined)
    return (2, joined)


def _select_subtitle_tracks(subtitles: list[dict]) -> list[dict]:
    if not subtitles:
        return []

    ordered = sorted(subtitles, key=_subtitle_priority)
    best_priority = _subtitle_priority(ordered[0])[0]

    if best_priority == 0:
        return [ordered[0]]

    return ordered[:MAX_SUBTITLE_TRACKS]


def _build_prompt(data: dict) -> str:
    video = data["video_info"]
    subtitles = _select_subtitle_tracks(data["subtitles"])
    pages = video.get("pages") or []
    has_multi_page = len(pages) > 1

    subtitle_chunks: list[str] = []
    for sub in subtitles:
        page_segments = sub.get("page_segments") or []
        lines: list[str] = []
        if page_segments:
            for segment in page_segments:
                segment_entries = _filter_subtitle_entries(segment.get("entries") or [])
                if not segment_entries:
                    continue
                lines.append(f"【{segment.get('label', '未命名分P')}】")
                lines.extend(
                    f"[{entry['from']:.1f}-{entry['to']:.1f}] {entry['content']}"
                    for entry in segment_entries
                )
        else:
            filtered_entries = _filter_subtitle_entries(sub["entries"])
            lines = [
                f"[{entry['from']:.1f}-{entry['to']:.1f}] {entry['content']}"
                for entry in filtered_entries
            ]
        subtitle_chunks.append(f"语言: {sub['lang']}\n" + "\n".join(lines))

    payload = {
        "title": video["title"],
        "publish_date": time.strftime("%Y-%m-%d", time.localtime(video.get("pubdate", 0))),
        "category": video.get("tname", ""),
        "desc": video.get("desc", ""),
        "page_count": len(pages) or 1,
        "page_outline": [
            {
                "page": page.get("page"),
                "part": page.get("part", ""),
            }
            for page in pages
        ],
        "subtitle_strategy": "优先选择中文字幕；尽量保留完整字幕；明显广告字幕已尽量过滤。",
        "subtitles_excerpt": "\n\n".join(subtitle_chunks),
    }

    return (
        "请只基于以下视频标题、发布日期、简介和字幕片段，整理一份中文 Markdown 正文。\n"
        "当前文档的标题和日期会由程序写入。你需要额外给出 2 个简短 tag，但 tag 不能出现在正文段落里，而是单独放在程序可解析的标记行中。\n"
        "你绝对不要重复输出标题、日期、front matter、引言、问候语或总结段落。\n\n"
        "【严格执行规则】\n"
        "1. 你是一个极度严谨的视频干货提取机，只负责穿透废话，提取视频主体到底讲了什么事实、用了什么论据。\n"
        "2. 零废话原则：禁止输出“总而言之”“在这个视频中”“视频最后总结道”等包装性废话。\n"
        "3. 细节至上：禁止抽象化和空泛总结，必须优先保留具体数据、案例、类比、场景、关键数字和有价值的原话。\n"
        "4. 广告免疫：明显属于广告、赞助、带货、产品植入、购买引导、功能推荐的内容必须静默忽略，绝对不要写“这里忽略了广告”等提示。\n"
        "5. 不要扩展到评论区、观众反馈、舆情、热度或任何未提供的信息。\n"
        "6. 如果信息不足，可以明确说“字幕信息有限”或“依据有限字幕判断”，但不要编造细节。\n"
        "7. 语言风格要客观、冷静、信息密度高，少用形容词，不要重复改写同一个意思。\n"
        "8. 目标是高密度提炼，不是逐段复述字幕。请优先保留最值得记下来的信息，不要为了完整而把同类内容拆成很多重复要点。\n"
        "9. 相近观点、重复举例、同一结论的多次铺垫要主动合并，只留下最有解释力的论据、案例、数字或原话。\n"
        "10. 当视频内容很多时，优先输出最关键、最有信息量的 4-8 条要点；不要因为材料更长就无限增加条目数量。\n"
        "11. 每条要点尽量遵循“观点在前，证据在后”的写法，先说明结论，再补充支撑它的事实、案例、数据或类比。\n\n"
        "12. 请根据标题、简介、分区和字幕内容，自行判断它更像评论、教学、新闻、vlog、访谈、评测或其他类型，并据此调整提炼方式；不要被预设模板限制。\n\n"
        "13. 每个条目尽量以 `- **短导语：**` 开头，短导语控制在 2-8 个字，让阅读时一眼能扫到重点。\n"
        "14. 如果内容明显是教程、教学、实操演示，优先整理准备条件、关键步骤、核心方法、常见问题、注意事项和作者建议，不要写成泛泛介绍。\n"
        f"15. {'当前视频是多分P结构。请在同一个文档里保留分P层次，在 `### ✨ 主要内容` 下按 `#### P1 标题`、`#### P2 标题` 这样的子标题分段，再在每个分P下面写 1-3 条带加粗导语的重点。不要把所有分P混成一整串总列表。' if has_multi_page else '当前视频不是多分P结构，`### ✨ 主要内容` 下直接用带加粗导语的条列即可。'}\n\n"
        "【强制输出结构】\n"
        "请严格且仅使用以下 Markdown 结构输出：\n"
        "[TAGS] tag1, tag2\n"
        "### 💡 视频主题\n"
        "（用 1-2 句话直接说明这个视频到底在探讨或解决什么问题。）\n\n"
        "### ✨ 主要内容\n"
        "（用条列方式整理视频干货。优先输出高密度内容，每一个核心点都必须尽量附带字幕中的事实、例子、数字、类比或原话作为支撑。）\n\n"
        "tag 要求：\n"
        "1. 只给 2 个 tag。\n"
        "2. tag 要简短，尽量是 2-6 个字的主题词或领域词，不要写成长句。\n"
        "3. 不要带井号，不要写解释，不要超过 2 个。\n"
        "4. 尽量避免空泛口号词，优先使用能概括主题的稳定名词。\n"
        "5. 除了开头这一行 [TAGS]，不要在正文其他位置重复 tag。\n\n"
        "除了这条 [TAGS] 行、两个标题和它们下面的正文，不要输出任何其他章节。\n\n"
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
                "content": "你是一个极度严谨的视频干货提取机。你的唯一任务是穿透所有废话、广告、赞助、带货和产品植入，精准提取视频主体到底讲了什么事实、用了什么论据。你极度讨厌空泛总结和套话，只关心具体数据、案例、类比和原话。",
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
    content = re.sub(r"^##\s*🧭\s*视频主题", "### 💡 视频主题", content, flags=re.MULTILINE)
    content = re.sub(r"^##\s*💡\s*核心内容", "### ✨ 主要内容", content, flags=re.MULTILINE)
    content = re.sub(r"^##\s*💡\s*核心观点", "### ✨ 主要内容", content, flags=re.MULTILINE)
    content = re.sub(r"^##\s*核心观点", "### ✨ 主要内容", content, flags=re.MULTILINE)
    content = re.sub(r"^##\s*核心内容", "### ✨ 主要内容", content, flags=re.MULTILINE)
    content = re.sub(r"^###\s*核心内容", "### ✨ 主要内容", content, flags=re.MULTILINE)
    content = re.sub(r"^###\s*视频主题", "### 💡 视频主题", content, flags=re.MULTILINE)
    return content.strip()
