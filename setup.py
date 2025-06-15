import os
import warnings

import truststore  # type: ignore # Om een of andere reden herkent pyright dit package niet, terwijl die wel in environment zit
from dotenv import load_dotenv


def check_environment() -> None:
    if os.getenv("OLYMPOS_USERNAME") is None:
        raise ValueError("Please set env variables. Did you load the .env file?")


def setup() -> None:
    """
    1. Suppress unnecessary warnings (so needs te in front of imports generating warnings)
    2. Certificate management: Injects truststore
    3. Loads environment variables from .env file
    4. Checks the environment is 32-bit
    """
    warnings.filterwarnings("ignore", message="Apply externally defined coinit_flags", module="pywinauto")
    truststore.inject_into_ssl()
    load_dotenv()
    check_environment()


if __name__ == "__main__":
    setup()
