import os
from datetime import datetime
from time import sleep

from pywinauto import timings
from pywinauto.application import Application, WindowSpecification
from robocorp import log
from robocorp.workitems import ApplicationException, BusinessException  # noqa: F401


class Olympos:
    def __init__(self, dummy_run: bool) -> None:
        self.dummy_run: bool = dummy_run
        self.app: Application | None = None
        self.main_window: WindowSpecification | None = None

    def start_and_login(self) -> None:
        """Go to Olympos web page and log in."""
        olympos_username = self._get_env("OLYMPOS_USERNAME")
        olympos_password = self._get_env("OLYMPOS_PASSWORD")

        Application().start(olympos_path)  # cannot immediately set self.app from start? It spawns a different process maybe?
        sleep(1)
        self.app = Application(backend="uia").connect(title_re=".*Olympos")
        self.main_window = self.app.window(title_re=".*Olympos")

        self.main_window.username.type_keys(olympos_username, with_spaces=True)
        self.main_window.password.type_keys(olympos_password, with_spaces=True)
        log.info("Ingelogd")

    def _get_env(self, var: str) -> str:
        value: str | None = os.getenv(var)
        if value is None:
            raise ValueError(f"Please set env variable {var}")
        return value
