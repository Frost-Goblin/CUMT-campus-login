from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = BASE_DIR


def resolve_user_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "CUMT Campus Login"
    return Path.home() / "CUMT Campus Login"


USER_DATA_DIR = resolve_user_data_dir()
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = USER_DATA_DIR / "config.json"
RUNTIME_LOG_PATH = USER_DATA_DIR / "desktop_app_runtime.log"
RUNTIME_LOG_BACKUP_PATH = USER_DATA_DIR / "desktop_app_runtime.log.1"
RUNTIME_LOG_MAX_BYTES = 512 * 1024
UI_LOG_MAX_BLOCKS = 1000
FAULT_LOG_PATH = USER_DATA_DIR / "desktop_app_fault.log"
FONT_DIR = RESOURCE_DIR / "assets" / "fonts"
ICON_DIR = RESOURCE_DIR / "assets" / "icons"
APP_ICON_PATH = ICON_DIR / "app.png"
APP_ICO_PATH = ICON_DIR / "app.ico"
ACTIVE_APP_ICON_PATH = APP_ICON_PATH
PROJECT_GITHUB_URL = ""
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def append_runtime_log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if RUNTIME_LOG_PATH.exists() and RUNTIME_LOG_PATH.stat().st_size > RUNTIME_LOG_MAX_BYTES:
            RUNTIME_LOG_PATH.replace(RUNTIME_LOG_BACKUP_PATH)
    except Exception:
        pass

    with RUNTIME_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")
