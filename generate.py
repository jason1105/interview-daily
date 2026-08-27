#!/usr/bin/env python3
"""
Daily Interview Question Generator
每天从热门技术岗位中选一个，生成一道面试题并详细拆解。
"""

import json
import os
import sys
from datetime import datetime, timezone

try:
    from openai import OpenAI
except ImportError:
    os.system(f"{sys.executable} -m pip install openai -q")
    from openai import OpenAI

# ── 配置 ─────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")
MODEL = os.environ.get("LLM_MODEL") or os.environ.get("MODEL") or "deepseek-v4-flash"

# 技术岗位轮转列表
ROLES = [
    {"name": "后端工程师", "tags": ["系统设计", "数据库", "并发", "API设计"]},
    {"name": "前端工程师", "tags": ["JavaScript", "性能优化", "浏览器原理", "React/Vue"]},
    {"name": "全栈工程师", "tags": ["前后端协作", "API设计", "数据库", "部署"]},
    {"name": "数据工程师", "tags": ["数据管道", "SQL", "大数据", "ETL"]},
    {"name": "机器学习工程师", "tags": ["模型训练", "特征工程", "部署推理", "评估指标"]},
    {"name": "DevOps工程师", "tags": ["CI/CD", "容器化", "监控", "基础设施即代码"]},
    {"name": "算法工程师", "tags": ["数据结构", "算法设计", "复杂度分析", "动态规划"]},
    {"name": "移动端工程师", "tags": ["iOS/Android", "性能优化", "跨平台", "UI交互"]},
    {"name": "安全工程师", "tags": ["漏洞分析", "加密算法", "渗透测试", "安全架构"]},
    {"name": "架构师", "tags": ["分布式系统", "微服务", "高可用", "技术选型"]},
]

PRACTICE_URLS = {
    "算法": "https://leetcode.cn/problemset/",
    "系统设计": "https://github.com/donnemartin/system-design-primer",
    "数据库": "https://sqlzoo.net/",
    "JavaScript": "https://javascript.info/",
    "数据结构": "https://leetcode.cn/problemset/",
    "default": "https://github.com/jwasham/coding-interview-university",
}

PROMPT_TEMPLATE = """你是一位资深技术面试官，请为【{role}】岗位生成今日面试题。

要求：
1. 题目要贴近真实面试场景，难度适中（不要太简单也不要过于偏门）
2. 按以下 JSON 格式严格输出，不要输出任何其他内容

{{
  "question": "面试题目（1-3句话，清晰描述问题）",
  "type": "题目类型（算法/系统设计/数据库/项目经验/行为面试/语言特性/框架原理 之一）",
  "difficulty": "难度（简单/中等/困难 之一）",
  "tags": ["标签1", "标签2"],
  "breakdown": {{
    "focus": "考察点（这道题主要考察什么，2-3个要点）",
    "framework": "答题框架（分步骤说明如何系统地回答这道题，列出3-5个步骤）",
    "example": "高分答案示例（给出一个完整、高质量的参考答案，不少于200字）",
    "pitfalls": "常见误区（列出2-3个面试者容易犯的错误）",
    "followup": "追问方向（面试官可能会继续追问的2-3个问题）"
  }}
}}"""


def generate_question(role_info: dict, date_str: str) -> dict:
    """调用 OpenRouter 生成面试题"""
    client = OpenAI(
        base_url=os.environ.get("LLM_BASE_URL") or "https://api.deepseek.com",
        api_key=OPENROUTER_API_KEY,
    )

    prompt = PROMPT_TEMPLATE.format(role=role_info["name"])

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        extra_headers={
            "HTTP-Referer": "https://jason1105.github.io/interview-daily",
            "X-Title": "Interview Daily",
        },
    )

    raw = response.choices[0].message.content.strip()

    # 稳健提取 JSON：不同模型可能包 markdown 围栏、加前言/思维链，
    # 或直接返回裸对象。统一抓取第一个完整的 {...} 再解析。
    def _extract_json(text):
        import re
        # 先剥 markdown 代码块
        m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
        if m:
            text = m.group(1).strip()
        # 再抓第一个 { 到最后一个 } 之间的内容
        i, j = text.find("{"), text.rfind("}")
        if i != -1 and j != -1 and j > i:
            return text[i:j+1]
        return text

    cleaned = _extract_json(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        print("❌ 无法解析模型输出为 JSON。原始输出前 500 字符：", file=sys.stderr)
        print(repr(raw[:500]), file=sys.stderr)
        raise
    data["date"] = date_str
    data["role"] = role_info["name"]

    # 添加练习链接
    question_type = data.get("type", "default")
    data["practice_url"] = PRACTICE_URLS.get(question_type, PRACTICE_URLS["default"])

    return data


def main():
    if not OPENROUTER_API_KEY:
        print("❌ 缺少 LLM_API_KEY / OPENROUTER_API_KEY 环境变量")
        sys.exit(1)

    today = datetime.now(timezone.utc)
    date_str = today.strftime("%Y-%m-%d")

    # 按天轮转岗位
    day_of_year = today.timetuple().tm_yday
    role_info = ROLES[day_of_year % len(ROLES)]

    print(f"📅 日期: {date_str}")
    print(f"💼 岗位: {role_info['name']}")
    print(f"🤖 模型: {MODEL}")
    print("⏳ 生成中...")

    question_data = generate_question(role_info, date_str)

    # 防空响应：题目无效则不写盘，保留 latest.json / index（不被空覆盖）
    if not isinstance(question_data, dict) or not str(question_data.get("question", "")).strip():
        print("❌ 模型返回空/无效题目，跳过写入以避免覆盖已有数据。", file=sys.stderr)
        sys.exit(1)

    # 保存当天文件
    questions_dir = os.path.join(os.path.dirname(__file__), "questions")
    os.makedirs(questions_dir, exist_ok=True)

    daily_path = os.path.join(questions_dir, f"{date_str}.json")
    with open(daily_path, "w", encoding="utf-8") as f:
        json.dump(question_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已保存: {daily_path}")

    # 更新 latest.json
    latest_path = os.path.join(questions_dir, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(question_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已更新: {latest_path}")

    # 更新索引文件（用于历史归档）
    index_path = os.path.join(questions_dir, "index.json")
    index = []
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)

    # 避免重复
    existing_dates = {item["date"] for item in index}
    if date_str not in existing_dates:
        index.insert(0, {
            "date": date_str,
            "role": question_data["role"],
            "question": question_data["question"][:80] + "…" if len(question_data["question"]) > 80 else question_data["question"],
            "type": question_data.get("type", ""),
            "difficulty": question_data.get("difficulty", ""),
        })
        # 不再截断索引：questions/*.json 永久保留，索引一旦截断，
        # 超出窗口的历史题目就再也无法被检索到，等于静默丢失归档。
        # 单条索引约 150 字节，一年约 55KB，展示侧由前端分页处理。

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"✅ 索引已更新，共 {len(index)} 条记录")

    print(f"\n🎯 题目预览: {question_data['question'][:100]}")


if __name__ == "__main__":
    main()
