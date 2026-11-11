import json
from pathlib import Path

CATALOG = json.loads(
    (Path(__file__).parent.parent / "data/departments.json").read_text(encoding="utf-8")
)


def modes(department):
    return [
        {"id": f"module_{i + 1}", "label": t[0], "bot_name": t[0], "description": t[1]}
        for i, t in enumerate(CATALOG[department]["topics"])
    ]


def questions(department):
    return [
        {
            "id": f"{department}-{i + 1}",
            "mode": f"module_{i + 1}",
            "question": t[2],
            "answer": t[3],
        }
        for i, t in enumerate(CATALOG[department]["topics"])
    ]
