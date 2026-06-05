"""
src/prompt_builder.py

Core goal: generate a sentence that leaves a meaningful gap.

Architecture:
  Current context  →  Observation (one image)  →  Discovery pattern
  →  Stop before finishing the thought  →  One sentence with a gap
"""

import json
import os

from src.discovery_engine import build_discovery_context
from src.observation_engine import build_observation_context

_ROOT        = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_PRESETS_DIR = os.path.join(_ROOT, "style_library", "writing", "presets")

_AVOID_CONTENT = [
    "温柔", "治愈", "成长", "坚持", "焦虑", "快乐", "努力",
    "梦想", "治愈感", "松弛感",
]

_AVOID_REASONING = [
    "因此", "所以", "于是", "其实", "原来", "意味着",
    "虽然", "但是", "然而", "却",
]

_QUALITY_LADDER = """\
【成功标准】
差：今天虽然阴天，但依然值得期待。
  → AI腔。有逻辑，没余韵。读者不需要参与。

中：云层很厚，像一封迟迟没有拆开的信。
  → 有画面，但说完了。读者是旁观者。

好：云层很厚，天却一直没有下定决心。
  → 开始有性格。但还是解释了。

很好：云层很厚，像在等什么。
  → 读者开始参与，自己填补空白。目标在这里。

顶级：晴天时爱晴，雨天时爱雨。
  → 没有画面炫技，没有文学技巧炫技。读者会停下来。这是另一种难度。

目标：很好或顶级。"""


def _load_preset(preset_id: str) -> dict:
    path = os.path.join(_PRESETS_DIR, f"{preset_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Preset not found: {preset_id}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_discovery_prompt(context: dict, preset_id: str) -> str:
    """
    Build the complete prompt.

    Args:
        context: situational data —
            {
              "language":    "zh-CN",
              "weather":     "cloudy",
              "temperature": 18,
              "location":    "Shanghai",
              "time_of_day": "evening",
              "mood":        "calm",
            }
        preset_id: e.g. "zh_evening"

    Returns:
        A ready-to-send prompt string.
    """
    preset      = _load_preset(preset_id)
    discovery   = build_discovery_context(preset)
    observation = build_observation_context(preset, context)

    # ── Context block ─────────────────────────────────────────────────────────
    weather  = context.get("weather", "")
    temp     = context.get("temperature", "")
    location = context.get("location", "")
    tod      = context.get("time_of_day", "")

    ctx_parts = []
    weather_str = f"{weather}，{temp}°C" if temp else weather
    if location:
        weather_str = f"{location}，{weather_str}"
    if weather_str.strip():
        ctx_parts.append(f"天气：{weather_str}")
    if tod:
        ctx_parts.append(f"时段：{tod}")
    context_block = "\n".join(ctx_parts) if ctx_parts else "（无特定情境）"

    # ── Observation block ─────────────────────────────────────────────────────
    obs_theme    = observation.get("theme", "")
    obs_objects  = "、".join(observation.get("objects", [])[:3])
    obs_contrasts = "、".join(observation.get("contrasts", [])[:2])
    obs_avoid    = "、".join(observation.get("avoid_details", [])[:4])

    obs_lines = [f"场景：{obs_theme}"]
    if obs_objects:
        obs_lines.append(f"可用意象（最多选一个）：{obs_objects}")
    if obs_contrasts:
        obs_lines.append(f"内在张力：{obs_contrasts}")
    if obs_avoid:
        obs_lines.append(f"不要出现：{obs_avoid}")
    observation_block = "\n".join(obs_lines)

    # ── Discovery block ───────────────────────────────────────────────────────
    d_id          = discovery["primary_id"]
    d_description = discovery["primary"].get("description", "")
    d_approach    = discovery["primary"].get("approach", "")
    d_question    = discovery["core_question"]
    d_bad         = discovery["primary"].get("bad_output_patterns", [])
    d_good        = discovery["primary"].get("good_output_patterns", [])

    discovery_lines = [f"含义：{d_description}"]
    if d_approach:
        discovery_lines.append(f"方法：{d_approach}")
    discovery_lines.append(f"问自己：{d_question}")
    discovery_block = "\n".join(discovery_lines)

    bad_block  = "\n".join(f"  ✗ {p}" for p in d_bad)
    good_block = "\n".join(f"  ✓ {p}" for p in d_good)

    # ── Avoid strings ─────────────────────────────────────────────────────────
    avoid_content_str   = "、".join(_AVOID_CONTENT)
    avoid_reasoning_str = "、".join(_AVOID_REASONING)

    # ── Assemble ──────────────────────────────────────────────────────────────
    prompt = f"""生成一个留有空白的句子。

不要把思路写完。
留一个缺口。
让读者用自己的情感填补它。

【当前情境】
{context_block}

【观察入口】
{observation_block}

【发现方式：{d_id}】
{discovery_block}

【这个方向的错误输出】
{bad_block}

【这个方向的好输出】
{good_block}

{_QUALITY_LADDER}

【语言规则】
偏好状态而非判断：
  ✗ 未必明亮　✗ 并不孤独　✗ 不会阻挡
  ✓ 忽明忽暗　✓ 渐远渐近　✓ 半开半掩　✓ 欲落未落　✓ 将晴未晴

禁止出现：我、你、我们

禁止（这些词会毁掉余韵）：{avoid_reasoning_str}

偏好的质地：状态　流动　变化　气息　余韵

不要解释。不要得出结论。不要给出道德判断。
在句子完成之前停下来。

【生成过程】
第一步：从"可用意象"里选取最多一个具体意象作为入口
第二步：施加发现方式，越过观察层面
第三步：在句子把意思说完之前停下来——留出那个缺口
第四步：问自己：读者需要参与才能理解这句话吗？

【输出前的质量检查】
  这句话解释了所有东西吗？→ 删掉结论，重写
  这句话给出了完整的判断吗？→ 删掉判断，重写
  这句话只是一个好看的场景吗？→ 重写
  读者需要停下来想一想吗？→ 可以输出

【输出规则】
- 只写一句话
- 中文
- 最多32个汉字（意义完整优先于长度限制）
- 不加引号，不加解释，不加emoji，不加标签
- 如果是原创句子：不署名
- 如果是直接引用某位作家的原句：注明作者和出处，格式为「句子 ——作者《书名》」
- 禁止使用：{avoid_content_str}
- 不要只堆叠意象

只输出那一句话。"""

    return prompt


# ── Backward-compatible alias ─────────────────────────────────────────────────

def build_quote_prompt(context: dict, preset_id: str) -> str:
    """Alias kept for call sites in quote_generator.py."""
    return build_discovery_prompt(context, preset_id)
