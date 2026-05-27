from __future__ import annotations

import copy
import ctypes
import faulthandler
import json
import sys
import time
import traceback
from pathlib import Path

if sys.platform == "win32":
    from ctypes import wintypes

    import winreg

from PySide6.QtCore import QEvent, QRect, QRectF, QSize, QThread, QTimer, Qt, QUrl, qInstallMessageHandler
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QFont,
    QIcon,
    QMoveEvent,
    QPainter,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSizePolicy,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidgetAction,
    QWidget,
)

try:
    from winotify import Notification as WinotifyNotification
except ImportError:  # pragma: no cover - optional runtime dependency
    WinotifyNotification = None

from constants import (
    ALLOWED_CAMPUS_SSIDS,
    APP_DISPLAY_NAME,
    APP_VERSION,
    APP_USER_MODEL_ID,
    DEFAULT_APP_FONT_FAMILY,
    DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS,
    FORM_LABEL_WIDTH,
    INPUT_HEIGHT,
    LATENCY_TARGETS,
    NETWORK_ICON_GLYPHS,
    OPERATORS,
    SETTINGS_PANEL_WIDTH,
    STARTUP_AUTO_LOGIN_MAX_ATTEMPTS,
    STARTUP_AUTO_LOGIN_RETRY_INTERVAL_SECONDS,
    STARTUP_RUN_VALUE_NAME,
    STARTUP_STATUS_MONITOR_DURATION_SECONDS,
    STARTUP_STATUS_MONITOR_INTERVAL_SECONDS,
    STATUS_INTERVAL_OPTIONS,
    UI_RADIUS,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
)
from paths import (
    ACTIVE_APP_ICON_PATH,
    APP_ICON_PATH,
    BASE_DIR,
    CONFIG_PATH,
    FAULT_LOG_PATH,
    ICON_DIR,
    PROJECT_GITHUB_URL,
    USER_DATA_DIR,
    UI_LOG_MAX_BLOCKS,
    append_runtime_log,
)
from styles import (
    TYPOGRAPHY,
    build_app_style,
    load_bundled_font_families,
    pick_font_family,
    quote_font_family,
)
from widgets import (
    ClickableFrame,
    ClickableStatusBadge,
    FlatComboBox,
    PasswordLineEdit,
    ResizeGrip,
    TitleBar,
)
from workers import (
    ConnectivityWorker,
    LoginWorker,
    LogoutWorker,
    StatusWorker,
)

import main as portal_core


if sys.platform == "win32":
    class WindowsMessage(ctypes.Structure):
        _fields_ = (
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", wintypes.POINT),
        )


_SHOW_EXISTING_INSTANCE_MESSAGE_ID = 0


def get_show_existing_instance_message_id() -> int:
    global _SHOW_EXISTING_INSTANCE_MESSAGE_ID
    if sys.platform != "win32":
        return 0
    if not _SHOW_EXISTING_INSTANCE_MESSAGE_ID:
        user32 = ctypes.windll.user32
        user32.RegisterWindowMessageW.argtypes = (ctypes.c_wchar_p,)
        user32.RegisterWindowMessageW.restype = wintypes.UINT
        _SHOW_EXISTING_INSTANCE_MESSAGE_ID = int(
            user32.RegisterWindowMessageW("CUMT.CampusLogin.ShowExistingWindow")
        )
    return _SHOW_EXISTING_INSTANCE_MESSAGE_ID


def notify_existing_instance() -> None:
    if sys.platform != "win32":
        return
    message_id = get_show_existing_instance_message_id()
    if not message_id:
        return
    user32 = ctypes.windll.user32
    user32.PostMessageW.argtypes = (
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
    user32.PostMessageW.restype = wintypes.BOOL
    user32.PostMessageW(wintypes.HWND(0xFFFF), message_id, 0, 0)






def set_windows_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def acquire_single_instance_lock():
    if sys.platform != "win32":
        return None
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.GetLastError.restype = ctypes.c_uint32
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_bool

    handle = kernel32.CreateMutexW(None, True, "Local\\CUMT.CampusLogin.SingleInstance")
    already_exists = kernel32.GetLastError() == 183
    if already_exists:
        if handle:
            kernel32.CloseHandle(handle)
        return None
    return handle


def load_app_icon(fallback_provider) -> QIcon:
    icon_path = ACTIVE_APP_ICON_PATH
    if ACTIVE_APP_ICON_PATH.exists():
        icon_path = ACTIVE_APP_ICON_PATH
    elif APP_ICON_PATH.exists():
        icon_path = APP_ICON_PATH

    if icon_path.exists():
        icon = QIcon(str(icon_path.resolve()))
        if not icon.isNull():
            return icon
    return fallback_provider.standardIcon(QStyle.SP_DriveNetIcon)




def install_exception_logging() -> None:
    def handle_exception(exc_type, exc_value, exc_tb) -> None:
        append_runtime_log("Unhandled exception:")
        append_runtime_log("".join(traceback.format_exception(exc_type, exc_value, exc_tb)).rstrip())
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    def qt_message_handler(mode, context, message) -> None:
        append_runtime_log(f"Qt message: {message}")

    sys.excepthook = handle_exception
    qInstallMessageHandler(qt_message_handler)
    fault_handle = FAULT_LOG_PATH.open("a", encoding="utf-8")
    faulthandler.enable(file=fault_handle, all_threads=True)






class CampusLoginWindow(QMainWindow):
    def __init__(self, start_hidden: bool = False, from_startup: bool = False) -> None:
        super().__init__()
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.loaded_font_families = load_bundled_font_families()
        self.font_family = pick_font_family(
            self.loaded_font_families,
            "MiSans VF",
            "MiSans",
            fallback=DEFAULT_APP_FONT_FAMILY,
        )
        self.config = portal_core.load_config()
        self.config.setdefault("ui", {})
        self.worker_thread: QThread | None = None
        self.worker: LoginWorker | None = None
        self.logout_thread: QThread | None = None
        self.logout_worker: LogoutWorker | None = None
        self.status_thread: QThread | None = None
        self.status_worker: StatusWorker | None = None
        self.connectivity_thread: QThread | None = None
        self.connectivity_worker: ConnectivityWorker | None = None
        self.tray_icon: QSystemTrayIcon | None = None
        self.tray_status_label: QLabel | None = None
        self.tray_status_dot: QLabel | None = None
        self.tray_refresh_action: QAction | None = None
        self.tray_login_action: QAction | None = None
        self.tray_logout_action: QAction | None = None
        self.status_timer: QTimer | None = None
        self.startup_status_timer: QTimer | None = None
        self.refresh_spin_timer: QTimer | None = None
        self.refresh_spin_angle = 0
        self.refresh_spin_steps_remaining = 0
        self.refresh_renderer = QSvgRenderer(str((ICON_DIR / "refresh-status.svg").resolve()))
        self._allow_close = False
        self._is_busy = False
        self._initial_position_applied = False
        self._startup_tasks_started = False
        self._resize_grip_width = 10
        self._geometry_correction_in_progress = False
        self._settings_panel_width = SETTINGS_PANEL_WIDTH
        self._settings_panel_visible = False
        self._loading_ui_settings = False
        self._settings_signals_connected = False
        self._exit_waiting_threads_logged: set[str] = set()
        self._start_hidden = start_hidden
        self._from_startup = from_startup or start_hidden
        self._last_auto_connect_at = 0.0
        self._auto_connect_paused_for_session = False
        self._status_detection_paused_for_session = False
        self._current_login_is_manual = False
        self._startup_status_deadline = 0.0
        self._startup_auto_login_attempts = 0
        self._last_startup_auto_login_at = 0.0
        self._startup_auto_login_exhausted = False
        self._last_campus_connected_state: bool | None = None
        self._last_campus_authenticated_state: bool | None = None
        self._suppress_next_status_change_notification = False
        self._manual_status_refresh_pending = False
        self._status_thread_started_at = 0.0
        self.app_icon = load_app_icon(self.style())
        self.setWindowIcon(self.app_icon)

        self._build_ui()
        self._create_resize_grips()
        self._ensure_ui_config_defaults()
        self._load_ui_settings()
        self._load_form_from_config()
        if sys.platform == "win32":
            self.setAttribute(Qt.WA_NativeWindow, True)
            self.winId()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_window_constraints()
        if not self._initial_position_applied:
            self._initial_position_applied = True
            QTimer.singleShot(0, self._position_initial_window)
        if not self._startup_tasks_started:
            self._startup_tasks_started = True
            QTimer.singleShot(0, self._finish_startup)

    def start_hidden_startup_tasks(self) -> None:
        if self._startup_tasks_started:
            return
        self._startup_tasks_started = True
        QTimer.singleShot(0, self._finish_startup)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            self._update_resize_grips()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_resize_grips()
        self._refresh_window_constraints()
        self._constrain_window_geometry()

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        self._refresh_window_constraints()

    def nativeEvent(self, eventType, message):
        if sys.platform == "win32":
            try:
                native_message = WindowsMessage.from_address(int(message))
                if native_message.message == get_show_existing_instance_message_id():
                    QTimer.singleShot(0, self._show_window)
                    return True, 0
            except Exception:
                pass
        return super().nativeEvent(eventType, message)

    def _create_resize_grips(self) -> None:
        self._resize_grips = {
            "top": ResizeGrip(self, Qt.TopEdge, Qt.SizeVerCursor),
            "bottom": ResizeGrip(self, Qt.BottomEdge, Qt.SizeVerCursor),
        }
        self._update_resize_grips()

    def _update_resize_grips(self) -> None:
        if not hasattr(self, "_resize_grips"):
            return

        visible = not self.isMaximized()
        grip = self._resize_grip_width
        width = self.width()
        height = self.height()

        for widget in self._resize_grips.values():
            widget.setVisible(visible)
            widget.raise_()

        if not visible:
            return

        self._resize_grips["top"].setGeometry(0, 0, width, grip)
        self._resize_grips["bottom"].setGeometry(0, height - grip, width, grip)

    def _virtual_available_geometry(self) -> QRect:
        screens = QApplication.screens()
        if not screens:
            return QRect()

        rect = QRect(screens[0].availableGeometry())
        for screen in screens[1:]:
            rect = rect.united(screen.availableGeometry())
        return rect

    def _refresh_window_constraints(self) -> None:
        virtual = self._virtual_available_geometry()
        if virtual.isNull():
            return

        fixed_width = self.minimumWidth()
        max_height = min(
            max(self.minimumHeight(), self._main_page_max_height()),
            max(self.minimumHeight(), virtual.height()),
        )
        self.setMaximumSize(fixed_width, max_height)

    def _main_page_max_height(self) -> int:
        if not hasattr(self, "title_bar") or not hasattr(self, "main_content_widget"):
            return self.minimumHeight()

        self.main_content_widget.adjustSize()
        title_height = self.title_bar.sizeHint().height()
        main_height = self.main_content_widget.sizeHint().height()
        max_height = title_height + main_height
        return max(self.minimumHeight(), max_height)

    def _constrain_window_geometry(self) -> None:
        if self._geometry_correction_in_progress or self.isMaximized():
            return

        virtual = self._virtual_available_geometry()
        if virtual.isNull():
            return

        geometry = self.geometry()
        fixed_width = self.minimumWidth()
        max_height = min(
            max(self.minimumHeight(), self._main_page_max_height()),
            max(self.minimumHeight(), virtual.height()),
        )

        width = fixed_width
        height = min(max(geometry.height(), self.minimumHeight()), max_height)
        x = geometry.x()
        y = geometry.y()

        if x < virtual.left():
            x = virtual.left()
        if y < virtual.top():
            y = virtual.top()
        if x + width > virtual.right() + 1:
            x = virtual.right() - width + 1
        if y + height > virtual.bottom() + 1:
            y = virtual.bottom() - height + 1

        corrected = QRect(x, y, width, height)
        if corrected == geometry:
            return

        self._geometry_correction_in_progress = True
        try:
            self.setGeometry(corrected)
        finally:
            self._geometry_correction_in_progress = False

    def _finish_startup(self) -> None:
        append_runtime_log("Startup tasks begin")
        self._create_tray()
        if sys.platform == "win32":
            QTimer.singleShot(1500, self._sync_startup_registration)
        self._start_startup_status_monitor()
        if self._start_hidden and self.tray_icon and self.isVisible():
            QTimer.singleShot(0, self._minimize_to_tray)
        append_runtime_log("Startup tasks complete")

    def _position_initial_window(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        width = min(self.minimumWidth(), available.width())
        height = min(self.height(), available.height())
        self.resize(width, height)

        x = available.left() + max(0, (available.width() - width) // 2)
        y = available.top() + max(0, (available.height() - height) // 2)
        self.move(x, y)

    def _ensure_window_visible(self) -> None:
        if not self.isVisible():
            return

        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        frame = self.frameGeometry()
        x = frame.left()
        y = frame.top()

        if frame.right() > available.right():
            x = available.right() - frame.width() + 1
        if frame.bottom() > available.bottom():
            y = available.bottom() - frame.height() + 1
        if frame.left() < available.left():
            x = available.left()
        if frame.top() < available.top():
            y = available.top()

        self.move(x, y)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.window_surface = QFrame()
        self.window_surface.setObjectName("windowSurface")
        outer.addWidget(self.window_surface)

        surface_layout = QVBoxLayout(self.window_surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)

        self.title_bar = TitleBar(self)
        surface_layout.addWidget(self.title_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.main_scroll = scroll
        content_shell = QWidget()
        content_layout = QHBoxLayout(content_shell)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        content_layout.setAlignment(Qt.AlignLeft)
        surface_layout.addWidget(content_shell, 1)

        content_layout.addWidget(scroll, 0)

        self.settings_panel = self._build_settings_panel()
        self.settings_panel.setMinimumWidth(self._settings_panel_width)
        self.settings_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.settings_shell = QWidget()
        settings_shell_layout = QVBoxLayout(self.settings_shell)
        settings_shell_layout.setContentsMargins(10, 8, 10, 8)
        settings_shell_layout.setSpacing(0)
        settings_shell_layout.addWidget(self.settings_panel)
        self.settings_shell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.settings_shell.setVisible(False)
        content_layout.addWidget(self.settings_shell, 1)

        body = QWidget()
        self.main_content_widget = body
        scroll.setWidget(body)

        outer = QVBoxLayout(body)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(16)

        header_card = self._make_card()
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(10)

        status_box = QHBoxLayout()
        status_box.setSpacing(8)
        self.network_icon_label = QLabel(NETWORK_ICON_GLYPHS["none"])
        self.network_icon_label.setObjectName("statusIcon")
        self.network_icon_label.setAlignment(Qt.AlignCenter)
        status_box.addWidget(self.network_icon_label, alignment=Qt.AlignVCenter)

        self.connection_badge = QLabel("校园网未检测")
        self.connection_badge.setObjectName("statusBadge")
        self.connection_badge.setFont(self._make_typography_font("status_badge"))
        status_box.addWidget(self.connection_badge)

        self.auth_badge = ClickableStatusBadge("登录未检测")
        self.auth_badge.setObjectName("statusBadge")
        self.auth_badge.setFont(self._make_typography_font("status_badge"))
        self.auth_badge.setToolTip("打开校园网登录页")
        self.auth_badge.clicked.connect(self._open_portal_page)
        status_box.addWidget(self.auth_badge)
        header_layout.addLayout(status_box)
        header_layout.addStretch()

        self.status_refresh_button = QPushButton()
        self.status_refresh_button.setObjectName("statusActionButton")
        self.status_refresh_button.setToolTip("刷新状态")
        self.refresh_icon = QIcon(str((ICON_DIR / "refresh-status.svg").resolve()))
        self.status_refresh_button.setIcon(self.refresh_icon)
        self.status_refresh_button.setIconSize(QSize(18, 18))
        self.status_refresh_button.setFocusPolicy(Qt.NoFocus)
        self.status_refresh_button.setAutoDefault(False)
        self.status_refresh_button.setDefault(False)
        self.status_refresh_button.clicked.connect(
            lambda: self._refresh_environment_status(force=True, visual_feedback=True)
        )
        header_layout.addWidget(self.status_refresh_button)

        config_card = self._make_card()
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(16, 16, 16, 16)
        config_layout.setSpacing(12)

        config_header = QLabel("登录配置")
        config_header.setObjectName("sectionTitle")
        config_header.setFont(self._make_section_title_font())
        config_layout.addWidget(config_header)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)

        self.username_edit = QLineEdit()
        self.username_edit.setObjectName("plainInput")
        self.username_edit.setFixedHeight(INPUT_HEIGHT)
        self.username_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.username_edit.setFont(self._make_operator_font(16))
        self.username_edit.setPlaceholderText("请输入学号或账号")
        self.username_edit.textChanged.connect(self._update_form_action_buttons)

        self.password_edit = PasswordLineEdit()
        self.password_edit.setFixedHeight(INPUT_HEIGHT)
        self.password_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.password_edit.setFont(self._make_operator_font(16))
        self.password_edit.setPlaceholderText("请输入密码")
        self.password_edit.textChanged.connect(self._update_form_action_buttons)

        self.operator_combo = FlatComboBox()
        self.operator_combo.setFont(self._make_operator_font(16))
        self.operator_combo.view().setFont(self._make_operator_font(16))
        for label, suffix in OPERATORS:
            self.operator_combo.addItem(label, suffix)

        form.addRow("账号", self.username_edit)
        form.addRow("密码", self.password_edit)
        form.addRow("运营商", self.operator_combo)
        config_layout.addLayout(form)

        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.LabelRole)
            if label_item is None:
                continue
            label_widget = label_item.widget()
            if isinstance(label_widget, QLabel):
                label_widget.setObjectName("formLabel")
                label_widget.setFixedWidth(FORM_LABEL_WIDTH)
                label_widget.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                label_widget.setFont(self._make_form_label_font())

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self.save_button = QPushButton("保存配置")
        self.save_button.setObjectName("secondary")
        self.save_button.setFont(self._make_button_font(16))
        self.save_button.setMinimumWidth(108)
        self.save_button.clicked.connect(self._save_config)
        button_row.addWidget(self.save_button)

        self.login_button = QPushButton("立即登录")
        self.login_button.setObjectName("primary")
        self.login_button.setFont(self._make_button_font(16))
        self.login_button.setMinimumWidth(108)
        self.login_button.clicked.connect(lambda: self._start_login(manual=True))
        button_row.addWidget(self.login_button)

        self.logout_button = QPushButton("注销")
        self.logout_button.setObjectName("danger")
        self.logout_button.setFont(self._make_button_font(16))
        self.logout_button.setMinimumWidth(88)
        self.logout_button.clicked.connect(self._start_logout)
        button_row.addWidget(self.logout_button)

        button_row.addStretch()
        config_layout.addLayout(button_row)

        self.last_result_label = QLabel("尚未执行登录。")
        self.last_result_label.setObjectName("subtitle")
        self.last_result_label.setWordWrap(True)
        config_layout.addWidget(self.last_result_label)

        tools_card = self._make_card()
        tools_layout = QVBoxLayout(tools_card)
        tools_layout.setContentsMargins(16, 16, 16, 16)
        tools_layout.setSpacing(10)
        tools_layout.setAlignment(Qt.AlignTop)

        tools_title = QLabel("状态与诊断")
        tools_title.setObjectName("sectionTitle")
        tools_title.setFont(self._make_section_title_font())
        tools_layout.addWidget(tools_title)

        self.env_summary_label = QLabel("正在检测当前网络环境。")
        self.env_summary_label.setObjectName("hint")
        self.env_summary_label.setWordWrap(True)
        tools_layout.addWidget(self.env_summary_label)

        tools_buttons = QHBoxLayout()
        tools_buttons.setSpacing(6)

        self.detect_button = QPushButton("连通性测试")
        self.detect_button.setObjectName("ghost")
        self.detect_button.setFont(self._make_button_font(16))
        self.detect_button.setCheckable(True)
        self.detect_button.clicked.connect(lambda: self._show_tools_page("latency"))
        tools_buttons.addWidget(self.detect_button)

        self.details_toggle = QPushButton("显示网络详情")
        self.details_toggle.setObjectName("ghost")
        self.details_toggle.setFont(self._make_button_font(16))
        self.details_toggle.setCheckable(True)
        self.details_toggle.clicked.connect(lambda: self._show_tools_page("details"))
        tools_buttons.addWidget(self.details_toggle)

        self.log_toggle = QPushButton("显示运行日志")
        self.log_toggle.setObjectName("ghost")
        self.log_toggle.setFont(self._make_button_font(16))
        self.log_toggle.setCheckable(True)
        self.log_toggle.clicked.connect(lambda: self._show_tools_page("log"))
        tools_buttons.addWidget(self.log_toggle)
        tools_layout.addLayout(tools_buttons)

        self.tools_stack = QStackedWidget()
        self.tools_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tools_layout.addWidget(self.tools_stack, 1)

        latency_page = QWidget()
        latency_layout = QVBoxLayout(latency_page)
        latency_layout.setContentsMargins(0, 6, 0, 0)
        latency_layout.setSpacing(10)
        latency_hint = QLabel("选择下方按钮后即可测试三个目标网站的连通性。")
        latency_hint.setObjectName("hint")
        latency_hint.setWordWrap(True)
        latency_layout.addWidget(latency_hint)

        self.latency_result_labels: dict[str, QLabel] = {}
        for site_name, site_url in LATENCY_TARGETS:
            row = ClickableFrame()
            row.setObjectName("card")
            row.setCursor(Qt.PointingHandCursor)
            row.setToolTip(f"打开 {site_name}")
            row.clicked.connect(lambda url=site_url: QDesktopServices.openUrl(QUrl(url)))
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)
            row_layout.setSpacing(12)

            text_layout = QVBoxLayout()
            text_layout.setContentsMargins(0, 0, 0, 0)
            text_layout.setSpacing(2)

            name_label = QLabel(site_name)
            name_label.setFont(self._make_site_name_font(16))
            text_layout.addWidget(name_label)

            url_label = QLabel(site_url)
            url_label.setObjectName("hint")
            url_label.setWordWrap(True)
            text_layout.addWidget(url_label)

            result_label = QLabel("未测速")
            result_label.setFont(self._make_button_font(15))
            result_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            result_label.setMinimumWidth(120)
            self.latency_result_labels[site_name] = result_label

            row_layout.addLayout(text_layout, 1)
            row_layout.addWidget(result_label)
            latency_layout.addWidget(row)

        self.run_latency_button = QPushButton("开始测试")
        self.run_latency_button.setObjectName("secondary")
        self.run_latency_button.setFont(self._make_button_font(16))
        self.run_latency_button.setMinimumWidth(120)
        self.run_latency_button.clicked.connect(self._start_connectivity_test)
        latency_layout.addWidget(self.run_latency_button, alignment=Qt.AlignLeft)
        latency_layout.addStretch(1)
        self.tools_stack.addWidget(latency_page)

        details_page = QWidget()
        details_layout = QVBoxLayout(details_page)
        details_layout.setContentsMargins(0, 6, 0, 0)
        details_layout.setSpacing(10)
        self.env_details = QLabel("")
        self.env_details.setObjectName("hint")
        self.env_details.setFont(self._make_typography_font("hint", pixel_size=14))
        self.env_details.setWordWrap(True)
        self.env_details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details_layout.addWidget(self.env_details)
        details_layout.addStretch(1)
        self.tools_stack.addWidget(details_page)

        log_page = QWidget()
        log_layout = QVBoxLayout(log_page)
        log_layout.setContentsMargins(0, 6, 0, 0)
        log_layout.setSpacing(10)
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(UI_LOG_MAX_BLOCKS)
        self.log_output.setMinimumHeight(220)
        self.log_output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(self.log_output, 1)
        self.tools_stack.addWidget(log_page)

        self._tool_pages = {
            "latency": 0,
            "details": 1,
            "log": 2,
        }
        self._tool_buttons = {
            "latency": self.detect_button,
            "details": self.details_toggle,
            "log": self.log_toggle,
        }
        self._show_tools_page("latency")

        outer.addWidget(header_card)
        outer.addWidget(config_card)
        outer.addWidget(tools_card)
        outer.addStretch(1)

        self.setStyleSheet(
            build_app_style(quote_font_family(self.font_family))
        )
        QTimer.singleShot(0, self._sync_content_minimum_widths)

    def _build_settings_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("settingsPanel")
        panel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 20, 18, 18)
        layout.setSpacing(14)

        title = QLabel("设置")
        title.setObjectName("settingsTitle")
        title.setFont(self._make_typography_font("settings_title"))
        layout.addWidget(title)

        def add_section_header(text: str) -> QLabel:
            header = QLabel(text)
            header.setObjectName("settingsSection")
            layout.addWidget(header)
            return header

        def add_separator() -> None:
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Plain)
            line.setStyleSheet("background: #ffffff; border: none; border-top: 1px solid #eef2f8;")
            layout.addWidget(line)

        close_label = QLabel("关闭后")
        close_label.setObjectName("settingsOptionLabel")
        layout.addWidget(close_label)
        self.close_behavior_combo = FlatComboBox()
        self.close_behavior_combo.setFont(self._make_operator_font(16))
        self.close_behavior_combo.view().setFont(self._make_operator_font(16))
        self.close_behavior_combo.addItem("最小化到系统托盘", "tray")
        self.close_behavior_combo.addItem("直接退出（关闭程序）", "exit")
        layout.addWidget(self.close_behavior_combo)

        add_separator()
        self.system_notifications_check = QCheckBox("启用系统通知")
        self.system_notifications_check.setObjectName("settingsOptionCheck")
        layout.addWidget(self.system_notifications_check)

        add_separator()
        self.startup_enabled_check = QCheckBox("启用开机自启动")
        self.startup_enabled_check.setObjectName("settingsOptionCheck")
        layout.addWidget(self.startup_enabled_check)

        self.startup_mode_row = QWidget()
        startup_mode_layout = QVBoxLayout(self.startup_mode_row)
        startup_mode_layout.setContentsMargins(0, 0, 0, 0)
        startup_mode_layout.setSpacing(8)
        self.startup_mode_combo = FlatComboBox()
        self.startup_mode_combo.setFont(self._make_operator_font(16))
        self.startup_mode_combo.view().setFont(self._make_operator_font(16))
        self.startup_mode_combo.addItem("开机时打开主页面", "show")
        self.startup_mode_combo.addItem("开机时隐藏在托盘", "tray")
        startup_mode_layout.addWidget(self.startup_mode_combo)
        layout.addWidget(self.startup_mode_row)

        add_separator()
        self.monitor_check = QCheckBox("后台定时检测连接状态")
        self.monitor_check.setObjectName("settingsOptionCheck")
        layout.addWidget(self.monitor_check)

        self.monitor_options_row = QWidget()
        monitor_options_layout = QVBoxLayout(self.monitor_options_row)
        monitor_options_layout.setContentsMargins(0, 0, 0, 0)
        monitor_options_layout.setSpacing(8)
        self.monitor_hint_label = QLabel("关闭后仍会在启动时自动检测登录状态")
        self.monitor_hint_label.setObjectName("hint")
        self.monitor_hint_label.setWordWrap(True)
        monitor_options_layout.addWidget(self.monitor_hint_label)
        self.monitor_interval_combo = FlatComboBox()
        self.monitor_interval_combo.setFont(self._make_operator_font(16))
        self.monitor_interval_combo.view().setFont(self._make_operator_font(16))
        for label, seconds in STATUS_INTERVAL_OPTIONS:
            self.monitor_interval_combo.addItem(label, seconds)
        monitor_options_layout.addWidget(self.monitor_interval_combo)
        layout.addWidget(self.monitor_options_row)

        add_separator()
        self.auto_connect_check = QCheckBox("检测到校园网未登录时自动登录")
        self.auto_connect_check.setObjectName("settingsOptionCheck")
        layout.addWidget(self.auto_connect_check)
        self.auto_connect_pause_label = QLabel("自动检测和自动登录已临时停止，手动登录成功后恢复。")
        self.auto_connect_pause_label.setObjectName("hint")
        self.auto_connect_pause_label.setWordWrap(True)
        self.auto_connect_pause_label.setVisible(False)
        layout.addWidget(self.auto_connect_pause_label)

        add_separator()
        settings_actions = QHBoxLayout()
        settings_actions.setSpacing(8)

        self.open_config_dir_button = QPushButton("打开配置文件夹")
        self.open_config_dir_button.setObjectName("ghost")
        self.open_config_dir_button.setFont(self._make_settings_action_font())
        self.open_config_dir_button.clicked.connect(self._open_user_data_dir)
        settings_actions.addWidget(self.open_config_dir_button)

        self.open_github_button = QPushButton("打开项目地址")
        self.open_github_button.setObjectName("ghost")
        self.open_github_button.setFont(self._make_settings_action_font())
        self.open_github_button.setIcon(QIcon(str((ICON_DIR / "github.svg").resolve())))
        self.open_github_button.setIconSize(QSize(18, 18))
        self.open_github_button.clicked.connect(self._open_project_github)
        settings_actions.addWidget(self.open_github_button)
        layout.addLayout(settings_actions)

        version_label = QLabel(f"版本 {APP_VERSION}")
        version_label.setObjectName("hint")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setFont(self._make_typography_font("hint", pixel_size=13))
        layout.addWidget(version_label)

        layout.addStretch(1)
        return panel

    def _make_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        return card

    def _make_form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("formLabel")
        label.setFixedWidth(FORM_LABEL_WIDTH)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return label

    def _make_font(self, family: str, pixel_size: int, weight: int | QFont.Weight) -> QFont:
        font = QFont(family)
        font.setPixelSize(pixel_size)
        font.setWeight(weight if isinstance(weight, QFont.Weight) else QFont.Weight(weight))
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        return font

    def _make_typography_font(
        self,
        role: str,
        pixel_size: int | None = None,
        weight: int | QFont.Weight | None = None,
    ) -> QFont:
        values = TYPOGRAPHY[role]
        return self._make_font(
            self.font_family,
            pixel_size if pixel_size is not None else int(values["size"]),
            weight if weight is not None else int(values["weight"]),
        )

    def _make_button_font(self, size: int | None = None) -> QFont:
        return self._make_typography_font("button", pixel_size=size)

    def _make_settings_action_font(self) -> QFont:
        return self._make_typography_font("button", pixel_size=15, weight=600)

    def _make_title_font(self, pixel_size: int = 30) -> QFont:
        return self._make_typography_font("window_title", pixel_size=pixel_size)

    def _make_section_title_font(self, pixel_size: int | None = None) -> QFont:
        return self._make_typography_font("section_title", pixel_size=pixel_size)

    def _make_field_font(self, pixel_size: int | None = None) -> QFont:
        return self._make_typography_font("field", pixel_size=pixel_size)

    def _make_form_label_font(self, pixel_size: int | None = None) -> QFont:
        return self._make_typography_font("form_label", pixel_size=pixel_size)

    def _make_site_name_font(self, pixel_size: int | None = None) -> QFont:
        return self._make_typography_font("site_name", pixel_size=pixel_size)

    def _make_operator_font(self, pixel_size: int | None = None) -> QFont:
        return self._make_typography_font("field", pixel_size=pixel_size)

    def _show_tools_page(self, page_name: str) -> None:
        self.tools_stack.setCurrentIndex(self._tool_pages[page_name])
        for key, button in self._tool_buttons.items():
            button.blockSignals(True)
            button.setChecked(key == page_name)
            button.blockSignals(False)

    def _toggle_settings_panel(self) -> None:
        self._set_settings_panel_visible(not self._settings_panel_visible)

    def _set_settings_panel_visible(self, visible: bool) -> None:
        self._settings_panel_visible = visible
        self.main_scroll.setVisible(not visible)
        self.settings_shell.setVisible(visible)
        self.title_bar.settings_button.blockSignals(True)
        self.title_bar.settings_button.setChecked(visible)
        self.title_bar.settings_button.setToolTip("返回主页面" if visible else "显示设置")
        self.title_bar.settings_button.blockSignals(False)
        self._sync_content_minimum_widths()

    def _latency_result_color(self, latency_ms: int | float | None, ok: bool) -> str:
        if not ok or latency_ms is None:
            return "#dc2626"
        if latency_ms < 100:
            return "#159669"
        if latency_ms < 300:
            return "#b77905"
        return "#e0532f"

    def _update_latency_result_widgets(self, latency_tests: list[dict] | None = None) -> None:
        latest = {item.get("name"): item for item in (latency_tests or [])}
        for site_name, label in self.latency_result_labels.items():
            item = latest.get(site_name)
            if not item:
                label.setText("未测速")
                label.setStyleSheet("color: #152033;")
            elif item.get("ok"):
                latency_ms = item.get("latency_ms")
                label.setText(f"{latency_ms if latency_ms is not None else '-'} ms")
                label.setStyleSheet(
                    f"color: {self._latency_result_color(latency_ms, True)};"
                )
            else:
                label.setText("不可达")
                label.setStyleSheet("color: #dc2626;")

    def _sync_content_minimum_widths(self) -> None:
        self.main_content_widget.adjustSize()
        main_min_width = self.main_content_widget.sizeHint().width()
        if main_min_width <= 0:
            return

        self.main_content_widget.setMinimumWidth(main_min_width)
        self.main_content_widget.setMaximumWidth(main_min_width)
        self.main_scroll.setMinimumWidth(main_min_width)
        self.main_scroll.setMaximumWidth(main_min_width)
        settings_panel_width = max(0, main_min_width - 20)
        self.settings_shell.setMinimumWidth(main_min_width)
        self.settings_shell.setMaximumWidth(main_min_width)
        self.settings_panel.setMinimumWidth(settings_panel_width)
        self.settings_panel.setMaximumWidth(settings_panel_width)
        content_min_width = main_min_width
        title_min_width = self.title_bar.sizeHint().width()
        total_min_width = max(WINDOW_MIN_WIDTH, content_min_width, title_min_width)
        self.setMinimumWidth(total_min_width)
        self.setMaximumWidth(total_min_width)
        if not self._initial_position_applied or not self._settings_panel_visible:
            self.resize(total_min_width, self.height())
        self._refresh_window_constraints()

    def _ensure_ui_config_defaults(self) -> None:
        ui_config = self.config.setdefault("ui", {})
        legacy_close_behavior = ui_config.get("close_behavior", "tray")
        if legacy_close_behavior == "ask":
            legacy_close_behavior = "tray"
        ui_config["close_behavior"] = legacy_close_behavior
        ui_config.setdefault("startup_enabled", False)
        ui_config.setdefault("startup_mode", "show")
        ui_config.setdefault("status_monitor_enabled", False)
        ui_config.setdefault(
            "status_refresh_interval_seconds",
            DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS,
        )
        ui_config.setdefault("auto_connect_enabled", False)
        ui_config.setdefault("system_notifications_enabled", True)
        ui_config.setdefault("tray_minimize_notice_shown", False)

    def _load_ui_settings(self) -> None:
        self._loading_ui_settings = True
        ui_config = self.config["ui"]

        close_behavior = ui_config.get("close_behavior", "tray")
        close_index = next(
            (
                i
                for i in range(self.close_behavior_combo.count())
                if self.close_behavior_combo.itemData(i) == close_behavior
            ),
            0,
        )
        self.close_behavior_combo.setCurrentIndex(close_index)

        self.startup_enabled_check.setChecked(bool(ui_config.get("startup_enabled", False)))
        startup_mode = ui_config.get("startup_mode", "show")
        startup_mode_index = next(
            (
                i
                for i in range(self.startup_mode_combo.count())
                if self.startup_mode_combo.itemData(i) == startup_mode
            ),
            0,
        )
        self.startup_mode_combo.setCurrentIndex(startup_mode_index)

        self.monitor_check.setChecked(bool(ui_config.get("status_monitor_enabled", False)))
        monitor_interval = int(
            ui_config.get(
                "status_refresh_interval_seconds",
                DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS,
            )
        )
        monitor_interval_index = next(
            (
                i
                for i in range(self.monitor_interval_combo.count())
                if int(self.monitor_interval_combo.itemData(i)) == monitor_interval
            ),
            next(
                i
                for i in range(self.monitor_interval_combo.count())
                if int(self.monitor_interval_combo.itemData(i))
                == DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS
            ),
        )
        self.monitor_interval_combo.setCurrentIndex(monitor_interval_index)
        self.auto_connect_check.setChecked(bool(ui_config.get("auto_connect_enabled", False)))
        self.system_notifications_check.setChecked(
            bool(ui_config.get("system_notifications_enabled", True))
        )

        self._loading_ui_settings = False
        self._update_settings_ui_state()

        if not self._settings_signals_connected:
            self.system_notifications_check.toggled.connect(self._save_ui_settings)
            self.startup_enabled_check.toggled.connect(self._save_ui_settings)
            self.startup_mode_combo.currentIndexChanged.connect(self._save_ui_settings)
            self.monitor_check.toggled.connect(self._save_ui_settings)
            self.monitor_interval_combo.currentIndexChanged.connect(self._save_ui_settings)
            self.auto_connect_check.toggled.connect(self._save_ui_settings)
            self.close_behavior_combo.currentIndexChanged.connect(self._save_ui_settings)
            self._settings_signals_connected = True

    def _save_ui_settings(self, *_args) -> None:
        if self._loading_ui_settings:
            return

        previous_ui_config = copy.deepcopy(self.config.get("ui", {}))
        ui_config = self.config.setdefault("ui", {})
        ui_config["close_behavior"] = self.close_behavior_combo.currentData() or "tray"
        ui_config["startup_enabled"] = self.startup_enabled_check.isChecked()
        ui_config["startup_mode"] = self.startup_mode_combo.currentData() or "show"
        ui_config["status_monitor_enabled"] = self.monitor_check.isChecked()
        ui_config["status_refresh_interval_seconds"] = int(
            self.monitor_interval_combo.currentData()
            or DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS
        )
        ui_config["auto_connect_enabled"] = self.auto_connect_check.isChecked()
        ui_config["system_notifications_enabled"] = self.system_notifications_check.isChecked()
        self._update_settings_ui_state()
        try:
            self._sync_startup_registration()
            self._write_config()
            self._apply_status_monitor_settings()
        except OSError as exc:
            self.config["ui"] = previous_ui_config
            self._loading_ui_settings = True
            self._load_ui_settings()
            self._loading_ui_settings = False
            QMessageBox.warning(
                self,
                "设置保存失败",
                f"无法更新开机自启动设置。\n\n{str(exc).strip()}",
            )

    def _update_settings_ui_state(self) -> None:
        startup_enabled = self.startup_enabled_check.isChecked()
        self.startup_mode_row.setEnabled(startup_enabled)
        self.startup_mode_combo.setEnabled(startup_enabled)

        monitor_enabled = self.monitor_check.isChecked()
        self.monitor_options_row.setEnabled(monitor_enabled)
        self.monitor_hint_label.setEnabled(True)
        self.monitor_interval_combo.setEnabled(monitor_enabled)
        self.auto_connect_pause_label.setVisible(self._auto_connect_paused_for_session)

    def _apply_status_monitor_settings(self) -> None:
        if self._status_detection_paused_for_session:
            if self.status_timer is not None:
                self.status_timer.stop()
                self.status_timer = None
            return
        if self.config["ui"].get("status_monitor_enabled", False):
            if self.startup_status_timer is not None:
                return
            self._start_status_monitor()
            return
        if self.status_timer is not None:
            self.status_timer.stop()
            self.status_timer = None

    def _pause_auto_detection_and_login_for_session(self, log_message: str | None = None) -> None:
        self._set_auto_connect_paused_for_session(True)
        self._status_detection_paused_for_session = True
        if self.startup_status_timer is not None:
            self.startup_status_timer.stop()
            self.startup_status_timer = None
        if self.status_timer is not None:
            self.status_timer.stop()
            self.status_timer = None
        self._update_settings_ui_state()
        if log_message:
            self._append_log(log_message)

    def _handle_access_window_rejection(self, message: str) -> None:
        notice = message or "当前时段不允许上网。"
        if self._looks_unreadable_message(notice):
            notice = "当前时段不允许上网。"
        self._append_log(notice)
        self.last_result_label.setText(notice)
        self._show_windows_notification("校园网登录受限", notice)
        self._pause_auto_detection_and_login_for_session(
            "当前时段不允许上网，已停止本次运行内的自动检测和自动登录。"
        )

    def _looks_unreadable_message(self, message: str | None) -> bool:
        text = str(message or "").strip()
        if not text:
            return True
        chars = [char for char in text if not char.isspace()]
        if not chars:
            return True
        bad_count = sum(1 for char in chars if char in {"?", "？", "�"})
        return bad_count >= 4 and bad_count / len(chars) >= 0.6

    def _login_message_for_result(self, result: dict, fallback: str) -> str:
        reason = str(result.get("reason", ""))
        message = str(result.get("message", "") or "").strip()
        reason_fallbacks = {
            "outside_access_window": "当前时段不允许上网。",
            "account_not_found": "账号不存在，请确认账号或运营商选择是否正确。",
            "invalid_credentials": "统一身份认证用户名密码错误！",
            "device_limit": "登录设备超限，请先下线其他设备。",
            "portal_rejected": "登录失败，门户返回信息无法识别。",
            "not_confirmed": "登录失败，未能确认联网成功。",
            "probe_error": "登录失败，无法访问校园网门户。",
        }
        if self._looks_unreadable_message(message):
            return reason_fallbacks.get(reason, fallback)
        return message

    def _handle_non_retriable_login_failure(self, result: dict) -> bool:
        reason = str(result.get("reason", ""))
        message = self._login_message_for_result(result, "登录失败。")
        stop_reasons = {
            "outside_access_window",
            "account_not_found",
            "invalid_credentials",
            "device_limit",
        }
        if reason not in stop_reasons:
            return False

        if reason == "outside_access_window":
            self._handle_access_window_rejection(message)
        else:
            self._pause_auto_detection_and_login_for_session(
                "已停止本次运行内的自动检测和自动登录。"
            )
            self._append_log(message)
            self.last_result_label.setText(message)
            self._show_windows_notification("校园网登录失败", message)
        return True

    def _resolve_startup_pythonw(self) -> str:
        executable = Path(sys.executable)
        if executable.name.lower() == "python.exe":
            pythonw = executable.with_name("pythonw.exe")
            if pythonw.exists():
                return str(pythonw)
        return str(executable)

    def _build_startup_command(self) -> str:
        startup_mode = self.config["ui"].get("startup_mode", "show")
        if getattr(sys, "frozen", False):
            command = f'"{sys.executable}" --from-startup'
        else:
            pythonw_path = self._resolve_startup_pythonw()
            script_path = str(BASE_DIR / "desktop_app.py")
            command = f'"{pythonw_path}" "{script_path}" --from-startup'
        if startup_mode == "tray":
            command += " --start-hidden"
        return command

    def _remove_startup_run_value(self) -> None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                try:
                    winreg.DeleteValue(key, STARTUP_RUN_VALUE_NAME)
                except FileNotFoundError:
                    pass
        except OSError:
            pass

    def _write_startup_run_value(self, command: str) -> None:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, STARTUP_RUN_VALUE_NAME, 0, winreg.REG_SZ, command)

    def _sync_startup_registration(self) -> None:
        if sys.platform != "win32":
            return
        if self.config["ui"].get("startup_enabled", False):
            self._install_startup_registration()
            return
        self._remove_startup_registration()

    def _install_startup_registration(self) -> None:
        command = self._build_startup_command()
        self._write_startup_run_value(command)

    def _remove_startup_registration(self) -> None:
        self._remove_startup_run_value()

    def _load_form_from_config(self) -> None:
        login_cfg = self.config["login"]

        self.username_edit.setText(login_cfg.get("username", ""))
        self.password_edit.setText(login_cfg.get("password", ""))
        self.config["portal"]["target_ssids"] = list(ALLOWED_CAMPUS_SSIDS)
        self.config["portal"]["target_ssid"] = ALLOWED_CAMPUS_SSIDS[0]

        suffix = login_cfg.get("account_suffix", "")
        combo_index = next(
            (index for index, (_, value) in enumerate(OPERATORS) if value == suffix),
            len(OPERATORS) - 1,
        )
        self.operator_combo.setCurrentIndex(combo_index)
        self._update_form_action_buttons()

    def _start_status_monitor(self) -> None:
        if self._status_detection_paused_for_session:
            return
        interval_seconds = int(
            self.config.get("ui", {}).get(
                "status_refresh_interval_seconds",
                DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS,
            )
        )
        interval_ms = max(1, interval_seconds) * 1000
        if self.status_timer is None:
            self.status_timer = QTimer(self)
            self.status_timer.timeout.connect(self._refresh_environment_status)
        self.status_timer.setInterval(interval_ms)
        self.status_timer.start()

    def _start_startup_status_monitor(self) -> None:
        if self._status_detection_paused_for_session:
            append_runtime_log("Startup status monitor skipped: detection paused for this session")
            return
        self._startup_auto_login_attempts = 0
        self._last_startup_auto_login_at = 0.0
        self._startup_auto_login_exhausted = False
        self._startup_status_deadline = (
            time.monotonic() + STARTUP_STATUS_MONITOR_DURATION_SECONDS
        )
        self.last_result_label.setText("正在检测校园网连接和登录状态。")
        append_runtime_log(
            "Startup status monitor started: "
            f"duration={STARTUP_STATUS_MONITOR_DURATION_SECONDS}s, "
            f"interval={STARTUP_STATUS_MONITOR_INTERVAL_SECONDS}s, "
            f"auto_connect={self.config.get('ui', {}).get('auto_connect_enabled', False)}"
        )

        if self.startup_status_timer is None:
            self.startup_status_timer = QTimer(self)
            self.startup_status_timer.timeout.connect(self._run_startup_status_monitor_tick)

        self.startup_status_timer.setInterval(
            max(1, STARTUP_STATUS_MONITOR_INTERVAL_SECONDS) * 1000
        )
        self.startup_status_timer.start()
        self._run_startup_status_monitor_tick(first_tick=True)

    def _run_startup_status_monitor_tick(self, first_tick: bool = False) -> None:
        if self._status_detection_paused_for_session:
            append_runtime_log("Startup status monitor stopped: detection paused for this session")
            self._stop_startup_status_monitor(final_text=None, start_background_monitor=False)
            return
        if self._is_busy or (self.worker_thread and self.worker_thread.isRunning()):
            append_runtime_log("Startup status monitor tick skipped: login/logout busy")
            return
        if time.monotonic() >= self._startup_status_deadline:
            append_runtime_log("Startup status monitor reached deadline")
            self._stop_startup_status_monitor()
            return

        append_runtime_log(f"Startup status monitor tick: first={first_tick}")
        if first_tick:
            self._refresh_environment_status(
                force=True,
                suppress_change_notification=True,
            )
            return

        self._refresh_environment_status(force=True)

    def _stop_startup_status_monitor(
        self,
        final_text: str | None = "启动检测已完成。",
        start_background_monitor: bool = True,
    ) -> None:
        if self.startup_status_timer is not None:
            self.startup_status_timer.stop()
            self.startup_status_timer = None

        if final_text and self.last_result_label.text().startswith("正在检测校园网"):
            self.last_result_label.setText(final_text)

        if (
            start_background_monitor
            and not self._status_detection_paused_for_session
            and self.config["ui"].get("status_monitor_enabled", False)
        ):
            self._start_status_monitor()

    def _set_status_badge(self, badge: QLabel, text: str, background: str) -> None:
        badge.setText(text)
        status_badge = TYPOGRAPHY["status_badge"]
        badge.setStyleSheet(
            "QLabel#statusBadge { "
            f"background: {background}; color: #ffffff; "
            f"font-family: {quote_font_family(self.font_family)}; "
            f"font-size: {status_badge['size']}px; "
            f"font-weight: {status_badge['weight']}; "
            f"border-radius: {UI_RADIUS}px; padding: 6px 12px; }}"
        )

    def _set_network_icon(self, network_type: str) -> None:
        self.network_icon_label.setText(
            NETWORK_ICON_GLYPHS.get(network_type, NETWORK_ICON_GLYPHS["none"])
        )

    def _open_portal_page(self) -> None:
        QDesktopServices.openUrl(QUrl("http://10.2.5.251/"))

    def _open_user_data_dir(self) -> None:
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(USER_DATA_DIR)))

    def _open_project_github(self) -> None:
        if not PROJECT_GITHUB_URL:
            self.last_result_label.setText("GitHub 项目地址暂未配置。")
            return
        QDesktopServices.openUrl(QUrl(PROJECT_GITHUB_URL))

    def _set_tray_auth_status(self, authenticated: bool) -> None:
        status_text = "已登录" if authenticated else "未登录"
        dot_color = "#16a34a" if authenticated else "#dc2626"
        self._set_tray_status(status_text, dot_color)

    def _set_tray_checking_status(self) -> None:
        self._set_tray_status("正在检测登录状态", "#2563eb")

    def _set_tray_logging_in_status(self) -> None:
        self._set_tray_status("正在登录", "#2563eb")

    def _set_tray_status(self, status_text: str, dot_color: str) -> None:
        if self.tray_status_label is not None:
            self.tray_status_label.setText(status_text)
        if self.tray_status_dot is not None:
            self.tray_status_dot.setStyleSheet(
                f"background: {dot_color}; border-radius: 5px;"
            )

        if self.tray_icon is not None:
            self.tray_icon.setToolTip(f"CUMT 校园网登录器 - {status_text}")

    def _sync_tray_actions(self) -> None:
        if self.tray_refresh_action is not None:
            self.tray_refresh_action.setEnabled(not self._is_busy)
        if self.tray_login_action is not None:
            form_complete = self._is_login_form_complete()
            self.tray_login_action.setEnabled((not self._is_busy) and form_complete)
            self.tray_login_action.setText("登录中..." if self._is_busy else "一键登录")
        if self.tray_logout_action is not None:
            self.tray_logout_action.setEnabled(not self._is_busy)

        authenticated = bool(self._last_campus_authenticated_state)
        if self._is_busy and self.worker_thread is not None:
            self._set_tray_logging_in_status()
        else:
            self._set_tray_auth_status(authenticated)

    def _set_auto_connect_paused_for_session(self, paused: bool) -> None:
        self._auto_connect_paused_for_session = paused
        if hasattr(self, "auto_connect_pause_label"):
            self.auto_connect_pause_label.setVisible(paused)
        self._sync_tray_actions()

    def _show_windows_notification(self, title: str, message: str) -> None:
        if not self.config.get("ui", {}).get("system_notifications_enabled", True):
            return

        if WinotifyNotification is not None and sys.platform == "win32":
            try:
                WinotifyNotification(
                    app_id=APP_USER_MODEL_ID,
                    title=title,
                    msg=message,
                    icon=str(ACTIVE_APP_ICON_PATH.resolve())
                    if ACTIVE_APP_ICON_PATH.exists()
                    else (str(APP_ICON_PATH.resolve()) if APP_ICON_PATH.exists() else ""),
                    duration="short",
                ).show()
                return
            except Exception as exc:
                append_runtime_log(f"Windows toast notification failed: {exc}")

        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.Information,
                4000,
            )

    def _notify_campus_connection_change(
        self,
        campus_connected: bool,
        campus_authenticated: bool,
        connection_text: str,
    ) -> None:
        if self._suppress_next_status_change_notification:
            self._last_campus_connected_state = campus_connected
            self._last_campus_authenticated_state = campus_authenticated
            self._suppress_next_status_change_notification = False
            return

        previous_state = self._last_campus_connected_state
        self._last_campus_connected_state = campus_connected
        previous_auth_state = self._last_campus_authenticated_state
        self._last_campus_authenticated_state = campus_authenticated

        if previous_state is not None and previous_state != campus_connected:
            if campus_connected:
                self._show_windows_notification(
                    "校园网已连接",
                    f"当前网络：{connection_text}",
                )
            else:
                self._show_windows_notification(
                    "校园网已断开",
                    f"当前网络：{connection_text}",
                )
            return

        if (
            campus_connected
            and previous_auth_state is not None
            and previous_auth_state != campus_authenticated
        ):
            if campus_authenticated:
                self._show_windows_notification(
                    "校园网登录已恢复",
                    f"当前网络：{connection_text}",
                )
                return
            self._show_windows_notification(
                "校园网登录已断开",
                f"仍连接 {connection_text}，但登录状态已失效。",
            )

    def _apply_environment_status(self, status: dict) -> None:
        info = status.get("network", {})
        target_ssids = list(ALLOWED_CAMPUS_SSIDS)
        campus_connected = bool(status.get("campus_connected"))
        campus_authenticated = bool(status.get("campus_authenticated"))
        network_type = info.get("network_type", "")
        current_ssid = info.get("ssid", "")

        self._set_network_icon(network_type)

        if campus_connected:
            if network_type == "wifi" and current_ssid:
                connection_text = current_ssid
            elif network_type == "ethernet":
                connection_text = "CUMT_Stu"
            else:
                connection_text = "校园网"
            self._set_status_badge(self.connection_badge, connection_text, "#159570")
        else:
            if network_type == "wifi" and current_ssid:
                connection_text = current_ssid
            elif network_type == "ethernet":
                connection_text = "有线网络"
            else:
                connection_text = "无网络"
            self._set_status_badge(self.connection_badge, connection_text, "#8b2331")

        self._notify_campus_connection_change(
            campus_connected,
            campus_authenticated,
            connection_text,
        )

        if campus_authenticated:
            self._set_status_badge(self.auth_badge, "已登录", "#2563eb")
        else:
            self._set_status_badge(self.auth_badge, "未登录", "#b7791f")
        self._set_tray_auth_status(campus_authenticated)

        if campus_connected:
            if network_type == "wifi":
                ssid = current_ssid or "未知 SSID"
                if campus_authenticated:
                    self.env_summary_label.setText(f"已连接校园网 Wi-Fi {ssid}，并且已经登录。")
                else:
                    self.env_summary_label.setText(f"已连接校园网 Wi-Fi {ssid}，但当前尚未登录。")
            elif network_type == "ethernet":
                if campus_authenticated:
                    self.env_summary_label.setText("已连接校园网有线网络，并且已经登录。")
                else:
                    self.env_summary_label.setText("已连接校园网有线网络，但当前尚未登录。")
            else:
                self.env_summary_label.setText("已检测到校园网环境。")
        else:
            if network_type == "wifi" and current_ssid:
                self.env_summary_label.setText(
                    f"当前连接的是 {current_ssid}。"
                )
            elif network_type == "ethernet":
                self.env_summary_label.setText("已检测到有线网络，但尚未确认它属于校园网。")
            else:
                self.env_summary_label.setText("当前没有检测到可用于校园网登录的活动会话。")

        self.env_details.setText(
            f"Type: {network_type or '-'}\n"
            f"SSID: {info.get('ssid', '') or '-'}\n"
            f"IP: {info.get('wlan_user_ip', '') or '-'}\n"
            f"MAC: {info.get('wlan_user_mac', '') or '-'}\n"
            f"Interface: {info.get('interface_name', '') or '-'}\n"
            f"Portal URL: {status.get('portal_url', '') or '-'}"
        )
        latency_tests = status.get("latency_tests") or []
        if "latency_tests" in status:
            self._update_latency_result_widgets(latency_tests)

    def _handle_environment_status(self, status: dict) -> None:
        network = status.get("network", {})
        append_runtime_log(
            "Environment status result: "
            f"connected={bool(status.get('campus_connected'))}, "
            f"authenticated={bool(status.get('campus_authenticated'))}, "
            f"type={network.get('network_type', '') or '-'}, "
            f"ssid={network.get('ssid', '') or '-'}, "
            f"ip={network.get('wlan_user_ip', '') or '-'}, "
            f"portal_reachable={bool(status.get('portal_reachable'))}, "
            f"error={status.get('error', '') or '-'}"
        )
        self._apply_environment_status(status)
        if self.startup_status_timer is not None:
            append_runtime_log(
                "Startup status result: "
                f"connected={bool(status.get('campus_connected'))}, "
                f"authenticated={bool(status.get('campus_authenticated'))}, "
                f"type={network.get('network_type', '') or '-'}, "
                f"ssid={network.get('ssid', '') or '-'}, "
                f"ip={network.get('wlan_user_ip', '') or '-'}, "
                f"portal_reachable={bool(status.get('portal_reachable'))}, "
                f"error={status.get('error', '') or '-'}"
            )
        if self.startup_status_timer is not None and status.get("campus_authenticated"):
            self._stop_startup_status_monitor(
                final_text="已登录校园网，启动检测已停止。",
            )
            return
        self._maybe_auto_connect(status)

    def _handle_status_thread_finished(
        self,
        thread: QThread | None = None,
    ) -> None:
        elapsed = time.monotonic() - self._status_thread_started_at if self._status_thread_started_at else 0.0
        append_runtime_log(f"Environment status thread finished: elapsed={elapsed:.2f}s")
        if thread is None or self.status_thread is thread:
            self.status_thread = None
            self.status_worker = None
        self._stop_refresh_animation()
        self.status_refresh_button.setEnabled(True)
        if self._manual_status_refresh_pending:
            self._manual_status_refresh_pending = False
            self.last_result_label.setText("状态已更新。")

    def _start_refresh_animation(self, visual_feedback: bool = False) -> None:
        if visual_feedback:
            self._start_refresh_spin()
        self.status_refresh_button.setProperty("refreshing", visual_feedback)
        self.status_refresh_button.style().unpolish(self.status_refresh_button)
        self.status_refresh_button.style().polish(self.status_refresh_button)

    def _stop_refresh_animation(self) -> None:
        self.status_refresh_button.setProperty("refreshing", False)
        self.status_refresh_button.style().unpolish(self.status_refresh_button)
        self.status_refresh_button.style().polish(self.status_refresh_button)

    def _start_refresh_spin(self) -> None:
        if self.refresh_spin_timer is None:
            self.refresh_spin_timer = QTimer(self)
            self.refresh_spin_timer.timeout.connect(self._update_refresh_spin)
        if self.refresh_spin_timer.isActive():
            self.refresh_spin_steps_remaining = min(
                self.refresh_spin_steps_remaining + 12,
                36,
            )
            return

        self.refresh_spin_angle = 0
        self.refresh_spin_steps_remaining = 12
        self.refresh_spin_timer.start(25)
        self._update_refresh_spin()

    def _update_refresh_spin(self) -> None:
        if self.refresh_spin_steps_remaining <= 0:
            if self.refresh_spin_timer is not None:
                self.refresh_spin_timer.stop()
            self.status_refresh_button.setIcon(self.refresh_icon)
            return

        self.refresh_spin_angle = (self.refresh_spin_angle + 30) % 360
        size = self.status_refresh_button.iconSize()
        scale = 4
        render_size = QSize(size.width() * scale, size.height() * scale)
        rotated = QPixmap(render_size)
        rotated.fill(Qt.transparent)
        painter = QPainter(rotated)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.translate(render_size.width() / 2, render_size.height() / 2)
        painter.rotate(self.refresh_spin_angle)
        icon_rect = QRectF(-9 * scale, -9 * scale, 18 * scale, 18 * scale)
        self.refresh_renderer.render(painter, icon_rect)
        painter.end()
        self.status_refresh_button.setIcon(
            QIcon(rotated.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        )
        self.refresh_spin_steps_remaining -= 1

    def _summarize_connectivity_test(self, status: dict) -> str:
        if status.get("error"):
            return f"连通性测试失败：{status['error']}"

        latency_tests = status.get("latency_tests") or []
        if not latency_tests:
            return "连通性测试未返回结果。"

        parts = []
        for item in latency_tests:
            if item.get("ok"):
                parts.append(f"{item.get('name', '-')} {item.get('latency_ms', '-')} ms")
            else:
                parts.append(f"{item.get('name', '-')} 不可达")
        return "连通性测试结果：" + "，".join(parts)

    def _maybe_auto_connect(self, status: dict) -> None:
        log_startup_skip = self.startup_status_timer is not None
        if self._status_detection_paused_for_session:
            if log_startup_skip:
                append_runtime_log("Startup auto-login skipped: detection paused for this session")
            return
        if self._auto_connect_paused_for_session:
            if log_startup_skip:
                append_runtime_log("Startup auto-login skipped: auto-login paused for this session")
            return
        ui_config = self.config.get("ui", {})
        if not ui_config.get("auto_connect_enabled", False):
            if log_startup_skip:
                append_runtime_log("Startup auto-login skipped: auto-connect disabled")
            return
        if not status.get("campus_connected"):
            if log_startup_skip:
                append_runtime_log("Startup auto-login skipped: campus network not connected")
            return
        if status.get("campus_authenticated"):
            if log_startup_skip:
                append_runtime_log("Startup auto-login skipped: already authenticated")
            return
        if self._is_busy:
            if log_startup_skip:
                append_runtime_log("Startup auto-login skipped: login/logout busy")
            return
        if self.worker_thread and self.worker_thread.isRunning():
            if log_startup_skip:
                append_runtime_log("Startup auto-login skipped: login worker already running")
            return
        if self.connectivity_thread and self.connectivity_thread.isRunning():
            if log_startup_skip:
                append_runtime_log("Startup auto-login skipped: connectivity test running")
            return
        if not self.username_edit.text().strip() or not self.password_edit.text():
            if log_startup_skip:
                append_runtime_log("Startup auto-login skipped: username or password is empty")
            return

        now = time.monotonic()
        if log_startup_skip:
            if self._startup_auto_login_exhausted:
                append_runtime_log("Startup auto-login skipped: max attempts already reached")
                return
            if self._startup_auto_login_attempts >= STARTUP_AUTO_LOGIN_MAX_ATTEMPTS:
                self._startup_auto_login_exhausted = True
                append_runtime_log(
                    "Startup auto-login exhausted max attempts; continuing status detection only"
                )
                return
            if (
                self._startup_auto_login_attempts > 0
                and now - self._last_startup_auto_login_at < STARTUP_AUTO_LOGIN_RETRY_INTERVAL_SECONDS
            ):
                append_runtime_log("Startup auto-login skipped: retry interval not reached")
                return

        if not log_startup_skip:
            interval_seconds = int(
                ui_config.get(
                    "status_refresh_interval_seconds",
                    DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS,
                )
            )
            cooldown_seconds = max(20, interval_seconds * 2)
            if (
                self._last_auto_connect_at > 0
                and now - self._last_auto_connect_at < cooldown_seconds
            ):
                return

        if log_startup_skip:
            self._startup_auto_login_attempts += 1
            self._last_startup_auto_login_at = now
            append_runtime_log(
                "Startup auto-login attempt "
                f"{self._startup_auto_login_attempts}/{STARTUP_AUTO_LOGIN_MAX_ATTEMPTS}"
            )

        self._last_auto_connect_at = now
        self._append_log("检测到校园网未登录，开始自动登录。")
        append_runtime_log("Startup auto-login started" if log_startup_skip else "Background auto-login started")
        self.last_result_label.setText("检测到校园网未登录，正在自动登录。")
        self._start_login(manual=False)

    def _refresh_environment_status(
        self,
        force: bool = False,
        visual_feedback: bool = False,
        suppress_change_notification: bool = False,
    ) -> None:
        if self._is_busy and not force:
            append_runtime_log("Environment status refresh skipped: app is busy")
            return
        if self.status_thread and self.status_thread.isRunning():
            elapsed = time.monotonic() - self._status_thread_started_at if self._status_thread_started_at else 0.0
            if visual_feedback:
                self._start_refresh_spin()
                self._manual_status_refresh_pending = True
                self.last_result_label.setText("正在检测网络状态，请稍候。")
                self._set_tray_checking_status()
            append_runtime_log(f"Environment status refresh skipped: previous thread still running ({elapsed:.2f}s)")
            if elapsed <= 6:
                return
            append_runtime_log("Environment status thread appears stuck; clearing stale reference")
            self.status_thread = None
            self.status_worker = None
            self.status_refresh_button.setEnabled(True)

        if visual_feedback:
            self._manual_status_refresh_pending = True
            self.last_result_label.setText("正在检测网络状态。")

        self._set_tray_checking_status()

        target_ssids = list(ALLOWED_CAMPUS_SSIDS)
        self.config["portal"]["target_ssids"] = target_ssids
        self.config["portal"]["target_ssid"] = target_ssids[0]

        thread = QThread(self)
        worker = StatusWorker(self.config, timeout_seconds=2)
        self._status_thread_started_at = time.monotonic()
        append_runtime_log(
            "Environment status refresh started: "
            f"force={force}, visual={visual_feedback}, targets={','.join(target_ssids)}"
        )
        self.status_thread = thread
        self.status_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_environment_status)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        thread.finished.connect(
            lambda thread=thread: self._handle_status_thread_finished(thread)
        )
        thread.finished.connect(thread.deleteLater)
        self._start_refresh_animation(visual_feedback)
        if suppress_change_notification:
            self._suppress_next_status_change_notification = True
        thread.start()

    def _handle_connectivity_thread_finished(
        self,
        thread: QThread | None = None,
    ) -> None:
        if thread is None or self.connectivity_thread is thread:
            self.connectivity_thread = None
            self.connectivity_worker = None
        self.run_latency_button.setEnabled(not self._is_busy)
        self.run_latency_button.setText("开始测试")

    def _finish_connectivity_test(self, status: dict) -> None:
        self._apply_environment_status(status)

    def _start_connectivity_test(self) -> None:
        if self._is_busy:
            return
        if self.connectivity_thread and self.connectivity_thread.isRunning():
            return

        target_ssids = list(ALLOWED_CAMPUS_SSIDS)
        self.config["portal"]["target_ssids"] = target_ssids
        self.config["portal"]["target_ssid"] = target_ssids[0]

        self._show_tools_page("latency")
        self.run_latency_button.setEnabled(False)
        self.run_latency_button.setText("测试中...")

        thread = QThread(self)
        worker = ConnectivityWorker(self.config, timeout_seconds=3)
        self.connectivity_thread = thread
        self.connectivity_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._finish_connectivity_test)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        thread.finished.connect(
            lambda thread=thread: self._handle_connectivity_thread_finished(thread)
        )
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _handle_login_thread_finished(
        self,
        thread: QThread | None = None,
    ) -> None:
        if thread is None or self.worker_thread is thread:
            self.worker_thread = None
            self.worker = None

    def _handle_logout_thread_finished(
        self,
        thread: QThread | None = None,
    ) -> None:
        if thread is None or self.logout_thread is thread:
            self.logout_thread = None
            self.logout_worker = None

    def _apply_window_chrome(self) -> None:
        if sys.platform != "win32":
            return

        hwnd = int(self.winId())
        if not hwnd:
            return

        def colorref(hex_color: str) -> ctypes.c_int:
            value = hex_color.lstrip("#")
            red = int(value[0:2], 16)
            green = int(value[2:4], 16)
            blue = int(value[4:6], 16)
            return ctypes.c_int(red | (green << 8) | (blue << 16))

        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_BORDER_COLOR = 34
        DWMWA_CAPTION_COLOR = 35
        DWMWA_TEXT_COLOR = 36

        try:
            dwmapi = ctypes.windll.dwmapi
            false_value = ctypes.c_int(0)
            caption_color = colorref("f3f6fb")
            border_color = colorref("d9e3f0")
            text_color = colorref("152033")

            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(false_value),
                ctypes.sizeof(false_value),
            )
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_CAPTION_COLOR,
                ctypes.byref(caption_color),
                ctypes.sizeof(caption_color),
            )
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_BORDER_COLOR,
                ctypes.byref(border_color),
                ctypes.sizeof(border_color),
            )
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_TEXT_COLOR,
                ctypes.byref(text_color),
                ctypes.sizeof(text_color),
            )
        except Exception:
            pass

    def _validate_login_form(self) -> bool:
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if not username and not password:
            message = "请先输入账号和密码。"
        elif not username:
            message = "请先输入账号。"
        elif not password:
            message = "请先输入密码。"
        else:
            return True

        self.last_result_label.setText(message)
        self._append_log(message)
        return False

    def _is_login_form_complete(self) -> bool:
        return bool(self.username_edit.text().strip() and self.password_edit.text())

    def _update_form_action_buttons(self) -> None:
        if not hasattr(self, "save_button") or not hasattr(self, "login_button"):
            return
        enabled = self._is_login_form_complete() and not self._is_busy
        self.save_button.setEnabled(enabled)
        self.login_button.setEnabled(enabled)
        self._sync_tray_actions()

    def _save_config(self, validate: bool = True) -> bool:
        if validate and not self._validate_login_form():
            return False

        self.config["login"]["username"] = self.username_edit.text().strip()
        self.config["login"]["password"] = self.password_edit.text()
        self.config["login"]["account_suffix"] = self.operator_combo.currentData() or ""
        self.config["login"]["account_prefix"] = ""
        self.config["portal"]["target_ssids"] = list(ALLOWED_CAMPUS_SSIDS)
        self.config["portal"]["target_ssid"] = ALLOWED_CAMPUS_SSIDS[0]

        self._write_config()
        self._append_log("配置已保存。")
        self.last_result_label.setText("配置已保存。")
        return True

    def _write_config(self) -> None:
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def _set_busy_state(self, busy: bool) -> None:
        self._is_busy = busy
        form_complete = self._is_login_form_complete()
        self.login_button.setEnabled((not busy) and form_complete)
        self.logout_button.setEnabled(not busy)
        self.save_button.setEnabled((not busy) and form_complete)
        self.run_latency_button.setEnabled(
            (not busy)
            and not (self.connectivity_thread and self.connectivity_thread.isRunning())
        )
        self.operator_combo.setEnabled(not busy)
        self.username_edit.setEnabled(not busy)
        self.password_edit.setEnabled(not busy)
        self.login_button.setText("登录中..." if busy else "立即登录")
        self._sync_tray_actions()

    def _set_logout_busy_state(self, busy: bool) -> None:
        self._is_busy = busy
        form_complete = self._is_login_form_complete()
        self.login_button.setEnabled((not busy) and form_complete)
        self.logout_button.setEnabled(not busy)
        self.save_button.setEnabled((not busy) and form_complete)
        self.run_latency_button.setEnabled(
            (not busy)
            and not (self.connectivity_thread and self.connectivity_thread.isRunning())
        )
        self.operator_combo.setEnabled(not busy)
        self.username_edit.setEnabled(not busy)
        self.password_edit.setEnabled(not busy)
        self.logout_button.setText("注销中..." if busy else "注销")
        self._sync_tray_actions()

    def _ensure_campus_network_for_login(self) -> bool:
        try:
            status = portal_core.get_campus_status(self.config, timeout_seconds=2)
        except Exception:
            status = {"campus_connected": False}

        network = status.get("network", {})
        if network.get("network_type") == "wifi" and network.get("ssid") == "CUMT_Tec":
            self._append_log("当前连接的是 CUMT_Tec 教职工网络，学生账号无法登录教师端。")
            self.last_result_label.setText("当前为 CUMT_Tec 教职工网络，学生账号请切换到 CUMT_Stu。")
            return False

        if status.get("campus_connected"):
            return True

        self._append_log("当前不在校园网环境，已取消登录。")
        self.last_result_label.setText("请先连接校园网后再登录。")
        return False

    def _start_login(self, manual: bool = True) -> None:
        if self.connectivity_thread and self.connectivity_thread.isRunning():
            self.last_result_label.setText("请等待连通性测试完成后再执行登录。")
            return
        if not self._save_config(validate=True):
            return
        if not self._ensure_campus_network_for_login():
            return
        self._current_login_is_manual = manual
        self._set_busy_state(True)
        self._append_log("开始登录。")
        self.last_result_label.setText("正在尝试登录校园网。")

        run_config = copy.deepcopy(self.config)

        thread = QThread(self)
        worker = LoginWorker(run_config)
        self.worker_thread = thread
        self.worker = worker
        self._set_tray_logging_in_status()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.finished.connect(self._finish_login)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        thread.finished.connect(
            lambda thread=thread: self._handle_login_thread_finished(thread)
        )
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _start_logout(self) -> None:
        if self.connectivity_thread and self.connectivity_thread.isRunning():
            self.last_result_label.setText("请等待连通性测试完成后再执行注销。")
            return
        if self.logout_thread and self.logout_thread.isRunning():
            return

        self._set_logout_busy_state(True)
        self._append_log("开始注销。")
        self.last_result_label.setText("正在注销校园网登录。")

        run_config = copy.deepcopy(self.config)
        thread = QThread(self)
        worker = LogoutWorker(run_config)
        self.logout_thread = thread
        self.logout_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.finished.connect(self._finish_logout)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        thread.finished.connect(
            lambda thread=thread: self._handle_logout_thread_finished(thread)
        )
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _finish_logout(self, result: dict) -> None:
        self._set_logout_busy_state(False)
        ok = bool(result.get("ok"))
        message = str(result.get("message", "") or "").strip()
        if self._looks_unreadable_message(message):
            message = "已注销校园网登录。" if ok else "注销失败，未能确认已下线。"
        self._append_log(message)
        self._pause_auto_detection_and_login_for_session(
            "用户主动注销，已停止本次运行内的自动检测和自动登录。"
        )
        if not ok:
            self.last_result_label.setText(message)
            self._show_windows_notification("校园网注销失败", message)
            self._refresh_environment_status(force=True, suppress_change_notification=True)
            return

        logout_notice = "已注销，在手动登录前不再执行自动登录。"
        self.last_result_label.setText(logout_notice)
        self._last_campus_authenticated_state = False
        self._set_tray_auth_status(False)
        self._show_windows_notification(
            "校园网已注销",
            "在手动登录前不再执行自动登录。",
        )

    def _finish_login(self, result: dict) -> None:
        self._set_busy_state(False)
        ok = bool(result.get("ok"))
        if ok and self._current_login_is_manual:
            self._status_detection_paused_for_session = False
            self._set_auto_connect_paused_for_session(False)
            self._apply_status_monitor_settings()
        self._current_login_is_manual = False
        message = self._login_message_for_result(
            result,
            "请检查账号、密码、运营商或当前网络状态。",
        )
        self._append_log(message)
        self.last_result_label.setText(message or ("登录成功" if ok else "登录失败"))
        self._last_campus_authenticated_state = ok
        self._set_tray_auth_status(ok)
        if ok:
            if self.startup_status_timer is not None:
                self._stop_startup_status_monitor(
                    final_text="已登录校园网，启动检测已停止。",
                )
            self._refresh_environment_status(force=True, suppress_change_notification=True)
            success_notice = message or "当前设备已通过校园网认证。"
            if success_notice in {"登录成功", "校园网已登录。"}:
                success_notice = "当前设备已通过校园网认证。"
            self._show_windows_notification("校园网登录成功", success_notice)
        elif self._handle_non_retriable_login_failure(result):
            return
        else:
            self._refresh_environment_status(force=True, suppress_change_notification=True)
            self._show_windows_notification(
                "校园网登录失败",
                message or "请检查账号、密码、运营商或当前网络状态。",
            )

    def _append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def _create_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        self.tray_icon.setToolTip("CUMT 校园网登录器")

        tray_menu_family = pick_font_family(
            self.loaded_font_families,
            "MiSans VF Light",
            "MiSans VF",
            fallback=self.font_family,
        )

        menu = QMenu(self)
        menu.setFont(self._make_font(tray_menu_family, 14, QFont.Weight.Light))
        menu.setStyleSheet(
            """
            QMenu {
                background: #ffffff;
                color: #152033;
                border: 1px solid #cfd8e6;
                border-radius: __RADIUS__px;
                padding: 6px;
                font-family: __TRAY_FONT_FAMILY__;
                font-size: 14px;
                font-weight: 300;
            }
            QMenu::item {
                min-width: 148px;
                padding: 6px 16px 6px 14px;
                border-radius: __RADIUS__px;
            }
            QMenu::item:selected {
                background: #2563eb;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: #d9e3f0;
                margin: 4px 6px;
            }
            """
            .replace("__RADIUS__", str(UI_RADIUS))
            .replace("__TRAY_FONT_FAMILY__", quote_font_family(tray_menu_family))
        )

        tray_status_widget = QWidget()
        tray_status_widget.setObjectName("trayStatusWidget")
        tray_status_layout = QHBoxLayout(tray_status_widget)
        tray_status_layout.setContentsMargins(14, 6, 16, 6)
        tray_status_layout.setSpacing(7)

        self.tray_status_dot = QLabel()
        self.tray_status_dot.setFixedSize(10, 10)
        tray_status_layout.addWidget(self.tray_status_dot, 0, Qt.AlignVCenter)

        self.tray_status_label = QLabel()
        self.tray_status_label.setObjectName("trayStatusLabel")
        self.tray_status_label.setFont(
            self._make_font(tray_menu_family, 14, QFont.Weight.Light)
        )
        self.tray_status_label.setStyleSheet(
            f"color: #152033; background: transparent; "
            f"font-family: {quote_font_family(tray_menu_family)}; "
            f"font-size: 14px; font-weight: 300;"
        )
        tray_status_layout.addWidget(self.tray_status_label, 1, Qt.AlignVCenter)
        tray_status_widget.setStyleSheet("QWidget#trayStatusWidget { background: transparent; }")
        status_action = QWidgetAction(self)
        status_action.setDefaultWidget(tray_status_widget)
        menu.addAction(status_action)
        menu.addSeparator()

        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        self.tray_refresh_action = QAction("刷新状态", self)
        self.tray_refresh_action.triggered.connect(
            lambda: self._refresh_environment_status(force=True, visual_feedback=True)
        )
        menu.addAction(self.tray_refresh_action)

        self.tray_login_action = QAction("一键登录", self)
        self.tray_login_action.triggered.connect(lambda: self._start_login(manual=True))
        menu.addAction(self.tray_login_action)

        self.tray_logout_action = QAction("注销", self)
        self.tray_logout_action.triggered.connect(self._start_logout)
        menu.addAction(self.tray_logout_action)

        portal_action = QAction("打开登录页", self)
        portal_action.triggered.connect(self._open_portal_page)
        menu.addAction(portal_action)

        menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_application)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._handle_tray_activation)
        self.tray_icon.show()
        self._sync_tray_actions()

    def _show_window(self) -> None:
        self.showNormal()
        self._ensure_window_visible()
        self.raise_()
        self.activateWindow()

    def _handle_tray_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_window()

    def _quit_application(self) -> None:
        self._request_app_exit()

    def _stop_background_thread(
        self,
        thread: QThread | None,
        name: str,
        timeout_ms: int = 5000,
    ) -> bool:
        if thread is None or not thread.isRunning():
            return True

        thread.quit()
        if thread.isRunning():
            if name not in self._exit_waiting_threads_logged:
                self._exit_waiting_threads_logged.add(name)
                append_runtime_log(f"{name} thread is still running; delaying application exit")
            return False
        return True

    def _request_app_exit(self) -> None:
        self._allow_close = True
        if self.startup_status_timer is not None:
            self.startup_status_timer.stop()
            self.startup_status_timer = None
        if self.status_timer is not None:
            self.status_timer.stop()

        stopped = all(
            (
                self._stop_background_thread(self.status_thread, "status", 4000),
                self._stop_background_thread(self.connectivity_thread, "connectivity", 8000),
                self._stop_background_thread(self.worker_thread, "login", 8000),
                self._stop_background_thread(self.logout_thread, "logout", 8000),
            )
        )
        if not stopped:
            QTimer.singleShot(1000, self._request_app_exit)
            return

        if self.tray_icon:
            self.tray_icon.hide()
        self.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _get_close_behavior(self) -> str:
        return self.config.get("ui", {}).get("close_behavior", "ask")

    def _set_close_behavior(self, behavior: str) -> None:
        self.config.setdefault("ui", {})["close_behavior"] = behavior
        self._write_config()

    def _minimize_to_tray(self) -> None:
        self.hide()
        ui_config = self.config.setdefault("ui", {})
        if ui_config.get("tray_minimize_notice_shown", False):
            return

        self._show_windows_notification(
            "CUMT 校园网登录器",
            "应用已最小化到系统托盘，右击托盘图标可重新打开或退出。",
        )
        ui_config["tray_minimize_notice_shown"] = True
        try:
            self._write_config()
        except OSError as exc:
            append_runtime_log(f"Failed to save tray notice state: {exc}")

    def _prompt_close_behavior(self) -> str | None:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Question)
        dialog.setWindowTitle("关闭应用")
        dialog.setText("第一次关闭窗口时，需要确定默认行为。")
        dialog.setInformativeText(
            "选择“最小化到托盘”后，应用会继续在后台运行；"
            "选择“直接退出”后，应用会完全关闭。此次选择会保存为默认设置。"
        )
        tray_button = dialog.addButton("最小化到托盘", QMessageBox.AcceptRole)
        exit_button = dialog.addButton("直接退出", QMessageBox.DestructiveRole)
        dialog.addButton(QMessageBox.Cancel)
        dialog.exec()

        clicked = dialog.clickedButton()
        if clicked is tray_button:
            return "tray"
        if clicked is exit_button:
            return "exit"
        return None

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close or not self.tray_icon:
            event.accept()
            return

        behavior = self._get_close_behavior()
        if behavior == "tray":
            event.ignore()
            self._minimize_to_tray()
            return

        if behavior == "exit":
            event.ignore()
            self._request_app_exit()
            return

        choice = self._prompt_close_behavior()
        if choice == "tray":
            self._set_close_behavior("tray")
            event.ignore()
            self._minimize_to_tray()
            return

        if choice == "exit":
            self._set_close_behavior("exit")
            event.ignore()
            self._request_app_exit()
            return

        event.ignore()


def main() -> int:
    single_instance_lock = acquire_single_instance_lock()
    if sys.platform == "win32" and single_instance_lock is None:
        notify_existing_instance()
        return 0

    try:
        install_exception_logging()
        set_windows_app_user_model_id()
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        start_hidden = "--start-hidden" in sys.argv[1:]
        from_startup = "--from-startup" in sys.argv[1:]
        loaded_families = load_bundled_font_families()
        font_family = pick_font_family(
            loaded_families,
            "MiSans VF",
            "MiSans",
            fallback=DEFAULT_APP_FONT_FAMILY,
        )
        app_font = QFont(font_family)
        app_font.setPixelSize(int(TYPOGRAPHY["app"]["size"]))
        app_font.setWeight(QFont.Weight(int(TYPOGRAPHY["app"]["weight"])))
        app.setFont(app_font)
        window = CampusLoginWindow(start_hidden=start_hidden, from_startup=from_startup)
        if start_hidden:
            window.start_hidden_startup_tasks()
        else:
            window.show()
        return app.exec()
    finally:
        if sys.platform == "win32" and single_instance_lock:
            ctypes.windll.kernel32.CloseHandle(single_instance_lock)


if __name__ == "__main__":
    raise SystemExit(main())
