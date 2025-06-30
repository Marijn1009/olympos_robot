# flake8: noqa: E402
from setup import setup

setup()

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from robocorp import log
from robocorp.tasks import task, teardown
from robocorp.workitems import ApplicationException, BusinessException  # noqa: F401

from generate_robot_attempts_html import generate_robot_attempts_html
from log_attempt import log_attempt
from olympos_class import Olympos

DUMMY_RUN = False  # If True, no lasting changes will be made

REGISTRATIONS_DB = Path("work_directory/registered_lessons.json")
LAST_SCRAPE_FILE = Path("work_directory/last_scrape.txt")
REGISTRATIONS_DB.parent.mkdir(parents=True, exist_ok=True)


@teardown
def write_status_file(task) -> None:
    output_dir = Path.cwd() / "output"
    status = "FAIL" if task.failed else "SUCCESS"
    with (output_dir / "status.txt").open("w") as f:
        f.write(status)
    generate_robot_attempts_html()


@task
def main() -> None:
    lessons = [
        # {"name": "POLESPORTS", "lesson_type": "GROUPLESSON", "day": "Ma", "time": "20:15"},
        {"name": "POLESPORTS", "lesson_type": "GROUPLESSON", "day": "Wo", "time": "17:30"},
        {"name": "POLESPORTS", "lesson_type": "GROUPLESSON", "day": "Wo", "time": "18:45"},
        {"name": "AERIAL ACROBATIEK HG-GV", "lesson_type": "GROUPLESSON", "day": "Do", "time": "18:15"},
        # {"name": "AERIALACRO", "lesson_type": "COURSE", "time": "do 18:15 - 19:30"},
        # {"name": "AERIALACRO", "lesson_type": "COURSE", "time": "za 09:45 - 11:30"},
        # {"name": "POLESPORTS", "lesson_type": "COURSE", "time": "wo 17:30 - 18:45"},
        # {"name": "POLESPORTS", "lesson_type": "COURSE", "time": "ma 19:00 - 20:15"},
    ]
    # lessons = parse_args()

    if not lessons:
        raise ValueError("No lessons specified. Use --lesson to specify lessons.")

    for lesson in lessons:
        if "datetime" not in lesson:
            lesson["datetime"] = determine_next_datetime(lesson)

    registered_lessons = load_registered()

    filtered_lessons = delete_old_registrations(registered_lessons)
    if len(filtered_lessons) != len(registered_lessons):
        save_registered(filtered_lessons)
        registered_lessons = filtered_lessons

    olympos = Olympos(dummy_run=DUMMY_RUN)
    olympos.start_and_login()

    if should_scrape_today():
        scraped_lessons = olympos.scrape_registered_lessons()
        updated_lessons = append_registered(scraped_lessons, registered_lessons)
        if len(updated_lessons) != len(registered_lessons):
            save_registered(updated_lessons)
            registered_lessons = updated_lessons
        update_last_scrape()

    lessons_to_process = []
    for lesson in lessons:
        if is_registered(lesson, registered_lessons):
            log_attempt(lesson, "Already registered")
        else:
            lessons_to_process.append(lesson)

    if not lessons_to_process:
        log.info("All lessons already registered. Nothing to do.")
        return

    attempt = 0
    process_lessons(olympos, lessons_to_process, attempt, registered_lessons)


def should_scrape_today(last_scrape_file: Path = LAST_SCRAPE_FILE) -> bool:
    """Returns true if today there was no scrape of registrations yet."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    if not last_scrape_file.exists():
        return True
    with last_scrape_file.open() as f:
        last_scrape = f.read().strip()
    return last_scrape != today_str


def update_last_scrape(last_scrape_file: Path = LAST_SCRAPE_FILE) -> None:
    """Updates metadata file containing last date of scraped registrations."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    with last_scrape_file.open("w") as f:
        f.write(today_str)


def load_registered(registrations_db: Path = REGISTRATIONS_DB) -> list[dict]:
    """Loads DB file with list of lessons."""
    if registrations_db.exists():
        with registrations_db.open() as file:
            return json.load(file)
    return []


def save_registered(lessons: list[dict], registrations_db: Path = REGISTRATIONS_DB) -> None:
    """Overwrites DB file with list of lessons."""
    with registrations_db.open("w") as file:
        json.dump(lessons, file, indent=2)


def is_registered(lesson: dict, registered_list: list[dict]) -> bool:
    for registered in registered_list:
        if lesson.get("name") == registered.get("name") and lesson.get("time") == registered.get("time") and lesson.get("day") == registered.get("day"):
            return True
    return False


def append_registered(lessons: list[dict], old_lessons: list[dict]) -> list[dict]:
    """Return a new list with new lessons appended if not already registered."""
    updated = old_lessons.copy()
    for lesson in lessons:
        if not is_registered(lesson, updated):
            updated.append(lesson)
    return updated


def delete_old_registrations(lessons: list[dict]) -> list[dict]:
    today = datetime.now().date()
    return [lesson for lesson in lessons if datetime.fromisoformat(lesson["datetime"]).date() >= today]


def determine_next_datetime(lesson: dict) -> str:
    """Determine the next datetime for a lesson based on its day and time."""
    day_map = {"Ma": 0, "Di": 1, "Wo": 2, "Do": 3, "Vr": 4, "Za": 5, "Zo": 6}
    day_str = lesson.get("day")
    time_str = lesson.get("time")
    if day_str not in day_map or not time_str:
        raise ValueError(f"Cannot determine datetime for lesson: {lesson}")
    target_weekday = day_map[day_str]
    now = datetime.now()
    # Parse time
    hour, minute = map(int, time_str.split(":"))
    # Find next target_weekday (including today if still upcoming)
    days_ahead = (target_weekday - now.weekday() + 7) % 7
    candidate_date = now.date()
    # Today: check if time is still in the future
    if days_ahead == 0 and (now.hour, now.minute) >= (hour, minute):
        days_ahead = 7
    if days_ahead != 0:
        candidate_date = (now + timedelta(days=days_ahead)).date()
    return datetime.combine(candidate_date, datetime.min.time()).replace(hour=hour, minute=minute).isoformat()


def parse_args() -> list[dict]:
    parser = argparse.ArgumentParser(description="Olympos lesson registration bot")
    parser.add_argument(
        "--lesson",
        action="append",
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


def process_lessons(
    olympos: Olympos, lessons: list[dict], attempt: int, registered_lessons: list[dict], save_func=save_registered, log_attempt_func=log_attempt, max_retries=None, log=log
) -> None:
    if max_retries is None:
        max_retries = int(os.environ.get("MAX_RETRIES", "1"))
    if attempt > max_retries:
        log.warn("The unprocessed items are: %s", ", ".join(lesson.get("course_name", str(lesson)) for lesson in lessons))  # noqa: G010
        return
    error_lessons = []
    for lesson in lessons:
        try:
            perform_oplossing(olympos, lesson)
            registered_lessons.append(lesson)
            log_attempt_func(lesson, "Registered")
        except BusinessException as e:
            # no retry for BusinessException, so no error_actions.append(action)
            msg = str(e)
            if "vol" in msg.lower():
                log_attempt_func(lesson, "Already full")
            elif "niet aanwezig" in msg.lower():
                log_attempt_func(lesson, "Not found")
            else:
                log_attempt_func(lesson, f"BusinessException: {msg}")
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:  # noqa: BLE001
            error_lessons.append(lesson)
            log_attempt_func(lesson, f"Exception: {e}")
    save_func(registered_lessons)
    if len(error_lessons) > 0:
        attempt += 1
        process_lessons(olympos, error_lessons, attempt, registered_lessons, save_func=save_func, log_attempt_func=log_attempt_func, max_retries=max_retries, log=log)


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


if __name__ == "__main__":  # pragma: no cover
    main()
