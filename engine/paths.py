import os
import sys

APP_DIR_NAME = "DesktopKitten"


def user_data_dir():
    """
    Returns a writable per-user directory for settings and logs.

    A frozen PyInstaller build unpacks to a temporary directory, so anything
    written next to __file__ or sys.executable is discarded on exit. Settings
    and crash reports have to live outside the bundle to survive a restart.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")

    path = os.path.join(base, APP_DIR_NAME)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return os.path.abspath(".")
    return path


def user_data_file(filename):
    return os.path.join(user_data_dir(), filename)


def legacy_settings_path(filename="settings.json"):
    """Pre-1.1 location: next to the script. Only used to migrate old settings once."""
    return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), filename)
