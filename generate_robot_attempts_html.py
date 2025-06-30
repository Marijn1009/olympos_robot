import json
from datetime import datetime
from pathlib import Path

from robocorp import log

INPUT_FILE = Path("work_directory/robot_attempts.jsonl")
OUTPUT_FILE = Path("work_directory/robot_attempts.html")

HTML_HEADER = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Robot Attempts Log</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 2em; background: #f9f9f9; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; background: #fff; }
        th, td { border: 1px solid #ccc; padding: 8px 12px; text-align: left; }
        th { background: #eee; }
        tr:nth-child(even) { background: #f5f5f5; }
        .result-Registered { background: #d4edda; color: #155724; font-weight: bold; }
        .result-Already { background: #fff3cd; color: #856404; }
        .result-Not { background: #f8d7da; color: #721c24; }
        .success-cell { font-size: 1.5em; text-align: center; color: #28a745; }
    </style>
</head>
<body>
    <h1>Robot Attempts Log</h1>
    <table>
        <thead>
            <tr>
                <th>Timestamp</th>
                <th>Date</th>
                <th>Time</th>
                <th>Result</th>
                <th>✔</th>
                <th>Name</th>
                <th>Type</th>
                <th>Day</th>
                <th>Lesson Time</th>
                <th>Lesson Date</th>
            </tr>
        </thead>
        <tbody>
"""

HTML_FOOTER = """        </tbody>
    </table>
</body>
</html>
"""


def parse_datetime(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
    except ValueError:
        return dt_str, ""


def parse_lesson_datetime(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except ValueError:
        return dt_str, ""


def get_result_class(result):
    if result == "Registered":
        return "result-Registered"
    if result.startswith("Already"):
        return "result-Already"
    if result.startswith("Not"):
        return "result-Not"
    return ""


def get_success_mark(result):
    return "✔️" if result == "Registered" else ""


def generate_robot_attempts_html():
    rows = []
    if not INPUT_FILE.exists():
        log.warn(f"Input file {INPUT_FILE} not found.")
        return

    with INPUT_FILE.open(encoding="utf-8") as f:
        for line in f:
            stripped_line = line.strip()
            if not stripped_line:
                continue
            entry = json.loads(stripped_line)
            action = entry.get("action", {})
            # Parse main timestamp
            date, time = parse_datetime(entry.get("timestamp", ""))
            # Parse lesson datetime
            lesson_date, lesson_time = parse_lesson_datetime(action.get("datetime", ""))
            result = entry.get("result", "")
            result_class = get_result_class(result)
            success_mark = get_success_mark(result)
            rows.append(f"""<tr>
                <td>{entry.get("timestamp", "")}</td>
                <td>{date}</td>
                <td>{time}</td>
                <td class="{result_class}">{result}</td>
                <td class="success-cell">{success_mark}</td>
                <td>{action.get("name", "")}</td>
                <td>{action.get("lesson_type", "")}</td>
                <td>{action.get("day", "")}</td>
                <td>{action.get("time", "")}</td>
                <td>{lesson_date} {lesson_time}</td>
            </tr>""")

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        f.write(HTML_HEADER)
        for row in rows:
            f.write(row + "\n")
        f.write(HTML_FOOTER)


if __name__ == "__main__":
    generate_robot_attempts_html()
