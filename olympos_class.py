import os
import random
import re
from pathlib import Path
from time import sleep
from typing import cast

from playwright_stealth import StealthConfig, stealth_sync  # type: ignore
from robocorp import browser, log
from robocorp.workitems import ApplicationException, BusinessException

from playwright.sync_api import Locator, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError  # rename to avoid conflict with built-in TimeoutError


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
    PLAYWRIGHT_AUTH_STATE_PATH = "playwright/.auth/state.json"

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
        self.page.set_default_timeout(5000)

    def _login(self) -> None:
        if self.page is None:
            raise ApplicationException(code="PAGE_NOT_INITIALIZED", message="Page is not initialized. Please call start_and_login() first.")

        olympos_username = self._get_env("OLYMPOS_USERNAME")
        olympos_password = self._get_env("OLYMPOS_PASSWORD")

        # weiger olympos cookies
        self.page.get_by_role("button", name="Weigeren").click()

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
            self._login()

        log.info("Browser succesfully started and logged in.")

    def _get_env(self, var: str) -> str:
        value: str | None = os.getenv(var)
        if value is None:
            raise ValueError(f"Please set env variable {var}")
        return value

    def register_into_course(self, name: str, time: str) -> str:
        """Register into a course."""
        if self.dummy_run:
            comment = f"Dummy run: Registering into course {name} at {time}."
            log.info(comment)
            return comment

        # Simulate the registration process
        comment = f"Registering into course {name} at {time}."
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
        self.page.get_by_role("button", name="Doorgaan").click()
        # Click the label, because checkbox has overlay
        # Click on left top corner to avoid link in middle
        self.page.locator('label[for="ShoppingCartForm-UpdateHead-CONDITIONS"]').click(position={"x": 10, "y": 10})
        self.page.get_by_role("button", name="Bestelling afronden").click()
        expect(self.page.get_by_role("heading", name="Bedankt voor je bestelling!")).to_be_visible()

        log.info("Shopping cart completed successfully.")
