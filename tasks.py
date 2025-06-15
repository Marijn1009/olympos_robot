# flake8: noqa: E402
from setup import setup

setup()

import os

from robocorp import log
from robocorp.tasks import task
from robocorp.workitems import ApplicationException, BusinessException

from olympos_class import Olympos

DUMMY_RUN = True  # If True, no lasting changes will be made


@task
def main() -> None:
    olympos = Olympos(dummy_run=DUMMY_RUN)
    with log.suppress_variables():
        olympos.start_and_login()

    actions = [
        {"name": "POLESPORTS", "lesson_type": "GROUPLESSON", "day": "Ma", "time": "20:15"},
        {"name": "POLESPORTS", "lesson_type": "GROUPLESSON", "day": "Wo", "time": "18:45"},
        # {"name": "AERIALACRO", "lesson_type": "COURSE", "time": "do 18:15 - 19:30"},
        # {"name": "AERIALACRO", "lesson_type": "COURSE", "time": "za 09:45 - 11:30"},
        # {"name": "POLESPORTS", "lesson_type": "COURSE", "time": "wo 17:30 - 18:45"},
        # {"name": "POLESPORTS", "lesson_type": "COURSE", "time": "ma 19:00 - 20:15"},
    ]

    # Verwerk acties
    attempt = 0
    process_actions(olympos, actions, attempt)


def process_actions(olympos: Olympos, actions: list[dict], attempt: int) -> None:
    if attempt > int(os.environ.get("MAX_RETRIES", "1")):
        log.warn("The unprocessed items are: %s", ", ".join(action.get("course_name", str(action)) for action in actions))
        return
    error_actions = []
    for action in actions:
        try:
            perform_oplossing(olympos, action)
        except ApplicationException as err:
            error_actions.append(action)
            log.exception("ApplicationException occurred: %s. Action: %s", err, action)
        except BusinessException as err:
            # no retry for BusinessException, so no error_actions.append(action)
            log.exception("BusinessException occurred: %s. Action: %s", err, action)

    if len(error_actions) > 0:
        attempt += 1
        process_actions(olympos, error_actions, attempt)


def perform_oplossing(olympos: Olympos, action: dict) -> str:
    try:
        name = action["name"]
        lesson_type = action["lesson_type"]
        time = action["time"]
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

    return comment


if __name__ == "__main__":
    main()
