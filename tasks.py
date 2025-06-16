# flake8: noqa: E402
from setup import setup

setup()

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from robocorp import log
from robocorp.tasks import task
from robocorp.workitems import ApplicationException, BusinessException  # noqa: F401

from olympos_class import Olympos
from robot_attempt_log import log_attempt

DUMMY_RUN = True  # If True, no lasting changes will be made

REGISTRATIONS_DB = Path("work_directory/registered_lessons.json")
LAST_SCRAPE_FILE = Path("work_directory/last_scrape.txt")
REGISTRATIONS_DB.parent.mkdir(parents=True, exist_ok=True)


@task
def main() -> None:
    lessons = [
        {"name": "POLESPORTS", "lesson_type": "GROUPLESSON", "day": "Ma", "time": "20:15"},
        {"name": "POLESPORTS", "lesson_type": "GROUPLESSON", "day": "Wo", "time": "18:45"},
        # {"name": "AERIALACRO", "lesson_type": "COURSE", "time": "do 18:15 - 19:30"},
        # {"name": "AERIALACRO", "lesson_type": "COURSE", "time": "za 09:45 - 11:30"},
        # {"name": "POLESPORTS", "lesson_type": "COURSE", "time": "wo 17:30 - 18:45"},
        # {"name": "POLESPORTS", "lesson_type": "COURSE", "time": "ma 19:00 - 20:15"},
    ]
    # lessons = parse_args()

    if not lessons:
        raise ValueError("No lessons specified. Use --lesson to specify lessons.")

    registered_lessons = load_registered()
    registered_lessons = delete_old_registrations(registered_lessons)

    olympos = Olympos(dummy_run=DUMMY_RUN)
    olympos.start_and_login()

    if should_scrape_today():
        scraped_lessons = olympos.scrape_registered_lessons()
        append_registered(scraped_lessons, registered_lessons)
        update_last_scrape()

    lessons_to_process = [lesson for lesson in lessons if not is_registered(lesson, registered_lessons)]

    if not lessons_to_process:
        log.info("All lessons already registered. Nothing to do.")
        return

    attempt = 0
    process_lessons(olympos, lessons_to_process, attempt, registered_lessons)


def should_scrape_today() -> bool:
    today_str = datetime.now().strftime("%Y-%m-%d")
    if not LAST_SCRAPE_FILE.exists():
        return True
    with LAST_SCRAPE_FILE.open() as f:
        last_scrape = f.read().strip()
    return last_scrape != today_str


def update_last_scrape() -> None:
    today_str = datetime.now().strftime("%Y-%m-%d")
    with LAST_SCRAPE_FILE.open("w") as f:
        f.write(today_str)


def load_registered() -> list[dict]:
    if REGISTRATIONS_DB.exists():
        with REGISTRATIONS_DB.open() as file:
            return json.load(file)
    return []


def save_registered(lessons: list[dict]) -> None:
    with REGISTRATIONS_DB.open("w") as file:
        json.dump(lessons, file, indent=2)


def is_registered(lesson: dict, registered_list: list[dict]) -> bool:
    for registered in registered_list:
        if lesson.get("name") == registered.get("name") and lesson.get("time") == registered.get("time") and lesson.get("day") == registered.get("day"):
            return True
    return False


def append_registered(lessons: list[dict], old_lessons: list[dict]) -> None:
    updated = False
    for lesson in lessons:
        if not is_registered(lesson, old_lessons):
            old_lessons.append(lesson)
            updated = True
    if updated:
        save_registered(old_lessons)


def delete_old_registrations(lessons: list[dict]) -> list[dict]:
    """Return only registrations that are today or in the future."""
    today = datetime.now().date()
    filtered_lessons: list[dict] = []
    found_old_lesson: bool = False
    for lesson in lessons:
        lesson_date = datetime.fromisoformat(lesson["datetime"]).date()
        if lesson_date >= today:
            filtered_lessons.append(lesson)
        else:
            found_old_lesson = True

    if found_old_lesson:
        save_registered(filtered_lessons)

    return filtered_lessons


def parse_args() -> list[dict]:
    parser = argparse.ArgumentParser(description="Olympos lesson registration bot")
    parser.add_argument(
        "--lesson",
        lesson="append",  # allow multiple --lesson args
        help="Lesson as 'LESSON_TYPE,NAME,DAY,TIME' (e.g. 'GROUPLESSON,POLESPORTS,Ma,20:15')",
    )

    args, _ = parser.parse_known_args()

    # Collect lessons from command line
    lessons: list[dict] = []
    if args.lesson:
        for lesson in args.lesson:
            parts = [part.strip() for part in lesson.split(",")]
            if len(parts) == 4:
                lessons.append({"lesson_type": parts[0], "name": parts[1], "day": parts[2], "time": parts[3]})
            else:
                parser.error(f"Invalid lesson format: {lesson}. Expected format: 'LESSON_TYPE,NAME,DAY,TIME'")

    return lessons


def process_lessons(olympos: Olympos, lessons: list[dict], attempt: int, registered_lessons: list[dict]) -> None:
    if attempt > int(os.environ.get("MAX_RETRIES", "1")):
        log.warn("The unprocessed items are: %s", ", ".join(lesson.get("course_name", str(lesson)) for lesson in lessons))
        return
    error_lessons = []
    for lesson in lessons:
        try:
            perform_oplossing(olympos, lesson)
            registered_lessons.append(lesson)
            log_attempt(lesson, "Registered")
        except BusinessException as e:
            # no retry for BusinessException, so no error_actions.append(action)
            msg = str(e)
            if "vol" in msg.lower():
                log_attempt(lesson, "Already full")
            elif "niet aanwezig" in msg.lower():
                log_attempt(lesson, "Not found")
            else:
                log_attempt(lesson, f"BusinessException: {msg}")
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:  # noqa: BLE001
            error_lessons.append(lesson)
            log_attempt(lesson, f"Exception: {e}")
    save_registered(registered_lessons)
    if len(error_lessons) > 0:
        attempt += 1
        process_lessons(olympos, error_lessons, attempt, registered_lessons)


def perform_oplossing(olympos: Olympos, lesson: dict) -> None:
    try:
        name = lesson["name"]
        lesson_type = lesson["lesson_type"]
        time = lesson["time"]
    except KeyError as e:
        raise BusinessException(code="MISSING_FIELD", message=f"Missing field: {e}") from e

    # try:
    #     actie_kolom_datum_van = datetime.strptime(actie_kolom_datum_van, "%Y-%m-%d")
    # except ValueError as e:
    #     raise BusinessException(code="DATE_FORMAT_ERROR", message=f"Date format error: {e}") from e

    if lesson_type == "COURSE":
        olympos.register_into_course(name, time)
    elif lesson_type == "GROUPLESSON":
        olympos.register_into_group_lesson(name, time)
    else:
        raise BusinessException(code="LESSON_TYPE_NOT_FOUND", message=f"Lesson type {type} kan niet verwerkt worden.")


if __name__ == "__main__":
    main()
