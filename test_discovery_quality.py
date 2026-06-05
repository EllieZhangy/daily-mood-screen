"""
test_discovery_quality.py

Prints the full discovery prompt for four test contexts.
Does not call the LLM — use this to inspect prompt quality before running.

Usage:
    python test_discovery_quality.py
"""

from src.prompt_builder import build_discovery_prompt

# Bad outputs we want to move away from:
#   "窗玻璃映出室内指痕，与外面云层交织。"  — stays at visual scene, no realization
#   "不说话也温柔。"                         — pure atmosphere, no discovery
#   "风会替你记得。"                         — sounds gentle, intellectually empty
#   "灯光有了理由。"                         — mood without meaning

# Better direction:
#   Observation → realization: reader feels "I had not thought of it this way before"
#   The sentence moves, it does not just describe

CASES = [
    {
        "label": "雨天傍晚",
        "preset": "zh_rainy",
        "context": {
            "language": "zh-CN",
            "weather": "rainy",
            "temperature": 14,
            "location": "上海",
            "time_of_day": "evening",
        },
    },
    {
        "label": "多云早晨",
        "preset": "zh_gentle",
        "context": {
            "language": "zh-CN",
            "weather": "cloudy",
            "temperature": 18,
            "location": "北京",
            "time_of_day": "morning",
        },
    },
    {
        "label": "安静的周末",
        "preset": "zh_weekend",
        "context": {
            "language": "zh-CN",
            "weather": "sunny",
            "temperature": 22,
            "time_of_day": "afternoon",
        },
    },
    {
        "label": "怀旧的夜晚",
        "preset": "zh_nostalgic",
        "context": {
            "language": "zh-CN",
            "weather": "clear",
            "temperature": 16,
            "time_of_day": "night",
        },
    },
]


def run():
    separator = "=" * 60

    for case in CASES:
        print(separator)
        print(f"场景：{case['label']}  |  preset: {case['preset']}")
        print(separator)

        try:
            from src.discovery_engine import build_discovery_context
            from src.observation_engine import build_observation_context
            import json, os

            presets_dir = os.path.join(
                os.path.dirname(__file__), "style_library", "writing", "presets"
            )
            with open(os.path.join(presets_dir, f"{case['preset']}.json"), encoding="utf-8") as f:
                preset = json.load(f)

            discovery   = build_discovery_context(preset)
            observation = build_observation_context(preset, case["context"])

            print(f"  发现方式   : {discovery['primary_id']}")
            print(f"  问题       : {discovery['core_question']}")
            print(f"  观察场景   : {observation['theme']}")
            print()

            prompt = build_discovery_prompt(case["context"], case["preset"])
            print(prompt)

        except Exception as e:
            print(f"  ERROR: {e}")

        print()
        print(f"  → 输出占位符（实际运行需要 OPENAI_API_KEY）")
        print()


if __name__ == "__main__":
    run()
