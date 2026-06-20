# app/llm/parser.py
import json
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "dummy-key-for-tests"))

_SYSTEM_PROMPT = """You interpret natural language commands for a mug cup 3D modeling system.

Determine the user's intent and return a JSON object:

1. If the user wants to CREATE a new cup model:
{
  "intent": "create",
  "body_template": "tapered" | "cylinder",
  "handle_template": "bspline" | "ring" | null,
  "changes": []
}

2. If the user wants to MODIFY existing parameters:
{
  "intent": "modify",
  "body_template": null,
  "handle_template": null,
  "changes": [{"param": "param_name", "op": "set"|"delta", "value": number}]
}

op rules:
- "set"   → absolute target value  (e.g. "10mm로 바꿔줘", "set to 50", "make it 30mm")
- "delta" → relative change        (e.g. "15mm 더 크게", "5mm 줄여줘", "increase by 10")
For "delta", value is SIGNED: positive = increase, negative = decrease.
Example: "5mm 작게" → {"op": "delta", "value": -5}
CRITICAL: "X으로/로 수정/변경/바꿔줘" is ALWAYS op:"set" even if X is negative.
  "-10으로 바꿔줘" → {"op": "set", "value": -10}  (NOT delta)

3. If the user wants to apply a POST-PROCESS operation (selection context is provided):
{
  "intent": "post_process",
  "operation": "fillet_edge",
  "radius": number
}
Post-process keywords: fillet/필렛/라운드/round → "fillet_edge"
Use this intent ONLY when a selection context (Edge index) is provided.

The graph_context in each request lists all available parameters with their current
values, constraints, and geometry relationships. Only modify nodes where user_facing is true.

Creation keywords (any language): make, create, generate, new, 만들어, 생성, 새로운, 컵, 머그
Body types: tapered/테이퍼드=tapered, cylinder/원통=cylinder (default: tapered)
Handle types: bspline/손잡이=bspline, ring/링=ring, none/없는=null (default: bspline)

Return ONLY the JSON object, no explanation."""


def parse_command(
    command: str,
    graph_context: dict,
    selection: dict | None = None,
) -> dict:
    """자연어 명령을 파싱하여 intent와 변경 사항을 반환."""
    user_content = f"Current graph state:\n{json.dumps(graph_context, indent=2)}\n"
    if selection:
        user_content += f"Selection: {selection['type']} index {selection['index']}\n"
    user_content += f"\nCommand: {command}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=256,
        temperature=0,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    text = response.choices[0].message.content.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result = json.loads(text[start:end])
    result.setdefault("intent", "modify")
    result.setdefault("body_template", None)
    result.setdefault("handle_template", None)
    result.setdefault("changes", [])
    return result
