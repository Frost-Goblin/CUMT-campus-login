from __future__ import annotations

from paths import FONT_DIR

APP_USER_MODEL_ID = "CUMT.CampusLogin"
APP_DISPLAY_NAME = "CUMT 校园网登录器"
APP_VERSION = "v1.0.0"
OPERATORS = [
    ("中国电信", "@telecom"),
    ("中国移动", "@cmcc"),
    ("中国联通", "@unicom"),
    ("校园网", ""),
]

ALLOWED_CAMPUS_SSIDS = ("CUMT_Stu", "CUMT_Tec")

ICON_COLOR = "#24324d"
UI_RADIUS = 10
INPUT_HEIGHT = 40
FORM_LABEL_WIDTH = 60
SETTINGS_PANEL_WIDTH = 304
TRAILING_ICON_AREA_WIDTH = 42
TRAILING_ICON_SIZE = 22
WINDOW_MIN_WIDTH = 460
WINDOW_MIN_HEIGHT = 730
DEFAULT_APP_FONT_FAMILY = "Microsoft YaHei UI"

TYPOGRAPHY = {
    "app": {"size": 14, "weight": 400},
    "window_title": {"size": 30, "weight": 700},
    "title_brand": {"size": 26, "weight": 700},
    "title_text": {"size": 25, "weight": 700},
    "title_button_icon": {"size": 12, "weight": 400},
    "title_settings_icon": {"size": 15, "weight": 400},
    "title_min_icon": {"size": 14, "weight": 400},
    "title_close_icon": {"size": 13, "weight": 400},
    "subtitle": {"size": 14, "weight": 400},
    "hint": {"size": 13, "weight": 400},
    "form_label": {"size": 16, "weight": 400},
    "status_badge": {"size": 16, "weight": 475},
    "status_icon": {"size": 24, "weight": 400},
    "section_title": {"size": 23, "weight": 500},
    "settings_title": {"size": 23, "weight": 500},
    "settings_section": {"size": 17, "weight": 700},
    "settings_option": {"size": 17, "weight": 500},
    "field": {"size": 16, "weight": 400},
    "button": {"size": 17, "weight": 490},
    "site_name": {"size": 16, "weight": 500},
    "tooltip": {"size": 14, "weight": 400},
    "checkbox": {"size": 14, "weight": 500},
}

LATENCY_TARGETS = (
    ("教务系统", "http://jwxk1.cumt.edu.cn/jwglxt/xtgl/login_slogin.html"),
    ("哔哩哔哩", "https://www.bilibili.com"),
    ("GitHub", "https://github.com"),
)
STARTUP_RUN_VALUE_NAME = "CampusLoginDesktop"
STATUS_INTERVAL_OPTIONS = (
    ("5 秒", 5),
    ("15 秒", 15),
    ("30 秒", 30),
    ("60 秒", 60),
    ("2 分钟", 120),
    ("10 分钟", 600),
)
DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS = 30
STARTUP_STATUS_MONITOR_DURATION_SECONDS = 60
STARTUP_STATUS_MONITOR_INTERVAL_SECONDS = 3
STARTUP_AUTO_LOGIN_MAX_ATTEMPTS = 5
STARTUP_AUTO_LOGIN_RETRY_INTERVAL_SECONDS = 5

NETWORK_ICON_GLYPHS = {
    "wifi": "\ue701",
    "ethernet": "\ue839",
    "none": "\ue711",
}

BUNDLED_FONT_PATHS = (
    FONT_DIR / "MiSansVF.subset.ttf",
    FONT_DIR / "MiSansVF.ttf",
)
