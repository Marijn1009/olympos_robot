import json
from datetime import datetime
from pathlib import Path

ATTEMPT_LOG = Path("work_directory/robot_attempts.jsonl")


def log_attempt(action: dict, result: str) -> None:
    ATTEMPT_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "result": result,
        "action": action,
    }
    with ATTEMPT_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
