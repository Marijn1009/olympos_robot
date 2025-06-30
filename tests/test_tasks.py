import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tasks import (
    ApplicationException,
    BusinessException,
    append_registered,
    delete_old_registrations,
    determine_next_datetime,
    is_registered,
    load_registered,
    parse_args,
    process_lessons,
    save_registered,
    should_scrape_today,
    update_last_scrape,
)


@pytest.fixture
def sample_lessons() -> list[dict]:
    return [
        {"name": "Yoga", "time": "10:00", "day": "Monday"},
        {"name": "Pilates", "time": "11:00", "day": "Tuesday"},
    ]


@pytest.fixture
def temp_last_scrape_file(tmp_path):
    return tmp_path / "last_scrape.txt"


def test_should_scrape_today_when_file_does_not_exist(temp_last_scrape_file):
    assert should_scrape_today(last_scrape_file=temp_last_scrape_file) is True


def test_should_scrape_today_when_file_has_yesterdays_date(temp_last_scrape_file):
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    temp_last_scrape_file.write_text(yesterday)
    assert should_scrape_today(last_scrape_file=temp_last_scrape_file) is True


def test_should_scrape_today_when_file_has_todays_date(temp_last_scrape_file):
    today = datetime.now().strftime("%Y-%m-%d")
    temp_last_scrape_file.write_text(today)
    assert should_scrape_today(last_scrape_file=temp_last_scrape_file) is False


def test_update_last_scrape(temp_last_scrape_file):
    # Test that old data is overwritten:
    temp_last_scrape_file.write_text("old-date")

    # New data should be today's date
    update_last_scrape(last_scrape_file=temp_last_scrape_file)
    content = temp_last_scrape_file.read_text().strip()
    today = datetime.now().strftime("%Y-%m-%d")
    assert content == today


def test_update_last_scrape_creates_file_if_not_exists(temp_last_scrape_file):
    assert not temp_last_scrape_file.exists()
    update_last_scrape(last_scrape_file=temp_last_scrape_file)
    assert temp_last_scrape_file.exists()
    content = temp_last_scrape_file.read_text().strip()
    today = datetime.now().strftime("%Y-%m-%d")
    assert content == today


@pytest.fixture
def temp_registrations_db(tmp_path):
    return tmp_path / "sample_lessons.json"


def test_load_registered_returns_empty_list_when_file_does_not_exist(temp_registrations_db):
    assert not temp_registrations_db.exists()
    result = load_registered(registrations_db=temp_registrations_db)
    assert result == []


def test_load_registered_returns_data_when_file_exists(temp_registrations_db, sample_lessons):
    temp_registrations_db.write_text(json.dumps(sample_lessons))
    result = load_registered(registrations_db=temp_registrations_db)
    assert result == sample_lessons


def test_load_registered_handles_empty_file(temp_registrations_db):
    temp_registrations_db.write_text("")
    with pytest.raises(json.JSONDecodeError):
        load_registered(registrations_db=temp_registrations_db)


def test_load_registered_handles_invalid_json(temp_registrations_db):
    temp_registrations_db.write_text("{invalid json}")
    with pytest.raises(json.JSONDecodeError):
        load_registered(registrations_db=temp_registrations_db)


def test_save_registered_creates_file_and_writes_data(temp_registrations_db, sample_lessons):
    save_registered(sample_lessons, registrations_db=temp_registrations_db)
    assert temp_registrations_db.exists()
    # Check file content is valid JSON and matches input
    with temp_registrations_db.open() as f:
        data = json.load(f)
    assert data == sample_lessons


def test_save_registered_overwrites_existing_file(temp_registrations_db):
    initial = [{"name": "Old", "time": "09:00", "day": "Sunday"}]
    temp_registrations_db.write_text(json.dumps(initial))
    new_lessons = [{"name": "New", "time": "10:00", "day": "Monday"}]
    save_registered(new_lessons, registrations_db=temp_registrations_db)
    with temp_registrations_db.open() as f:
        data = json.load(f)
    assert data == new_lessons


def test_save_registered_writes_empty_list(temp_registrations_db: Path):
    save_registered([], registrations_db=temp_registrations_db)
    with temp_registrations_db.open() as f:
        data = json.load(f)
    assert data == []


@pytest.mark.parametrize(
    ("lesson", "registered", "expected"),
    [
        # Basic matches and mismatches
        ({"name": "Yoga", "time": "10:00", "day": "Monday"}, None, True),
        ({"name": "Pilates", "time": "11:00", "day": "Tuesday"}, None, True),
        ({"name": "Boxing", "time": "12:00", "day": "Wednesday"}, None, False),
        ({"name": "Yoga", "time": "12:00", "day": "Monday"}, None, False),  # name only matches
        ({"name": "Boxing", "time": "10:00", "day": "Monday"}, None, False),  # time only matches
        ({"name": "Yoga", "time": "10:00", "day": "Tuesday"}, None, False),  # day only matches
        ({"name": "Yoga", "time": "10:00", "day": "Monday", "extra": "field"}, None, True),  # extra field in lesson
        ({"name": "Yoga", "time": "10:00"}, None, False),  # missing day
        ({"name": "Yoga", "day": "Monday"}, None, False),  # missing time
        ({"time": "10:00", "day": "Monday"}, None, False),  # missing name
        # Empty registered list
        ({"name": "Yoga", "time": "10:00", "day": "Monday"}, [], False),
        # Extra fields in registered
        (
            {"name": "Boxing", "time": "12:00", "day": "Wednesday"},
            [
                {"name": "Yoga", "time": "10:00", "day": "Monday"},
                {"name": "Pilates", "time": "11:00", "day": "Tuesday"},
                {"name": "Boxing", "time": "12:00", "day": "Wednesday", "note": "VIP"},
            ],
            True,
        ),
        # Multiple matches
        (
            {"name": "Yoga", "time": "10:00", "day": "Monday"},
            [
                {"name": "Yoga", "time": "10:00", "day": "Monday"},
                {"name": "Yoga", "time": "10:00", "day": "Monday", "note": "duplicate"},
            ],
            True,
        ),
        # Case sensitivity
        ({"name": "yoga", "time": "10:00", "day": "Monday"}, None, False),
    ],
)
def test_is_registered_parametrized(lesson, registered, expected, sample_lessons):
    reg = sample_lessons if registered is None else registered
    assert is_registered(lesson, reg) is expected


def test_get_appended_registered_adds_new_lessons():
    old_lessons = [{"name": "Yoga", "time": "10:00", "day": "Monday"}]
    new_lessons = [{"name": "Pilates", "time": "11:00", "day": "Tuesday"}]
    lessons_appended = append_registered(new_lessons, old_lessons)
    assert len(lessons_appended) == 2
    assert any(lesson["name"] == "Pilates" for lesson in lessons_appended)


def test_delete_old_registrations_removes_past_lessons(monkeypatch):
    today = datetime.now().date()
    yesterday = (datetime.now() - timedelta(days=1)).date()
    tomorrow = (datetime.now() + timedelta(days=1)).date()

    lessons = [
        {"name": "Past", "datetime": datetime.combine(yesterday, datetime.min.time()).isoformat()},
        {"name": "Today", "datetime": datetime.combine(today, datetime.min.time()).isoformat()},
        {"name": "Future", "datetime": datetime.combine(tomorrow, datetime.min.time()).isoformat()},
    ]
    filtered = delete_old_registrations(lessons)
    expected_lessons = [lesson for lesson in lessons if lesson["name"] in ("Today", "Future")]
    assert filtered == expected_lessons


def test_delete_old_registrations_all_past():
    yesterday = (datetime.now() - timedelta(days=2)).date()
    lessons = [
        {"name": "Old1", "datetime": datetime.combine(yesterday, datetime.min.time()).isoformat()},
        {"name": "Old2", "datetime": datetime.combine(yesterday, datetime.min.time()).isoformat()},
    ]
    filtered = delete_old_registrations(lessons)
    assert filtered == []


def test_delete_old_registrations_all_future():
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    lessons = [
        {"name": "Future1", "datetime": datetime.combine(tomorrow, datetime.min.time()).isoformat()},
        {"name": "Future2", "datetime": datetime.combine(tomorrow, datetime.min.time()).isoformat()},
    ]
    filtered = delete_old_registrations(lessons)
    assert filtered == lessons


def test_delete_old_registrations_handles_empty_list():
    assert delete_old_registrations([]) == []


def test_delete_old_registrations_raises_on_missing_datetime():
    lessons = [{"name": "NoDatetime"}]
    with pytest.raises(KeyError):
        delete_old_registrations(lessons)


def test_delete_old_registrations_raises_on_invalid_datetime_format():
    lessons = [{"name": "BadDate", "datetime": "not-a-date"}]
    with pytest.raises(ValueError, match="not-a-date"):
        delete_old_registrations(lessons)


@pytest.mark.parametrize(
    ("lesson", "now_date", "expected_datetime"),
    [
        # Next Monday, time in future today
        ({"day": "Ma", "time": "23:59"}, datetime(2024, 6, 10, 10, 0), datetime(2024, 6, 10, 23, 59)),
        # Next Monday, time already passed today (should go to next week)
        ({"day": "Ma", "time": "09:00"}, datetime(2024, 6, 10, 10, 0), datetime(2024, 6, 17, 9, 0)),
        # Next Wednesday, today is Monday
        ({"day": "Wo", "time": "18:45"}, datetime(2024, 6, 10, 10, 0), datetime(2024, 6, 12, 18, 45)),
        # Next Sunday, today is Saturday
        ({"day": "Zo", "time": "08:00"}, datetime(2024, 6, 15, 12, 0), datetime(2024, 6, 16, 8, 0)),
        # Today, time in future
        ({"day": "Di", "time": "23:00"}, datetime(2024, 6, 11, 10, 0), datetime(2024, 6, 11, 23, 0)),
        # Today, time already passed (should go to next week)
        ({"day": "Di", "time": "09:00"}, datetime(2024, 6, 11, 10, 0), datetime(2024, 6, 18, 9, 0)),
    ],
)
def test_determine_next_datetime(monkeypatch, lesson, now_date, expected_datetime):
    # Patch datetime.now() to return now_date
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now_date

    monkeypatch.setattr("tasks.datetime", FixedDateTime)

    result = determine_next_datetime(lesson)
    actual_datetime = datetime.fromisoformat(result)
    assert actual_datetime == expected_datetime


def test_determine_next_datetime_invalid_day():
    with pytest.raises(ValueError, match="Cannot determine datetime"):
        determine_next_datetime({"day": "Xx", "time": "10:00"})


def test_determine_next_datetime_missing_time():
    with pytest.raises(ValueError, match="Cannot determine datetime"):
        determine_next_datetime({"day": "Ma"})


def test_determine_next_datetime_invalid_time_format():
    with pytest.raises(ValueError, match="notatime"):
        determine_next_datetime({"day": "Ma", "time": "notatime"})


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["prog", "--lesson", "GROUPLESSON,POLESPORTS,Ma,20:15"],
            [{"lesson_type": "GROUPLESSON", "name": "POLESPORTS", "day": "Ma", "time": "20:15"}],
        ),
        (
            ["prog", "--lesson", "COURSE,AERIALACRO,Za,09:45"],
            [{"lesson_type": "COURSE", "name": "AERIALACRO", "day": "Za", "time": "09:45"}],
        ),
        (
            ["prog", "--lesson", "GROUPLESSON,POLESPORTS,Wo,18:45", "--lesson", "GROUPLESSON,SPINNING,Di,18:30"],
            [
                {"lesson_type": "GROUPLESSON", "name": "POLESPORTS", "day": "Wo", "time": "18:45"},
                {"lesson_type": "GROUPLESSON", "name": "SPINNING", "day": "Di", "time": "18:30"},
            ],
        ),
        (
            ["prog"],
            [],
        ),
    ],
)
def test_parse_args_valid(monkeypatch, argv, expected):
    monkeypatch.setattr(sys, "argv", argv)
    result = parse_args()
    assert result == expected


@pytest.mark.parametrize(
    "bad_lesson",
    [
        "GROUPLESSON,POLESPORTS,Ma",  # too few parts
        "GROUPLESSON,POLESPORTS,Ma,20:15,EXTRA",  # too many parts
        "GROUPLESSON",  # way too few
        "",  # empty string
    ],
)
def test_parse_args_invalid(monkeypatch, bad_lesson):
    argv = ["prog", "--lesson", bad_lesson]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        parse_args()


@pytest.fixture
def dummy_olympos():
    class DummyOlympos:
        def __init__(self):
            self.calls = []

    return DummyOlympos()


def test_process_lessons_success(monkeypatch, dummy_olympos):
    lessons = [{"name": "Yoga", "lesson_type": "GROUPLESSON", "time": "10:00"}]
    registered = []

    called = {}

    def fake_perform_oplossing(olympos, lesson):
        called["called"] = True

    monkeypatch.setattr("tasks.perform_oplossing", fake_perform_oplossing)

    def fake_save(lessons_arg):
        called["saved"] = lessons_arg.copy()

    def fake_log(lesson, msg):
        called.setdefault("logs", []).append((lesson, msg))

    process_lessons(
        dummy_olympos,
        lessons,
        attempt=0,
        registered_lessons=registered,
        save_func=fake_save,
        log_attempt_func=fake_log,
    )
    assert called["called"]
    assert called["saved"] == [{"name": "Yoga", "lesson_type": "GROUPLESSON", "time": "10:00"}]
    assert "Registered" in [msg for _, msg in called["logs"]]


def test_process_lessons_business_exception(monkeypatch, dummy_olympos):
    lessons = [{"name": "Yoga", "lesson_type": "GROUPLESSON", "time": "10:00"}]
    registered = []

    def fake_perform_oplossing(olympos, lesson):
        raise BusinessException("vol", "Already full")

    monkeypatch.setattr("tasks.perform_oplossing", fake_perform_oplossing)

    logs = []

    def fake_log(lesson, msg):
        logs.append(msg)

    def fake_save(lessons_arg):
        pass

    process_lessons(
        dummy_olympos,
        lessons,
        attempt=0,
        registered_lessons=registered,
        save_func=fake_save,
        log_attempt_func=fake_log,
    )
    assert any("Already full" in msg for msg in logs)


def test_process_lessons_business_exception_not_found(monkeypatch, dummy_olympos):
    lessons = [{"name": "Yoga", "lesson_type": "GROUPLESSON", "time": "10:00"}]
    registered = []

    def fake_perform_oplossing(olympos, lesson):
        raise BusinessException("niet aanwezig", "Not found")

    monkeypatch.setattr("tasks.perform_oplossing", fake_perform_oplossing)

    logs = []

    def fake_log(lesson, msg):
        logs.append(msg)

    def fake_save(lessons_arg):
        pass

    process_lessons(
        dummy_olympos,
        lessons,
        attempt=0,
        registered_lessons=registered,
        save_func=fake_save,
        log_attempt_func=fake_log,
    )
    assert any("Not found" in msg for msg in logs)


def test_process_lessons_business_exception_other(monkeypatch, dummy_olympos):
    lessons = [{"name": "Yoga", "lesson_type": "GROUPLESSON", "time": "10:00"}]
    registered = []

    def fake_perform_oplossing(olympos, lesson):
        raise BusinessException("other", "Some other error")

    monkeypatch.setattr("tasks.perform_oplossing", fake_perform_oplossing)

    logs = []

    def fake_log(lesson, msg):
        logs.append(msg)

    def fake_save(lessons_arg):
        pass

    process_lessons(
        dummy_olympos,
        lessons,
        attempt=0,
        registered_lessons=registered,
        save_func=fake_save,
        log_attempt_func=fake_log,
        max_retries=1,
    )
    assert any("BusinessException" in msg for msg in logs)


def test_process_lessons_keyboardinterrupt(monkeypatch, dummy_olympos):
    lessons = [{"name": "Yoga", "lesson_type": "GROUPLESSON", "time": "10:00"}]
    registered = []

    def fake_perform_oplossing(olympos, lesson):
        raise KeyboardInterrupt()

    monkeypatch.setattr("tasks.perform_oplossing", fake_perform_oplossing)

    def fake_log(lesson, msg):
        pass

    def fake_save(lessons_arg):
        pass

    with pytest.raises(KeyboardInterrupt):
        process_lessons(
            dummy_olympos,
            lessons,
            attempt=0,
            registered_lessons=registered,
            save_func=fake_save,
            log_attempt_func=fake_log,
            max_retries=1,
        )


def test_process_lessons_exception_and_retry(monkeypatch, dummy_olympos):
    lessons = [
        {"name": "Yoga", "lesson_type": "GROUPLESSON", "time": "10:00"},
        {"name": "Pilates", "lesson_type": "GROUPLESSON", "time": "11:00"},
    ]
    registered = []

    call_count = {"count": 0}

    # Patch perform_oplossing so that on first call for "Yoga" it fails, on retry it succeeds
    def perform_oplossing_side_effect(olympos, lesson):
        if lesson["name"] == "Yoga" and call_count.get("retried") is None:
            call_count["retried"] = True
            raise ApplicationException("fail")
        call_count["count"] += 1

    monkeypatch.setattr("tasks.perform_oplossing", perform_oplossing_side_effect)

    logs = []

    def fake_log(lesson, msg):
        logs.append((lesson["name"], msg))

    def fake_save(lessons_arg):
        pass

    process_lessons(
        dummy_olympos,
        lessons,
        attempt=0,
        registered_lessons=registered,
        save_func=fake_save,
        log_attempt_func=fake_log,
        max_retries=1,
    )
    # Should have retried at least once
    assert call_count["count"] >= 2
    assert any("Exception" in msg for _, msg in logs)


def test_process_lessons_stops_after_max_retries(monkeypatch, dummy_olympos):
    lessons = [{"name": "Yoga", "lesson_type": "GROUPLESSON", "time": "10:00"}]
    registered = []

    def fake_perform_oplossing(olympos, lesson):
        raise ApplicationException("fail always")

    monkeypatch.setattr("tasks.perform_oplossing", fake_perform_oplossing)

    logs = []

    def fake_log(lesson, msg):
        logs.append(msg)

    def fake_save(lessons_arg):
        pass

    # Patch log.warn to capture warning
    warnings = {}

    class DummyLog:
        def warn(self, msg, *args):
            warnings["warned"] = msg % args

    process_lessons(
        dummy_olympos,
        lessons,
        attempt=2,
        registered_lessons=registered,
        save_func=fake_save,
        log_attempt_func=fake_log,
        max_retries=1,
        log=DummyLog(),  # type: ignore
    )
    assert "The unprocessed items are:" in warnings["warned"]
