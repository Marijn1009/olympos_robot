import os
import random
import re
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import cast

from playwright.sync_api import Locator, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError  # rename to avoid conflict with built-in TimeoutError
from playwright_stealth import StealthConfig, stealth_sync  # type: ignore
from robocorp import browser, log
from robocorp.workitems import ApplicationException, BusinessException


def press_sequentially_random(locator: Locator, input_text: str, min_delay: int = 40, max_delay: int = 120):
    """
    Types text into a Playwright element, pressing one key at a time with a random delay.
    Args:
        locator (Locator): Playwright Locator
        input_text (str): The string to type
        min_delay (int): Minimum delay between keys in ms
        max_delay (int): Maximum delay between keys in ms
    """
    for char in input_text:
        locator.press_sequentially(char)
        # Add a random delay (in seconds) between key presses, using a normal distribution
        mean_delay = (min_delay + max_delay) / 2
        stddev_delay = (max_delay - min_delay) / 6
        delay_ms = random.normalvariate(mean_delay, stddev_delay)
        sleep(max(0, delay_ms / 1000.0))


class Olympos:
    PLAYWRIGHT_AUTH_STATE_PATH = "work_directory/state.json"

    def __init__(self, dummy_run: bool) -> None:
        self.dummy_run: bool = dummy_run
        self.page: Page | None = None

    def _start(self) -> None:
        """Start the Olympos browser."""
        if Path(self.PLAYWRIGHT_AUTH_STATE_PATH).exists():
            self.page = browser.context(storage_state=self.PLAYWRIGHT_AUTH_STATE_PATH).new_page()
        else:
            self.page = browser.context().new_page()

        config = StealthConfig(navigator_user_agent=False)
        stealth_sync(self.page, config)

        self.page = browser.goto(url="https://www.olympos.nl/inloggen")
        self.page.set_default_timeout(60000)

    def _login(self) -> None:
        if self.page is None:
            raise ApplicationException(code="PAGE_NOT_INITIALIZED", message="Page is not initialized. Please call start_and_login() first.")

        olympos_username = self._get_env("OLYMPOS_USERNAME")
        olympos_password = self._get_env("OLYMPOS_PASSWORD")

        # weiger olympos cookies
        try:
            expect(self.page.get_by_role("button", name="Weigeren")).to_be_visible(timeout=5000)
            self.page.get_by_role("button", name="Weigeren").click()
        except AssertionError:
            pass

        # login
        sleep(0.5)
        press_sequentially_random(self.page.get_by_role("textbox", name="E-mailadres"), olympos_username)
        sleep(0.5)
        press_sequentially_random(self.page.get_by_role("textbox", name="Wachtwoord"), olympos_password)
        sleep(0.5)
        with self.page.expect_navigation():
            self.page.get_by_role("button", name="Inloggen").click()

        try:
            expect(self.page.get_by_role("heading", name="Mijn producten")).to_be_visible()
        except AssertionError as e:
            if self.page.get_by_role("alert").filter(has_text="robot").is_visible():
                raise BusinessException(code="ROBOT_DETECTED", message="Robot detected.") from e
            raise ApplicationException(code="LOGIN_FAILED", message="Login failed.") from e

        # save cookies to login automatically next time
        self.page.context.storage_state(path=self.PLAYWRIGHT_AUTH_STATE_PATH)

    def start_and_login(self) -> None:
        """Go to Olympos web page and log in."""
        self._start()
        self.page = cast(Page, self.page)  # tell pyright that page is not None

        try:
            # Already logged in due to cookies?
            expect(self.page.get_by_role("heading", name="Mijn producten")).to_be_visible()
            # if so, save current cookies again in case they have changed
            self.page.context.storage_state(path=self.PLAYWRIGHT_AUTH_STATE_PATH)
        except AssertionError:
            log.info("Not logged in, trying to log in...")
            with log.suppress_variables():
                self._login()

        log.info("Browser succesfully started and logged in.")

    def _get_env(self, var: str) -> str:
        value: str | None = os.getenv(var)
        if value is None:
            raise ValueError(f"Please set env variable {var}")
        return value

    def register_into_course(self, name: str, lesson_datetime: datetime) -> str:
        """Register into a course."""
        if self.page is None:
            raise ApplicationException(code="PAGE_NOT_INITIALIZED", message="Page is not initialized. Please call start_and_login() first.")

        self.page.goto("https://www.olympos.nl/tickets")

        description_map = {
            "AERIAL ACROBATIEK": "Aerial acrobatiek",
            "POLESPORTS": "Polesports",
            "CHEERLEADING": "Cheerleading",
        }

        button = self.page.get_by_role("link", name=f"Bestel nu Cursus {description_map.get(name, name)}")
        # extra wait until enabled. Default actionability checks or to_be_enabled() do not work here.
        expect(button).not_to_have_class(re.compile(r".*\bdisabled\b.*"))
        button.click()

        self.page.get_by_role("combobox", name="Groep").select_option("Inschrijven nieuwe cursus...")
        sleep(0.5)

        # Flexibly match course option using name and weekday abbreviation from lesson_datetime
        day_map = {0: "ma", 1: "di", 2: "we", 3: "do", 4: "vr", 5: "za", 6: "zo"}
        weekday_abbr = day_map[lesson_datetime.weekday()]
        # Build regex pattern to match course name and weekday abbreviation (do not escape spaces)
        pattern = re.compile(rf"{name}.*\b{weekday_abbr}\b.*", re.IGNORECASE)
        # Find all options in the combobox
        combobox = self.page.get_by_role("combobox", name="Inschrijven voor")
        options = combobox.locator("option").all()
        matched_option = None
        matched_option_disabled = False
        for option in options:
            option_text = option.inner_text()
            if pattern.search(option_text):
                matched_option = option.get_attribute("value")
                matched_option_disabled = option.get_attribute("disabled") is not None
                break
        if matched_option_disabled:
            raise BusinessException(code="COURSE_FULL", message=f"Cursus {name} op {weekday_abbr} is vol.")
        if matched_option:
            combobox.select_option(matched_option)
        else:
            raise BusinessException(code="COURSE_NOT_FOUND", message=f"Cursus {name} op {weekday_abbr} niet gevonden.")

        sleep(0.5)
        self.page.get_by_role("button", name="Inschrijven").nth(1).click()

        if self.dummy_run:
            comment = f"Dummy run: Registering into course {name} on {weekday_abbr}."
            log.info(comment)
            return comment

        self.complete_shopping_cart()

        comment = f"Registering into course {name} on {weekday_abbr}."
        log.info(comment)
        return comment

    def register_into_group_lesson(self, name: str, time: str) -> None:
        """Register into a group lesson."""
        if self.page is None:
            raise ApplicationException(code="PAGE_NOT_INITIALIZED", message="Page is not initialized. Please call start_and_login() first.")

        self.page.goto("https://www.olympos.nl/groepslessen")

        # Open select screen
        button = self.page.get_by_role("link", name="Reserveer nu Reserveren")
        # extra wait until enabled. Default actionability checks or to_be_enabled() do not work here.
        expect(button).not_to_have_class(re.compile(r".*\bdisabled\b.*"))
        button.click()
        self.page.get_by_role("button", name="Toevoegen").click()

        # filter for right name of lessons (in case of multiple pages/ avoid having to click next page)
        try:
            self.page.get_by_role("listbox", name="Activiteit").select_option(name)
        except PlaywrightTimeoutError as e:
            raise BusinessException(code="LESSON_NOT_FOUND", message=f"{name} niet aanwezig in groeplessen overzicht.") from e

        # select the right row/ exact lesson
        lesson = self.page.get_by_role("row").filter(has_text=re.compile(rf"^{re.escape(time)}.*"))
        try:
            expect(lesson).to_be_visible()
        except AssertionError as e:
            raise BusinessException(code="LESSON_NOT_FOUND", message=f"{name} op {time} is niet aanwezig in de lijst.") from e

        try:
            expect(lesson).not_to_have_class(re.compile(r".*\bdisabled\b.*"), timeout=500)  # if disabled, lesson is full
        except AssertionError as e:
            raise BusinessException(code="LESSON_FULL", message=f"{name} op {time} is vol.") from e

        lesson.click()

        # confirm and add to cart
        if self.dummy_run:
            log.info("Dummy run: Would add to cart group lesson %s at %s.", name, time)
            return

        with self.page.expect_navigation():
            self.page.get_by_role("button", name="Toevoegen").click()
        log.info("Added to cart: group lesson %s at %s.", name, time)

        self.complete_shopping_cart()
        log.info("Registered into group lesson %s at %s.", name, time)

    def complete_shopping_cart(self) -> None:
        """Complete the shopping cart."""
        if self.page is None:
            raise ApplicationException(code="PAGE_NOT_INITIALIZED", message="Page is not initialized. Please call start_and_login() first.")

        self.page.goto("https://www.olympos.nl/bestellen/winkelwagen")

        # TODO: Check of item dubbel in winkelwagen voorkomt. Altijd 1 boeken en niet meer

        self.page.get_by_role("button", name="Doorgaan").click()
        # Click the label, because checkbox has overlay
        # Click on left top corner to avoid link in middle
        self.page.locator('label[for="ShoppingCartForm-UpdateHead-CONDITIONS"]').click(position={"x": 10, "y": 10})
        self.page.get_by_role("button", name="Bestelling afronden").click()
        expect(self.page.get_by_role("heading", name="Bedankt voor je bestelling!")).to_be_visible()

    def scrape_registered_lessons(self) -> list[dict]:
        """Scrape the registered lessons."""
        if self.page is None:
            raise ApplicationException(code="PAGE_NOT_INITIALIZED", message="Page is not initialized. Please call start_and_login() first.")

        if not self.page.url.startswith("https://www.olympos.nl/mijn-actieve-producten"):
            self.page.goto("https://www.olympos.nl/mijn-actieve-producten")
        expect(self.page.get_by_role("heading", name="Mijn producten")).to_be_visible()

        # Match group lesson boxes:
        # Anchor of group lesson boxes
        group_lesson_header = self.page.get_by_role("strong").get_by_text("Reserveren Groepsles")
        # Full group lesson box
        group_lesson_locator = group_lesson_header.locator("..").locator("..").filter(has_text="Reserveringen")
        # Actually interesting part of the box
        group_lesson_geldigheid = group_lesson_locator.get_by_text("Geldigheid").locator("..")

        group_lessons: list[dict] = []
        for group_lesson in group_lesson_geldigheid.all():
            group_lesson_text = group_lesson.get_by_role("definition").first.inner_text()
            group_lessons.append(self.parse_group_lesson_text(group_lesson_text))

        return group_lessons

    @staticmethod
    def parse_group_lesson_text(group_lesson_text: str) -> dict:
        # Example input: "16 jun 2025 20:15 - 21:10 (POLESPORTS)"
        pattern = r"(\d{1,2} \w+ \d{4}) (\d{2}:\d{2}) – (\d{2}:\d{2}) \((.+)\)"  # noqa: RUF001
        match = re.match(pattern, group_lesson_text)
        if not match:
            raise ValueError(f"Could not parse group lesson text: {group_lesson_text}")

        date_str, start_time, end_time, name = match.groups()
        # Parse date and time
        dt_start = datetime.strptime(f"{date_str} {start_time}", "%d %b %Y %H:%M")
        # Get day as Dutch abbreviation (e.g., "Ma" for Monday)
        day_map = {0: "Ma", 1: "Di", 2: "Wo", 3: "Do", 4: "Vr", 5: "Za", 6: "Zo"}
        day = day_map[dt_start.weekday()]

        return {
            "name": name,
            "lesson_type": "GROUPLESSON",
            "day": day,
            "time": start_time,
            "datetime": dt_start.isoformat(),
        }
