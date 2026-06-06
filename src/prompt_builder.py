"""
src/prompt_builder.py

Core goal: generate a sentence that completes its thought clearly.

Architecture:
  Current context  →  Observation (one image)  →  Discovery pattern
  →  Finish the thought  →  One sentence that lands on a clear image,
     realization, observation, or emotional insight.
"""

import json
import os

from src.discovery_engine import build_discovery_context
from src.observation_engine import build_observation_context

_ROOT        = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_PRESETS_DIR = os.path.join(_ROOT, "style_library", "writing", "presets")

_AVOID_CONTENT = [
    "温柔", "治愈", "成长", "坚持", "焦虑", "快乐", "努力",
    "梦想", "治愈感", "松弛感", "治愈系", "正能量", "内耗",
]

_AVOID_REASONING = [
    "因此", "所以", "于是", "其实", "原来", "意味着",
    "虽然", "但是", "然而", "却",
]

_VOICE_GUIDE = """\
【声音参考——研究结构与气质，不复制原句】

这个声音的典型句子：
  · 总有人在回家的路上，也总有人在等灯亮起。
  · 天色慢下来，人也该慢下来。
  · 晴天时爱晴，雨天时爱雨。
  · 流水不争光，争的是滔滔不绝。
  · 秋日薄暮，用菊花煮竹叶青，人与海棠俱醉。
  · 草木蔓生，春山可望。
  · 天寒露重，望君保重。
  · 人生是旷野，不是轨迹。
  · 白鹭立雪，愚人看鹭，聪者观雪，智者见白。
  · 关关难过关关过，前轮漫漫亦灿灿。

这个声音的结构规律：

① 自然映照人——外部观察安静地折射内部：
   "天色慢下来，人也该慢下来"
   先说世界的动作，然后人跟上。不解释，读者自己感受到。

② 对称与平衡——两半句持有同一个秘密：
   "晴天时爱晴，雨天时爱雨"
   不是重复，是完整。每一半都需要另一半才成立。

③ 出乎意料的替换——用陌生的容器盛放熟悉的感受：
   "回忆若能下酒，往事便可作一场宿醉"
   不直接命名情感，用另一件事把它摆出来。

④ 递进的平行——同一个场景，三个深度：
   "愚人看鹭，聪者观雪，智者见白"
   层层深入，但不说破哪个更好——读者自己落在哪里。

⑤ 反转着陆——设置一个期待，然后落在意料之外：
   "流水不争光，争的是滔滔不绝"
   前半像放弃，后半是另一种胜利。

⑥ 具体时刻里——句子住在一个真实的时间里：
   "秋日薄暮""在热烈的夏天""天寒露重"
   不飘在空中，有温度，有季节，有时间段。

⑦ 不说破——洞察藏在结构里，不在解释里：
   "晴天时爱晴，雨天时爱雨"里有整个人生哲学，但从未用过"人生"这个词。

⑧ 暖，不甜——关心有分量，不轻飘：
   "天寒露重，望君保重"——四字关心，没有一个多余的字。"""

_QUALITY_LADDER = """\
【成功标准】

差：今天虽然阴天，但依然值得期待。
  → AI励志腔。因果逻辑代替了真实感受。没有画面，没有重量。

差：光线仿佛在说什么……
  → 悬空。用"仿佛"代替了一个真正的观察。句子没有落地。

中：云层很厚，像一封迟迟没有拆开的信。
  → 有画面，结构是好的。但"像"之后需要真正的落点，
    而"迟迟没有拆开"只是延续了悬念，没有完成。

好：云层很厚，天却一直没有下定决心。
  → 完整落地。天有了性格，句子有了结论，读者有了感受。

顶级：晴天时爱晴，雨天时爱雨。
  → 两句对称，装着整个人生态度，一个字都不解释。读者会停下来。

顶级：流水不争光，争的是滔滔不绝。
  → 反转着陆。前半放弃，后半是另一种坚持。完整，有回响。

目标：好或顶级。每一句都必须落在某个具体的地方。"""


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
    prompt = f"""生成一句话，写完它的思路，落在一个清晰的画面、感受或洞察上。

把句子写完。不要悬置结论。
不要用"仿佛""像是""或许是""好像""似乎"来代替一个真正的落点。

{_VOICE_GUIDE}

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

不要解释。不要给出道德判断。不要说教。
把句子写完，落在一个具体的画面、清晰的观察、真实的感受、或一个有重量的问题上。

【禁止的结尾方式】
  ✗ 或许是……　✗ 像是在……　✗ 仿佛……　✗ 好像……　✗ 似乎……
  ✗ 任何用省略号或悬置短语代替真正结论的结尾
  → 这些不是诗意，是未完成的句子。用一个真正的落点代替它。

【生成过程】
第一步：从"可用意象"里选取最多一个具体意象作为入口
第二步：施加发现方式，越过观察层面
第三步：把句子写完——落在一个清晰的画面、感受、洞察或问题上
第四步：问自己：这句话有落点吗？有具体的东西可以记住吗？

【输出前的质量检查】
  这句话用"或许""仿佛""像是"悬置了结论吗？→ 重写，给出真正的落点
  这句话只是一个好看但空洞的场景吗？→ 重写
  这句话在说教或给建议吗？→ 删掉判断，重写
  这句话落在一个清晰、具体、有回响的地方吗？→ 可以输出

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
