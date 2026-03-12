from .base import *  # noqa: F403,F401

DEBUG = get_bool_env("DJANGO_DEBUG", True)  # type: ignore[name-defined]
ALLOWED_HOSTS = get_list_env(  # type: ignore[name-defined]
    "DJANGO_ALLOWED_HOSTS",
    ["localhost", "127.0.0.1", "0.0.0.0"],
)

