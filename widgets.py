from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from constants import INPUT_HEIGHT, TRAILING_ICON_AREA_WIDTH, TRAILING_ICON_SIZE, UI_RADIUS
from paths import ICON_DIR


class GlassBackdrop(QFrame):
    """Paint one continuous translucent backdrop behind the whole window."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._backdrop = QPixmap()
        self._backdrop_key: tuple[int, int] | None = None

    def resizeEvent(self, event) -> None:
        self._backdrop_key = None
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self._ensure_backdrop()
        if not self._backdrop.isNull():
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self._backdrop)

    def _ensure_backdrop(self) -> None:
        width = self.width()
        height = self.height()
        key = (width, height)
        if width <= 0 or height <= 0 or key == self._backdrop_key:
            return

        # The backdrop contains only soft gradients. Keeping it in logical pixels
        # prevents costly cache rebuilds while a window crosses mixed-DPI screens.
        backdrop = QPixmap(width, height)
        backdrop.fill(Qt.transparent)

        painter = QPainter(backdrop)
        painter.setRenderHint(QPainter.Antialiasing, True)

        base = QLinearGradient(0, 0, width, height)
        base.setColorAt(0.0, QColor(219, 230, 245, 64))
        base.setColorAt(0.42, QColor(242, 246, 251, 54))
        base.setColorAt(1.0, QColor(223, 232, 243, 62))
        painter.fillRect(QRectF(0, 0, width, height), base)

        brand_glow = QRadialGradient(
            QPointF(width * 0.08, height * 0.02),
            max(width, height) * 0.72,
        )
        brand_glow.setColorAt(0.0, QColor(18, 46, 138, 30))
        brand_glow.setColorAt(0.48, QColor(70, 111, 190, 12))
        brand_glow.setColorAt(1.0, QColor(70, 111, 190, 0))
        painter.fillRect(QRectF(0, 0, width, height), brand_glow)

        ice_glow = QRadialGradient(
            QPointF(width * 1.02, height * 0.34),
            max(width, height) * 0.58,
        )
        ice_glow.setColorAt(0.0, QColor(87, 194, 196, 20))
        ice_glow.setColorAt(0.55, QColor(125, 205, 209, 8))
        ice_glow.setColorAt(1.0, QColor(125, 205, 209, 0))
        painter.fillRect(QRectF(0, 0, width, height), ice_glow)

        top_light = QLinearGradient(0, 0, 0, min(210, height))
        top_light.setColorAt(0.0, QColor(255, 255, 255, 26))
        top_light.setColorAt(0.46, QColor(255, 255, 255, 9))
        top_light.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(0, 0, width, min(210, height)), top_light)

        painter.end()
        self._backdrop = backdrop
        self._backdrop_key = key


class TitleBar(QFrame):
    def __init__(self, window: "CampusLoginWindow") -> None:
        super().__init__(window)
        self._window = window
        self.setObjectName("titleBar")
        self.setFixedHeight(62)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 10, 10)
        layout.setSpacing(10)

        self.title_brand = QLabel("CUMT")
        self.title_brand.setObjectName("titleBrand")
        brand_font = self._window._make_title_font(26)
        brand_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 112)
        self.title_brand.setFont(brand_font)
        layout.addWidget(self.title_brand, 0, Qt.AlignBottom)

        self.title_label = QLabel("校园网登录器")
        self.title_label.setObjectName("titleText")
        self.title_label.setFont(self._window._make_title_font(25))
        layout.addWidget(self.title_label, 0, Qt.AlignBottom)
        layout.addStretch()

        self.settings_button = self._make_button("\ue713", self._window._toggle_settings_panel, role="settings")
        self.settings_button.setCheckable(True)
        self.settings_button.setToolTip("显示设置")
        self.min_button = self._make_button("\ue921", self._window.showMinimized, role="min")
        self.close_button = self._make_button("\ue8bb", self._window.close, close=True)

        layout.addWidget(self.settings_button, 0, Qt.AlignTop)
        layout.addWidget(self.min_button, 0, Qt.AlignTop)
        layout.addWidget(self.close_button, 0, Qt.AlignTop)

    def _make_button(self, text: str, slot, close: bool = False, role: str = "button") -> QPushButton:
        button = QPushButton(text)
        object_names = {
            "settings": "titleSettingsButton",
            "min": "titleMinButton",
            "button": "titleButton",
        }
        button.setObjectName("titleCloseButton" if close else object_names.get(role, "titleButton"))
        button.clicked.connect(slot)
        button.setCursor(Qt.PointingHandCursor)
        return button

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            target = self.childAt(event.position().toPoint())
            if isinstance(target, QPushButton):
                super().mousePressEvent(event)
                return

            handle = self._window.windowHandle()
            if handle is not None and not self._window.isMaximized():
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)


class ResizeGrip(QWidget):
    def __init__(self, window: "CampusLoginWindow", edges, cursor_shape) -> None:
        super().__init__(window)
        self._window = window
        self._edges = edges
        self.setCursor(cursor_shape)
        self.setMouseTracking(True)
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton or self._window.isMaximized():
            super().mousePressEvent(event)
            return

        handle = self._window.windowHandle()
        if handle is not None:
            handle.startSystemResize(self._edges)
            event.accept()
            return
        super().mousePressEvent(event)


class FlatComboBox(QComboBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._arrow_icon = QIcon(str((ICON_DIR / "chevron-down.svg").resolve()))
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(INPUT_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"""
            QComboBox {{
                background: transparent;
                color: #152033;
                border: none;
                padding: 8px {TRAILING_ICON_AREA_WIDTH}px 8px 12px;
            }}
            QComboBox:disabled {{
                background: transparent;
                color: #a7b4c6;
                border: none;
            }}
            QComboBox:focus {{
                border: none;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: {TRAILING_ICON_AREA_WIDTH}px;
                border-left: 1px solid #d9e3f0;
                background: transparent;
                border-top-right-radius: {UI_RADIUS}px;
                border-bottom-right-radius: {UI_RADIUS}px;
            }}
            QComboBox:disabled::drop-down {{
                background: #f6f8fc;
                border-left: 1px solid #e4e9f1;
            }}
            QComboBox QAbstractItemView {{
                background: #ffffff;
                color: #152033;
                border: 1px solid #cfd8e6;
                border-radius: {UI_RADIUS}px;
                outline: none;
                padding: 4px;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }}
            """
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        enabled = self.isEnabled()
        background = QColor("#fbfdff" if enabled else "#f6f8fc")
        border = QColor("#cfd8e6" if enabled else "#dde4ef")

        painter.setPen(QPen(border, 1))
        painter.setBrush(background)
        painter.drawRoundedRect(rect, UI_RADIUS, UI_RADIUS)

        text_rect = self.rect().adjusted(12, 0, -(TRAILING_ICON_AREA_WIDTH + 8), 0)
        text = self.fontMetrics().elidedText(self.currentText(), Qt.ElideRight, text_rect.width())
        painter.setPen(QColor("#152033" if enabled else "#a7b4c6"))
        painter.setFont(self.font())
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, text)

        icon_left = self.width() - TRAILING_ICON_AREA_WIDTH + (
            TRAILING_ICON_AREA_WIDTH - TRAILING_ICON_SIZE
        ) // 2
        icon_top = int(rect.center().y() - TRAILING_ICON_SIZE / 2)
        icon_rect = QRect(icon_left, icon_top, TRAILING_ICON_SIZE, TRAILING_ICON_SIZE)
        painter.save()
        if not enabled:
            painter.setOpacity(0.45)
        self._arrow_icon.paint(painter, icon_rect, Qt.AlignCenter)
        painter.restore()

    def wheelEvent(self, event) -> None:
        event.ignore()


class PasswordLineEdit(QLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._password_visible = False
        self.setEchoMode(QLineEdit.Password)

        self._toggle_button = QToolButton(self)
        self._toggle_button.setCursor(Qt.PointingHandCursor)
        self._toggle_button.setFocusPolicy(Qt.NoFocus)
        self._toggle_button.setAutoRaise(True)
        self._toggle_button.setIcon(QIcon(str((ICON_DIR / "eye-off.svg").resolve())))
        self._toggle_button.setIconSize(QSize(TRAILING_ICON_SIZE, TRAILING_ICON_SIZE))
        self._toggle_button.setToolTip("显示密码")
        self._toggle_button.setStyleSheet(
            "QToolButton { border: none; background: transparent; padding: 0; }"
            "QToolButton:hover { background: transparent; }"
        )
        self._toggle_button.clicked.connect(self.toggle_password_visibility)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_toggle_button()

    def _position_toggle_button(self) -> None:
        self._toggle_button.setGeometry(
            self.width() - TRAILING_ICON_AREA_WIDTH,
            0,
            TRAILING_ICON_AREA_WIDTH,
            self.height(),
        )

    def toggle_password_visibility(self) -> None:
        self._password_visible = not self._password_visible
        self.setEchoMode(QLineEdit.Normal if self._password_visible else QLineEdit.Password)
        icon_name = "eye.svg" if self._password_visible else "eye-off.svg"
        self._toggle_button.setIcon(QIcon(str((ICON_DIR / icon_name).resolve())))
        self._toggle_button.setToolTip("隐藏密码" if self._password_visible else "显示密码")


class ClickableStatusBadge(QLabel):
    clicked = Signal()

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class ClickableFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)
