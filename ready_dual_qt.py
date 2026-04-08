import sys
import os
import json
import threading
import webbrowser
import ctypes
import re
from datetime import datetime
from PIL import Image, ImageDraw

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QPushButton, QTextEdit, QLineEdit, 
    QFrame, QScrollArea, QGraphicsDropShadowEffect, QComboBox,
    QSizePolicy, QPlainTextEdit, QSplitter, QDockWidget, QMenuBar, QMenu,
    QTabWidget, QInputDialog, QDialog, QCheckBox, QSpinBox, QMessageBox,
    QFileDialog
)
from PySide6.QtCore import Qt, QSize, Signal, QObject, Slot, QThread, QTimer, QByteArray
from PySide6.QtGui import QFont, QColor, QIcon, QPixmap, QImage, QPainter, QPen, QPainterPath, QTextCharFormat, QBrush, QSyntaxHighlighter

# Add core engine to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

from core.engine import Engine
from core.sigil_parser import parse_sigils

APP_NAME = "Ready Agentic AI"
APP_SUBTITLE = "MULTI MODAL AGENTIC AI"
APP_WINDOW_TITLE = f"{APP_NAME} - Multi Modal Agentic AI"
LAYOUT_STATE_VERSION = 1

# --- CORE BRIDGE ---
class AIBridge(QObject):
    chat_signal = Signal(str, str, str) # sender, text, color
    log_signal = Signal(str)           # tool log
    status_signal = Signal(str, str)    # target, text
    canvas_signal = Signal(str, str, str) # title, content, path
    approval_signal = Signal(object)    # approval request payload

# --- STYLING (QSS) ---
QSS_THEME = """
QMainWindow { background-color: #050505; }
QWidget { background-color: transparent; color: #d1d5db; font-family: 'Inter', 'Segoe UI', 'Consolas', sans-serif; }

#Sidebar { background-color: #050505; border-right: 1px solid #1a1a1a; min-width: 240px; }
#SidebarTitle { color: #facc15; font-size: 20px; font-weight: bold; margin-top: 10px; }
#SidebarSubtitle { color: #4b5563; font-size: 10px; font-weight: bold; margin-bottom: 20px; }

#Pane {
    background-color: #0a0a0a;
    border: 1px solid #1a1a1a;
}

#PaneHeader {
    background-color: #0d0d0d;
    border-bottom: 2px solid #1a1a1a;
    min-height: 54px;
    max-height: 54px;
}

#PaneHeaderText { font-weight: bold; font-size: 13px; }
#PaneHeaderMeta { color: #64748b; font-size: 11px; font-style: italic; }

/* Emerald Theme for Console */
#PaneConsole { border-top: 2px solid #10b981; }
#PaneConsoleText { color: #10b981; }

/* Cyan Theme for Canvas */
#PaneCanvas { border-top: 2px solid #22d3ee; }
#PaneCanvasText { color: #22d3ee; }

QPushButton {
    background-color: transparent;
    border: 1px solid #1a1a1a;
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: bold;
    text-align: left;
}

QPushButton:hover { background-color: #111111; }
#NewSessionBtn { border-color: #facc15; color: #facc15; font-size: 12px; padding: 12px; text-align: center; }
#ControlBtn { 
    border: 1px solid #1a1a1a; 
    border-radius: 6px;
    min-width: 44px;
    min-height: 36px;
    font-size: 16px;
    text-align: center;
}

#HistoryBtn { font-size: 11px; color: #a3a3a3; border: none; padding: 6px 10px; text-align: left; background: transparent; }
#HistoryBtnActive { border: 1px solid #facc15; color: #facc15; background: #0a0a0a; border-radius: 4px; }
#IconBtn { border: none; background: transparent; padding: 0px; }
#IconBtn:hover { background: #111111; }
#DeleteBtn { border: none; background: transparent; padding: 0px; }
#DeleteBtn:hover { background: #111111; }

QPlainTextEdit { background-color: #000000; border: none; font-family: 'Consolas'; font-size: 11px; padding: 15px; }
QLineEdit { background-color: #0f0f0f; border: 1px solid #1a1a1a; border-radius: 6px; padding: 10px; color: #ffffff; }

QScrollArea { border: none; }
QScrollBar:vertical { background: #050505; width: 8px; margin: 0px; }
QScrollBar::handle:vertical { background: #1a1a1a; min-height: 20px; }

#StatusBar { 
    background-color: #000000; 
    border-top: 1px solid #1a1a1a; 
    min-height: 32px; 
    max-height: 32px; 
}
#StatusBar QLabel {
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 10px;
    font-weight: bold;
    text-transform: uppercase;
    padding: 0 5px;
}

QMenuBar {
    background-color: #050505;
    border-bottom: 1px solid #1a1a1a;
    padding: 4px;
}
QMenuBar::item { padding: 4px 10px; color: #a3a3a3; }
QMenuBar::item:selected { background: #111111; color: #facc15; }

QMenu {
    background-color: #0a0a0a;
    border: 1px solid #1a1a1a;
    color: #d1d5db;
    padding: 4px;
}
QMenu::item {
    background-color: transparent;
    padding: 6px 26px 6px 12px;
}
QMenu::item:selected {
    background-color: #111111;
    color: #facc15;
}
QMenu::item:disabled {
    color: #4b5563;
}
QMenu::separator {
    height: 1px;
    background: #1a1a1a;
    margin: 4px 6px;
}

QSplitter::handle {
    background-color: #1a1a1a;
    width: 2px;
}

/* Dock Styling */
QDockWidget {
    color: #facc15;
    font-weight: bold;
    font-size: 10px;
}

QDockWidget::title {
    background-color: #0d0d0d;
    text-align: left;
    padding: 6px 15px;
    border-bottom: 2px solid #1a1a1a;
}

QTabBar::tab {
    background: #050505;
    border: 1px solid #1a1a1a;
    color: #64748b;
    padding: 8px 20px;
    font-size: 10px;
    font-weight: bold;
    text-transform: uppercase;
}

QTabBar::tab:selected {
    background: #0a0a0a;
    color: #facc15;
    border-bottom: 2px solid #facc15;
}

QMainWindow::separator {
    background-color: #1a1a1a;
    width: 2px;
    height: 2px;
}

QMainWindow::separator:hover {
    background-color: #facc15;
}
"""

def apply_glow(widget, color_hex="#facc15"):
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(20)
    shadow.setXOffset(0); shadow.setYOffset(0)
    shadow.setColor(QColor(color_hex))
    widget.setGraphicsEffect(shadow)

class MessageWidget(QFrame):
    def __init__(self, sender, text, color="#facc15"):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 10, 15, 15)
        self.layout.setSpacing(5)
        
        header = QLabel(sender.upper())
        header.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 10px;")
        self.layout.addWidget(header)
        
        body = QLabel(text)
        body.setWordWrap(True)
        body.setStyleSheet("color: #d1d5db; font-size: 12px;")
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.layout.addWidget(body)
        self.setStyleSheet("border-bottom: 1px solid #111111; margin-bottom: 10px;")

class ModelLoader(QThread):
    models_loaded = Signal(list)
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
    def run(self):
        models = self.engine._detect_models_list()
        self.models_loaded.emit(models)

def make_history_icon(kind, color_hex, size=18):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 18

    if kind == "trash":
        draw.rounded_rectangle([5*s, 7*s, 13*s, 15*s], radius=1*s, outline=color_hex, width=max(1, int(2*s)))
        draw.rectangle([4*s, 5*s, 14*s, 6.5*s], fill=color_hex)
        draw.rectangle([7*s, 3*s, 11*s, 4.5*s], fill=color_hex)
        for x in (7*s, 9*s, 11*s):
            draw.line([x, 8*s, x, 14*s], fill=color_hex, width=max(1, int(1*s)))
    else:
        draw.line([5*s, 13*s, 13*s, 5*s], fill=color_hex, width=max(2, int(3*s)))
        draw.polygon([(12*s, 4*s), (15*s, 3*s), (14*s, 6*s)], fill=color_hex)
        draw.polygon([(4*s, 14*s), (6*s, 13*s), (5*s, 15*s)], fill="#fef08a")

    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, size, size, QImage.Format_RGBA8888)
    return QIcon(QPixmap.fromImage(qimg))

def make_linkedin_icon(size=18):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 18
    draw.rounded_rectangle([1*s, 1*s, 17*s, 17*s], radius=3*s, fill="#0a66c2")
    draw.rectangle([4*s, 7*s, 6*s, 14*s], fill="#ffffff")
    draw.ellipse([3.7*s, 3.7*s, 6.3*s, 6.3*s], fill="#ffffff")
    draw.rectangle([8*s, 7*s, 10*s, 14*s], fill="#ffffff")
    draw.rounded_rectangle([10*s, 7*s, 14.5*s, 14*s], radius=1.4*s, outline="#ffffff", width=max(1, int(2*s)))
    draw.rectangle([10*s, 9*s, 11.4*s, 14*s], fill="#0a66c2")
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, size, size, QImage.Format_RGBA8888)
    return QIcon(QPixmap.fromImage(qimg))

def make_attachment_icon(size=20, color_hex="#facc15"):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor(color_hex))
    pen.setWidthF(max(2.0, size * 0.12))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)

    s = size / 24
    path = QPainterPath()
    path.moveTo(15.6 * s, 6.0 * s)
    path.cubicTo(18.5 * s, 8.9 * s, 18.5 * s, 13.4 * s, 15.6 * s, 16.3 * s)
    path.lineTo(11.1 * s, 20.8 * s)
    path.cubicTo(8.6 * s, 23.3 * s, 4.6 * s, 23.3 * s, 2.2 * s, 20.8 * s)
    path.cubicTo(-0.2 * s, 18.4 * s, -0.2 * s, 14.4 * s, 2.2 * s, 12.0 * s)
    path.lineTo(11.0 * s, 3.2 * s)
    path.cubicTo(13.0 * s, 1.2 * s, 16.2 * s, 1.2 * s, 18.2 * s, 3.2 * s)
    path.cubicTo(20.2 * s, 5.2 * s, 20.2 * s, 8.4 * s, 18.2 * s, 10.4 * s)
    path.lineTo(9.4 * s, 19.2 * s)
    path.cubicTo(8.3 * s, 20.3 * s, 6.5 * s, 20.3 * s, 5.4 * s, 19.2 * s)
    path.cubicTo(4.3 * s, 18.1 * s, 4.3 * s, 16.3 * s, 5.4 * s, 15.2 * s)
    path.lineTo(13.5 * s, 7.1 * s)
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)

class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, document, language):
        super().__init__(document)
        self.language = language
        self.formats = {
            "keyword": self.make_format("#facc15", bold=True),
            "string": self.make_format("#86efac"),
            "comment": self.make_format("#64748b", italic=True),
            "number": self.make_format("#f9a8d4"),
            "tag": self.make_format("#22d3ee", bold=True),
            "attr": self.make_format("#fbbf24"),
            "selector": self.make_format("#c084fc"),
        }

    @staticmethod
    def make_format(color, bold=False, italic=False):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    def apply_regex(self, text, pattern, fmt_key):
        for match in re.finditer(pattern, text):
            self.setFormat(match.start(), match.end() - match.start(), self.formats[fmt_key])

    def highlightBlock(self, text):
        if self.language in ("html", "xml"):
            self.apply_regex(text, r"<!--.*?-->", "comment")
            self.apply_regex(text, r"</?[\w:.-]+", "tag")
            self.apply_regex(text, r"\s[\w:-]+(?=\=)", "attr")
            self.apply_regex(text, r"\"[^\"\\]*(?:\\.[^\"\\]*)*\"|'[^'\\]*(?:\\.[^'\\]*)*'", "string")
            return

        if self.language == "css":
            self.apply_regex(text, r"/\*.*?\*/", "comment")
            self.apply_regex(text, r"(^|[{};])\s*[^{};:]+(?=\s*\{)", "selector")
            self.apply_regex(text, r"#[0-9a-fA-F]{3,8}\b|\b\d+(?:\.\d+)?(?:px|rem|em|%|vh|vw)?\b", "number")
            self.apply_regex(text, r"\"[^\"\\]*(?:\\.[^\"\\]*)*\"|'[^'\\]*(?:\\.[^'\\]*)*'", "string")
            return

        if self.language == "json":
            self.apply_regex(text, r"\"(?:[^\"\\]|\\.)*\"(?=\s*:)", "attr")
            self.apply_regex(text, r"\"(?:[^\"\\]|\\.)*\"", "string")
            self.apply_regex(text, r"\b(true|false|null)\b|-?\b\d+(?:\.\d+)?\b", "number")
            return

        keywords = (
            "and|as|async|await|break|case|catch|class|const|continue|def|elif|else|except|false|finally|for|from|"
            "function|if|import|in|let|new|null|or|pass|return|switch|throw|true|try|var|while|with|yield|"
            "public|private|protected|static|void|int|float|double|string|using|namespace|include"
        )
        self.apply_regex(text, rf"\b({keywords})\b", "keyword")
        self.apply_regex(text, r"#.*$|//.*$", "comment")
        self.apply_regex(text, r"\"[^\"\\]*(?:\\.[^\"\\]*)*\"|'[^'\\]*(?:\\.[^'\\]*)*'|`[^`]*`", "string")
        self.apply_regex(text, r"\b\d+(?:\.\d+)?\b", "number")

class HistoryItemWidget(QWidget):
    clicked = Signal(str)
    rename_req = Signal(str)
    delete_req = Signal(str)
    
    def __init__(self, session_id, name, is_active=False):
        super().__init__()
        self.sid = session_id
        self.name = name
        l = QHBoxLayout(self); l.setContentsMargins(5,2,5,2); l.setSpacing(5)
        
        self.btn = QPushButton(name.upper())
        self.btn.setObjectName("HistoryBtnActive" if is_active else "HistoryBtn")
        self.btn.clicked.connect(lambda: self.clicked.emit(self.sid))
        l.addWidget(self.btn, 1)
        
        rename = QPushButton(); rename.setObjectName("IconBtn")
        rename.setIcon(make_history_icon("pen", "#facc15"))
        rename.setIconSize(QSize(18, 18))
        rename.setToolTip("Rename chat")
        rename.setFixedSize(28, 24); rename.clicked.connect(lambda: self.rename_req.emit(self.sid))
        l.addWidget(rename)
        
        delete = QPushButton(); delete.setObjectName("DeleteBtn")
        delete.setIcon(make_history_icon("trash", "#f43f5e"))
        delete.setIconSize(QSize(18, 18))
        delete.setToolTip("Delete chat")
        delete.setFixedSize(28, 24); delete.clicked.connect(lambda: self.delete_req.emit(self.sid))
        l.addWidget(delete)

class ReadyDualAI(QMainWindow):
    def __init__(self):
        super().__init__()
        config_path = os.path.join(SCRIPT_DIR, "config.json")
        self.engine = Engine(config_path)
        self.engine.cached_models = []
        self.auto_approve = self.engine.config.get("auto_approve", False)
        self.setWindowTitle(APP_WINDOW_TITLE)
        self.resize(1360, 860)
        self.layout_state_path = os.path.join(SCRIPT_DIR, "layout_state.json")
        self.default_layout_state = None
        self.default_dataset_path = os.path.join(SCRIPT_DIR, "datasets", "ready_dual_tools.jsonl")
        self.pending_attachments = []
        
        # Colors
        self.ACCENT_YELLOW = "#facc15"
        self.ACCENT_CYAN = "#22d3ee"
        self.ACCENT_EMERALD = "#10b981"
        self.ACCENT_ORANGE = "#f97316"
        self.ACCENT_ROSE = "#f43f5e"
        
        # Bridge & Engine
        self.bridge = AIBridge()
        self.bridge.chat_signal.connect(self.add_message)
        self.bridge.log_signal.connect(self.add_log)
        self.bridge.status_signal.connect(self.update_status)
        self.bridge.canvas_signal.connect(self.update_canvas)
        self.bridge.approval_signal.connect(self._show_approval_dialog)

        self.apply_window_icon()
        self.ensure_default_config_sections()
        
        # Pre-load models to prevent settings freeze
        self.loader = ModelLoader(self.engine)
        self.loader.models_loaded.connect(self.on_models_ready)
        self.loader.start()
        
        self.init_ui()
        self.capture_default_layout()
        self.restore_saved_layout()
        self.populate_history()
        self.setStyleSheet(QSS_THEME)

    def on_models_ready(self, models):
        self.engine.cached_models = models

    def create_lightning_icon(self, size=256):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        s = size / 256
        draw.rounded_rectangle([s*24, s*24, s*232, s*232], radius=44*s, fill="#050505", outline=self.ACCENT_YELLOW, width=max(2, int(4*s)))
        draw.polygon(
            [
                (s*146, s*40), (s*76, s*138), (s*126, s*138),
                (s*106, s*218), (s*184, s*112), (s*136, s*112)
            ],
            fill=self.ACCENT_YELLOW,
            outline="#fef08a",
            width=max(1, int(2*s))
        )
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, size, size, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qimg)

    def apply_window_icon(self):
        icon = QIcon()
        for size in (16, 24, 32, 48, 64, 128, 256):
            icon.addPixmap(self.create_lightning_icon(size))
        app = QApplication.instance()
        if app:
            app.setWindowIcon(icon)
        self.setWindowIcon(icon)

    def ensure_default_config_sections(self):
        search_cfg = self.engine.config.setdefault("search", {})
        search_cfg.setdefault("provider", "duckduckgo")
        search_cfg.setdefault("brave_api_key", self.engine.config.get("brave_api_key", ""))
        search_cfg.setdefault("google_api_key", "")
        search_cfg.setdefault("google_cx", "")
        capabilities = self.engine.config.setdefault("capabilities", {})
        capabilities.setdefault("manager", {"vision": False})
        capabilities.setdefault("coder", {"vision": False})
        self.engine.config.setdefault("donation", {"url": ""})
        datasets = self.engine.config.setdefault("datasets", [])
        default_path = self.default_dataset_path.replace("\\", "/")
        if not any((d.get("path", "").replace("\\", "/") == default_path) for d in datasets if isinstance(d, dict)):
            datasets.insert(0, {
                "name": "Ready Agentic Tool Protocol",
                "path": default_path,
                "enabled": True
            })

    def on_settings(self):
        d = QDialog(self)
        d.setWindowTitle("SYSTEM CONFIGURATION")
        d.resize(720, 780)
        outer = QVBoxLayout(d)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(18, 18, 18, 18)
        v.setSpacing(10)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        def section(title):
            label = QLabel(title)
            label.setStyleSheet(f"color:{self.ACCENT_YELLOW}; font-weight:bold; margin-top:10px;")
            v.addWidget(label)

        def add_line(label, current, password=False):
            v.addWidget(QLabel(label))
            entry = QLineEdit(str(current or ""))
            if password:
                entry.setEchoMode(QLineEdit.Password)
            v.addWidget(entry)
            return entry

        def add_spin(label, current):
            v.addWidget(QLabel(label))
            spin = QSpinBox()
            spin.setRange(1, 262144)
            spin.setValue(int(current or 8192))
            v.addWidget(spin)
            return spin

        def add_combo(label, current, options):
            v.addWidget(QLabel(label))
            cb = QComboBox()
            cb.setEditable(True)
            values = ["auto"]
            for option in options:
                if option and option not in values:
                    values.append(option)
            if current and current not in values:
                values.insert(1, current)
            cb.addItems(values)
            cb.setCurrentText(str(current or "auto"))
            v.addWidget(cb)
            return cb

        def add_choice(label, current, options):
            v.addWidget(QLabel(label))
            cb = QComboBox()
            cb.addItems(options)
            if current in options:
                cb.setCurrentText(current)
            v.addWidget(cb)
            return cb

        def add_text(label, current):
            v.addWidget(QLabel(label))
            editor = QPlainTextEdit()
            editor.setPlainText(str(current or ""))
            editor.setMinimumHeight(130)
            v.addWidget(editor)
            return editor

        manager_cfg = self.engine.config.setdefault("manager", {})
        coder_cfg = self.engine.config.setdefault("coder", {})
        ui_cfg = self.engine.config.setdefault("ui", {})
        ui_cfg.pop("window_title", None)
        search_cfg = self.engine.config.setdefault("search", {})
        donation_cfg = self.engine.config.setdefault("donation", {})
        capabilities = self.engine.config.setdefault("capabilities", {})

        section("MANAGER")
        mgr_url = add_line("API URL", manager_cfg.get("url", "http://localhost:1234/v1"))
        mgr_model = add_combo("Model", manager_cfg.get("model", "auto"), self.engine.cached_models)
        mgr_tokens = add_spin("Max Tokens", manager_cfg.get("max_tokens", 8192))
        mgr_system = add_text("System Message", manager_cfg.get("system_message", ""))

        section("CODER")
        coder_url = add_line("API URL", coder_cfg.get("url", "http://localhost:1234/v1"))
        coder_model = add_combo("Model", coder_cfg.get("model", "auto"), self.engine.cached_models)
        coder_tokens = add_spin("Max Tokens", coder_cfg.get("max_tokens", 8192))
        coder_system = add_text("System Message", coder_cfg.get("system_message", ""))

        section("WEB SEARCH")
        search_provider = add_choice(
            "Default Search Provider for ~@search@~",
            search_cfg.get("provider", "duckduckgo"),
            ["duckduckgo", "brave", "google"]
        )
        brave_key = add_line("Brave Search API Key", search_cfg.get("brave_api_key", self.engine.config.get("brave_api_key", "")), password=True)
        google_key = add_line("Google API Key", search_cfg.get("google_api_key", ""), password=True)
        google_cx = add_line("Google Search Engine ID (CX)", search_cfg.get("google_cx", ""))

        section("SAFETY")
        auto_approve = QCheckBox("Auto-approve terminal commands and file writes")
        auto_approve.setChecked(self.auto_approve)
        v.addWidget(auto_approve)

        section("MODEL CAPABILITIES")
        manager_vision = QCheckBox("Manager model can read images")
        manager_vision.setChecked(bool(capabilities.get("manager", {}).get("vision", False)))
        coder_vision = QCheckBox("Coder model can read images")
        coder_vision.setChecked(bool(capabilities.get("coder", {}).get("vision", False)))
        v.addWidget(manager_vision)
        v.addWidget(coder_vision)

        section("WINDOW")
        theme_cb = add_combo("Theme", ui_cfg.get("theme", "Dark"), ["Dark"])

        section("OPEN SOURCE")
        donation_link = add_line("Donation URL", donation_cfg.get("url", ""))

        save = QPushButton("SAVE CONFIGURATION")
        save.setObjectName("NewSessionBtn")
        save.clicked.connect(d.accept)
        outer.addWidget(save)

        if d.exec():
            manager_cfg["url"] = mgr_url.text().strip() or "http://localhost:1234/v1"
            manager_cfg["model"] = mgr_model.currentText().strip() or "auto"
            manager_cfg["max_tokens"] = mgr_tokens.value()
            manager_cfg["system_message"] = mgr_system.toPlainText()

            coder_cfg["url"] = coder_url.text().strip() or "http://localhost:1234/v1"
            coder_cfg["model"] = coder_model.currentText().strip() or "auto"
            coder_cfg["max_tokens"] = coder_tokens.value()
            coder_cfg["system_message"] = coder_system.toPlainText()

            self.engine.config["brave_api_key"] = brave_key.text().strip()
            search_cfg["provider"] = search_provider.currentText().strip() or "duckduckgo"
            search_cfg["brave_api_key"] = brave_key.text().strip()
            search_cfg["google_api_key"] = google_key.text().strip()
            search_cfg["google_cx"] = google_cx.text().strip()
            self.engine.config["brave_api_key"] = search_cfg["brave_api_key"]
            self.engine.config["auto_approve"] = auto_approve.isChecked()
            capabilities.setdefault("manager", {})["vision"] = manager_vision.isChecked()
            capabilities.setdefault("coder", {})["vision"] = coder_vision.isChecked()
            ui_cfg["theme"] = theme_cb.currentText().strip() or "Dark"
            donation_cfg["url"] = donation_link.text().strip()

            self.auto_approve = self.engine.config["auto_approve"]
            self.setWindowTitle(APP_WINDOW_TITLE)
            if self.engine.manager_history and self.engine.manager_history[0].get("role") == "system":
                self.engine.manager_history[0]["content"] = manager_cfg["system_message"]
            if self.engine.coder_history and self.engine.coder_history[0].get("role") == "system":
                self.engine.coder_history[0]["content"] = coder_cfg["system_message"]

            self.engine._save_config()
            self.sync_auto_label()
            self.add_log("[SYSTEM] Configuration updated.")

    def create_agent_logo(self, size=256):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0)); draw = ImageDraw.Draw(img); s = size/256
        pc = "#334155"
        for i in range(5):
            draw.rectangle([s*(60+i*35), s*20, s*(75+i*35), s*45], fill=pc)
            draw.rectangle([s*(60+i*35), s*211, s*(75+i*35), s*236], fill=pc)
            draw.rectangle([s*20, s*(60+i*35), s*45, s*(75+i*35)], fill=pc)
            draw.rectangle([s*211, s*(60+i*35), s*236, s*(75+i*35)], fill=pc)
        draw.rounded_rectangle([s*40, s*40, s*216, s*216], radius=20*s, fill="#0a0a0a", outline=self.ACCENT_YELLOW, width=int(3*s))
        draw.polygon([(s*140,s*50),(s*140,s*120),(s*190,s*120),(s*110,s*230),(s*110,s*140),(s*50,s*140),(s*140,s*50)], fill=self.ACCENT_YELLOW, outline="#fef08a", width=int(2*s))
        data = img.tobytes("raw", "RGBA"); qimg = QImage(data, size, size, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qimg)

    def init_ui(self):
        # Set MainWindow Dock settings
        self.setDockOptions(QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks | QMainWindow.AnimatedDocks)
        
        # Area combining all directions
        all_areas = Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea
        self.setTabPosition(all_areas, QTabWidget.North)
        
        # Central Anchor: Empty to allow Docks to fill 100%
        # QMainWindow fills docks automatically if central is minimal
        self.setCentralWidget(QWidget())
        self.centralWidget().setMaximumSize(0,0)

        # --- DOCKABLE PANES ---
        # 1. Sidebar Dock (Far Left)
        self.sidebar_pane = QWidget(); self.sidebar_pane.setObjectName("Sidebar")
        side_v = QVBoxLayout(self.sidebar_pane); side_v.setContentsMargins(15,20,15,15)
        
        logo = QLabel(); logo.setPixmap(self.create_agent_logo(128).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)); logo.setAlignment(Qt.AlignCenter)
        side_v.addWidget(logo); t1 = QLabel(APP_NAME.upper()); t1.setObjectName("SidebarTitle"); t1.setAlignment(Qt.AlignCenter); side_v.addWidget(t1)
        t2 = QLabel(APP_SUBTITLE); t2.setObjectName("SidebarSubtitle"); t2.setAlignment(Qt.AlignCenter); side_v.addWidget(t2)
        
        self.new_btn = QPushButton("+  NEW SESSION"); self.new_btn.setObjectName("NewSessionBtn"); self.new_btn.clicked.connect(self.new_chat)
        apply_glow(self.new_btn, self.ACCENT_YELLOW); side_v.addWidget(self.new_btn); side_v.addSpacing(15)
        
        for nav, handler in [
            ("SETTINGS", self.on_settings),
            ("TOOL GUIDE", self.show_tool_guide),
            ("DATASETS", self.show_datasets_dialog),
            ("SUPPORT / DONATE", self.show_support_dialog),
        ]:
            btn = QPushButton(nav); side_v.addWidget(btn); side_v.addSpacing(8)
            btn.clicked.connect(handler)

        linkedin_btn = QPushButton("ALI DHEYAA")
        linkedin_btn.setIcon(make_linkedin_icon(18))
        linkedin_btn.setIconSize(QSize(18, 18))
        linkedin_btn.clicked.connect(self.open_linkedin)
        side_v.addWidget(linkedin_btn); side_v.addSpacing(8)
        
        side_v.addWidget(QLabel("HISTORY"), 0, Qt.AlignCenter)
        self.hist_scroll = QScrollArea(); self.hist_cont = QWidget(); self.hist_layout = QVBoxLayout(self.hist_cont)
        self.hist_layout.setContentsMargins(0,5,0,0); self.hist_layout.addStretch()
        self.hist_scroll.setWidget(self.hist_cont); self.hist_scroll.setWidgetResizable(True); side_v.addWidget(self.hist_scroll)

        self.sidebar_dock = QDockWidget("TOOLS", self); self.sidebar_dock.setWidget(self.sidebar_pane)
        self.sidebar_dock.setObjectName("DockTools")
        self.sidebar_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.sidebar_dock)
        
        # 2. Console Dock (Inner Left)
        self.console_pane = self.build_mono_pane("📟 TOOL CONSOLE", self.ACCENT_EMERALD, "PaneConsole", "PaneConsoleText")
        self.console_edit = self.console_pane.findChild(QPlainTextEdit)
        self.console_dock = QDockWidget("TOOL CONSOLE", self); self.console_dock.setWidget(self.console_pane)
        self.console_dock.setObjectName("DockToolConsole")
        self.console_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.splitDockWidget(self.sidebar_dock, self.console_dock, Qt.Horizontal)
        
        # 3. Chat Dock (Middle)
        self.chat_pane = QFrame(); self.chat_pane.setObjectName("Pane"); cp_v = QVBoxLayout(self.chat_pane); cp_v.setContentsMargins(0,0,0,10); cp_v.setSpacing(0)
        
        self.chat_scroll = QScrollArea(); self.chat_cont = QWidget(); self.chat_layout = QVBoxLayout(self.chat_cont); self.chat_layout.setContentsMargins(20,20,20,20); self.chat_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_cont); self.chat_scroll.setWidgetResizable(True); cp_v.addWidget(self.chat_scroll)
        
        self.attachment_label = QLabel("")
        self.attachment_label.setStyleSheet("color:#64748b; font-size:10px; padding:0 15px;")
        cp_v.addWidget(self.attachment_label)

        inp_h = QHBoxLayout(); inp_h.setContentsMargins(10,10,10,0); ibox = QFrame(); ibox.setStyleSheet("background:#0f0f0f; border:1px solid #1a1a1a; border-radius:6px;")
        ibox_h = QHBoxLayout(ibox); self.input = QLineEdit(); self.input.setPlaceholderText("Instruct the Manager..."); self.input.setStyleSheet("border:none;"); self.input.returnPressed.connect(self.send_message)
        ibox_h.addWidget(self.input, 1); self.send_btn = QPushButton("➤"); self.send_btn.setObjectName("ControlBtn"); self.send_btn.setStyleSheet(f"color:{self.ACCENT_YELLOW}; border:1px solid {self.ACCENT_YELLOW};"); self.send_btn.clicked.connect(self.send_message)
        attach_btn = QPushButton(); attach_btn.setObjectName("ControlBtn"); attach_btn.setIcon(make_attachment_icon(22, self.ACCENT_YELLOW)); attach_btn.setIconSize(QSize(22, 22)); attach_btn.setToolTip("Attach file or image"); attach_btn.clicked.connect(self.attach_files)
        ibox_h.addWidget(attach_btn); ibox_h.addWidget(self.send_btn); self.stop_btn = QPushButton("■"); self.stop_btn.setObjectName("ControlBtn"); self.stop_btn.setStyleSheet(f"color:{self.ACCENT_ROSE}; border:1px solid {self.ACCENT_ROSE};"); self.stop_btn.clicked.connect(self.stop_generation)
        ibox_h.addWidget(self.stop_btn); cp_v.addLayout(inp_h); inp_h.addWidget(ibox)
        
        self.chat_dock = QDockWidget("MANAGER CHAT", self); self.chat_dock.setWidget(self.chat_pane)
        self.chat_dock.setObjectName("DockManagerChat")
        self.chat_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.splitDockWidget(self.console_dock, self.chat_dock, Qt.Horizontal)
        
        # 4. Canvas Dock (Far Right)
        self.canvas_pane = self.build_mono_pane("</> CANVAS", self.ACCENT_CYAN, "PaneCanvas", "PaneCanvasText")
        self.canvas_edit = self.canvas_pane.findChild(QPlainTextEdit)
        self.canvas_dock = QDockWidget("EXPERT CANVAS", self); self.canvas_dock.setWidget(self.canvas_pane)
        self.canvas_dock.setObjectName("DockExpertCanvas")
        self.canvas_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.splitDockWidget(self.chat_dock, self.canvas_dock, Qt.Horizontal)
        
        # Force Chat to be the largest (Hub)
        self.resizeDocks([self.sidebar_dock, self.console_dock, self.chat_dock, self.canvas_dock], [200, 300, 600, 300], Qt.Horizontal)
        self.dock_widgets = [self.sidebar_dock, self.console_dock, self.chat_dock, self.canvas_dock]

        # --- COMMAND DASHBOARD (STATUS STRIPE) ---
        self.init_status_bar()
        self.init_menu()
        
    def init_status_bar(self):
        sb = self.statusBar()
        sb.setObjectName("StatusBar")
        sb.setSizeGripEnabled(False)
        
        # Dashboard Widgets
        self.mgr_st = QLabel("● MANAGER: READY"); self.mgr_st.setStyleSheet(f"color:{self.ACCENT_EMERALD};")
        self.cdr_st = QLabel("● CODER: STANDBY"); self.cdr_st.setStyleSheet("color:#64748b;")
        self.auto_lb = QLabel()
        self.sync_auto_label()
        
        def sep():
            s = QLabel("|"); s.setStyleSheet("color: #1a1a1a; font-weight: normal; padding: 0 10px;"); return s

        # Layout
        sb.addPermanentWidget(self.mgr_st)
        sb.addPermanentWidget(sep())
        sb.addPermanentWidget(self.cdr_st)
        sb.addPermanentWidget(sep())
        # Spacer
        sp = QLabel(""); sp.setMinimumWidth(100); sb.addPermanentWidget(sp, 1)
        sb.addPermanentWidget(sep())
        sb.addPermanentWidget(self.auto_lb)

    def sync_auto_label(self):
        if not hasattr(self, "auto_lb"):
            return
        self.auto_lb.setText("AUTO-APPROVE: ON" if self.auto_approve else "AUTO-APPROVE: OFF")
        color = self.ACCENT_YELLOW if self.auto_approve else "#4b5563"
        self.auto_lb.setStyleSheet(f"color:{color};")

    def init_menu(self):
        menubar = self.menuBar()
        layout_m = menubar.addMenu("Layout")
        reset_layout_action = layout_m.addAction("Reset Layout to Default")
        reset_layout_action.triggered.connect(self.reset_layout_to_default)
        help_m = menubar.addMenu("Help")
        about_action = help_m.addAction(f"About {APP_NAME}")
        about_action.triggered.connect(lambda: webbrowser.open("https://github.com/ReadyZer0/Ready-Agentic-LLM"))
        linkedin_action = help_m.addAction(make_linkedin_icon(18), "Ali Dheyaa on LinkedIn")
        linkedin_action.triggered.connect(self.open_linkedin)
        donate_action = help_m.addAction("Donate / Support")
        donate_action.triggered.connect(self.show_support_dialog)
        guide_action = help_m.addAction("Tool Documentation")
        guide_action.triggered.connect(self.show_tool_guide)

    def capture_default_layout(self):
        self.default_layout_state = QByteArray(self.saveState(LAYOUT_STATE_VERSION))

    def save_layout_state(self):
        data = {
            "version": LAYOUT_STATE_VERSION,
            "state": bytes(self.saveState(LAYOUT_STATE_VERSION)).hex(),
        }
        try:
            with open(self.layout_state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            if hasattr(self, "console_edit"):
                self.add_log(f"[SYSTEM] Layout auto-save failed: {exc}")

    def restore_saved_layout(self):
        if not os.path.exists(self.layout_state_path):
            return
        try:
            with open(self.layout_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") != LAYOUT_STATE_VERSION:
                return
            state = data.get("state", "")
            if state and not self.restoreState(QByteArray(bytes.fromhex(state)), LAYOUT_STATE_VERSION):
                self.add_log("[SYSTEM] Saved layout could not be restored; using default layout.")
        except Exception as exc:
            self.add_log(f"[SYSTEM] Saved layout could not be loaded: {exc}")

    def reset_layout_to_default(self):
        if self.default_layout_state:
            self.restoreState(self.default_layout_state, LAYOUT_STATE_VERSION)
        for dock in getattr(self, "dock_widgets", []):
            dock.setVisible(True)
        self.save_layout_state()
        self.add_log("[SYSTEM] Layout reset to default.")

    def createPopupMenu(self):
        menu = QMenu(self)
        docks = getattr(self, "dock_widgets", [])
        for dock in docks:
            action = menu.addAction(dock.windowTitle())
            action.setCheckable(True)
            action.setChecked(dock.isVisible())
            action.setEnabled(True)
            action.toggled.connect(dock.setVisible)
        return menu

    def build_mono_pane(self, title_text, color, obj_id="", text_id=""):
        p = QFrame(); p.setObjectName("Pane")
        if obj_id: p.setObjectName(obj_id)
        v = QVBoxLayout(p); v.setContentsMargins(0,0,0,0); v.setSpacing(0)
        
        e = QPlainTextEdit(); e.setReadOnly(True); e.setStyleSheet(f"color:{color};")
        v.addWidget(e)
        return p

    def open_linkedin(self):
        webbrowser.open("https://www.linkedin.com/in/ali-dheyaa-abdulwahab-6bbbb1239/")

    def copy_to_clipboard(self, text, label="Value"):
        QApplication.clipboard().setText(text)
        self.add_log(f"[SYSTEM] Copied {label}.")

    def add_donation_tab(self, tabs, title, rows, action_label=None, action_url=None, qr_path=None):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        if qr_path:
            qr_label = QLabel()
            qr_label.setAlignment(Qt.AlignCenter)
            if os.path.exists(qr_path):
                pixmap = QPixmap(qr_path).scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                qr_label.setPixmap(pixmap)
            else:
                qr_label.setText(f"QR image missing:\n{qr_path}")
                qr_label.setStyleSheet(f"color:{self.ACCENT_ROSE};")
            layout.addWidget(qr_label)
        for label, value in rows:
            layout.addWidget(QLabel(label))
            line = QLineEdit(value)
            line.setReadOnly(True)
            layout.addWidget(line)
            copy_btn = QPushButton(f"COPY {label.upper()}")
            copy_btn.clicked.connect(lambda _, val=value, lab=label: self.copy_to_clipboard(val, lab))
            layout.addWidget(copy_btn)
        if action_label and action_url:
            action = QPushButton(action_label)
            action.setObjectName("NewSessionBtn")
            action.clicked.connect(lambda: webbrowser.open(action_url))
            layout.addWidget(action)
        layout.addStretch()
        tabs.addTab(page, title)

    def show_support_dialog(self):
        d = QDialog(self)
        d.setWindowTitle("SUPPORT DEVELOPMENT")
        d.resize(560, 520)
        v = QVBoxLayout(d)

        title = QLabel("SUPPORT DEVELOPMENT")
        title.setStyleSheet(f"color:{self.ACCENT_YELLOW}; font-weight:bold; font-size:16px;")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        subtitle = QLabel(f"Choose your preferred way to support {APP_NAME}.")
        subtitle.setStyleSheet("color:#94a3b8;")
        subtitle.setAlignment(Qt.AlignCenter)
        v.addWidget(subtitle)

        tabs = QTabWidget()
        self.add_donation_tab(
            tabs,
            "Payoneer",
            [("Email", "alixghostt@gmail.com")],
            "PROCEED TO PAYONEER",
            "https://login.payoneer.com/"
        )
        self.add_donation_tab(
            tabs,
            "Wire (NBI)",
            [("Bank Name", "NBI"), ("IBAN", "IQ89NBIQ859002100061176")]
        )
        self.add_donation_tab(
            tabs,
            "Super Qi",
            [("Method", "Scan with Super Qi App")],
            qr_path=os.path.join(SCRIPT_DIR, "assets", "super_qi_qr_final.jpg")
        )
        self.add_donation_tab(
            tabs,
            "USDT",
            [("Network", "TRC20"), ("Address", "TUUeqeUP5ZAr7V8KVciHfBfvUVj8TsTtTL")],
            "PAY WITH TRUST WALLET",
            "https://link.trustwallet.com/send?coin=195&address=TUUeqeUP5ZAr7V8KVciHfBfvUVj8TsTtTL&token_id=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
            qr_path=os.path.join(SCRIPT_DIR, "assets", "usdt_qr.jpg")
        )
        v.addWidget(tabs, 1)

        linkedin = QPushButton("ALI DHEYAA ON LINKEDIN")
        linkedin.setIcon(make_linkedin_icon(18))
        linkedin.clicked.connect(self.open_linkedin)
        v.addWidget(linkedin)

        close = QPushButton("CLOSE")
        close.clicked.connect(d.accept)
        v.addWidget(close)
        d.exec()

    def populate_history(self):
        while self.hist_layout.count() > 1:
            i = self.hist_layout.takeAt(0)
            if i.widget(): i.widget().deleteLater()
        
        sessions = self.engine.list_sessions()
        if not sessions:
            empty = QLabel("No saved chats yet")
            empty.setStyleSheet("color:#4b5563; font-size:11px;")
            empty.setAlignment(Qt.AlignCenter)
            self.hist_layout.insertWidget(self.hist_layout.count()-1, empty)
            return

        for s in sessions:
            is_active = (s['id'] == self.engine.session_id)
            item = HistoryItemWidget(s['id'], s['name'], is_active)
            item.clicked.connect(self.load_session)
            item.rename_req.connect(self.rename_session_ui)
            item.delete_req.connect(self.delete_session_ui)
            self.hist_layout.insertWidget(self.hist_layout.count()-1, item)

    def clear_chat(self):
        while self.chat_layout.count() > 1:
            i = self.chat_layout.takeAt(0)
            if i.widget():
                i.widget().deleteLater()

    def refresh_attachment_label(self):
        if not hasattr(self, "attachment_label"):
            return
        if not self.pending_attachments:
            self.attachment_label.setText("")
            return
        names = ", ".join(os.path.basename(a["path"]) for a in self.pending_attachments)
        self.attachment_label.setText(f"ATTACHED: {names}")

    def attach_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach Files",
            SCRIPT_DIR,
            "Images and Files (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.txt *.md *.py *.js *.ts *.json *.html *.css *.xml *.yml *.yaml *.toml);;All Files (*.*)"
        )
        for path in paths:
            self.pending_attachments.append({"path": path})
        self.refresh_attachment_label()

    def paste_clipboard_image(self):
        image = QApplication.clipboard().image()
        if image.isNull():
            self.add_log("[WARNING] Clipboard does not contain an image.")
            return
        attach_dir = os.path.join(SCRIPT_DIR, "attachments")
        os.makedirs(attach_dir, exist_ok=True)
        filename = datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")
        path = os.path.join(attach_dir, filename)
        if image.save(path):
            self.pending_attachments.append({"path": path})
            self.refresh_attachment_label()
            self.add_log(f"[SYSTEM] Screenshot attached: {path}")
        else:
            self.add_log("[ERROR] Failed to save clipboard image.")

    def render_history_message(self, msg):
        role = msg.get("role")
        content = msg.get("content", "").strip()
        if not content:
            return

        if role == "user":
            self.add_message("YOU", content, self.ACCENT_YELLOW)
            return

        if role == "assistant":
            parsed = parse_sigils(content)
            segments = parsed.chat_segments if parsed.has_tools else [content]
            for segment in segments:
                clean = segment.strip()
                if clean and clean.upper() != "DONE":
                    self.add_message("MANAGER", clean, self.ACCENT_CYAN)

    def rename_session_ui(self, sid):
        current_name = next((s["name"] for s in self.engine.list_sessions() if s["id"] == sid), self.engine.session_name)
        new_name, ok = QInputDialog.getText(self, "Rename Session", "Enter New Task Name:", text=current_name)
        if ok and new_name:
            if self.engine.rename_session(sid, new_name):
                self.populate_history()

    def delete_session_ui(self, sid):
        was_active = (sid == self.engine.session_id)
        if self.engine.delete_session(sid):
            if was_active:
                self.clear_chat()
                self.add_log("[SYSTEM] Active session deleted; new chat ready.")
            self.populate_history()

    def load_session(self, sid):
        self.engine.save_session()
        if not self.engine.load_session(sid):
            self.add_log(f"[ERROR] Session not found: {sid}")
            return

        self.populate_history()
        self.clear_chat()
        for msg in self.engine.get_display_messages():
            self.render_history_message(msg)
        self.add_log(f"[SYSTEM] Loaded session: {self.engine.session_name}")

    def new_chat(self):
        if not self.engine.has_real_messages():
            self.engine.save_session(allow_empty=True)
            self.clear_chat()
            self.populate_history()
            self.add_log("[SYSTEM] New chat ready.")
            return

        self.engine.save_session()
        self.engine.reset_session(save_placeholder=True)
        self.clear_chat()
        self.populate_history()
        self.add_log("[SYSTEM] New chat ready.")

    def send_message(self):
        txt = self.input.text().strip()
        if not txt: return
        if getattr(self.engine, "_is_manager_running", False):
            self.add_log("[WARNING] Manager is already processing.")
            return
        attachments = list(self.pending_attachments)
        self.pending_attachments = []
        self.refresh_attachment_label()
        self.input.clear(); self.add_message("YOU", txt, self.ACCENT_YELLOW)
        if hasattr(self, "send_btn"):
            self.send_btn.setEnabled(False)
        # Fix: call the correct engine method
        self.engine.send_to_manager(
            txt,
            on_chat=lambda s, t: self.bridge.chat_signal.emit(s, t, self.ACCENT_CYAN),
            on_tool_log=self.bridge.log_signal.emit,
            on_status=self.bridge.status_signal.emit,
            on_coder_result=lambda content: self.bridge.canvas_signal.emit("Coder Result", content, ""),
            terminal_approve_fn=self._approve_terminal,
            write_approve_fn=self._approve_write,
            attachments=attachments
        )
        # Refresh history in background after a slight delay to allow naming logic
        QTimer.singleShot(2000, self.populate_history)

    def stop_generation(self):
        self.engine.cancel()
        self.add_log("[USER] Stop requested.")
        self.update_status("manager", "STOPPING")

    def _request_approval(self, title, content, editable=True, filepath=""):
        if self.auto_approve:
            return True, content

        result_event = threading.Event()
        request = {
            "title": title,
            "content": content,
            "editable": editable,
            "filepath": filepath,
            "approved": False,
            "edited": content,
            "event": result_event,
        }
        self.bridge.approval_signal.emit(request)
        result_event.wait(timeout=120)
        return request["approved"], request["edited"]

    def detect_code_language(self, filepath, content):
        ext = os.path.splitext(filepath or "")[1].lower()
        by_ext = {
            ".html": "html", ".htm": "html", ".xml": "xml", ".svg": "xml",
            ".css": "css",
            ".json": "json", ".jsonl": "json",
            ".py": "python", ".js": "javascript", ".ts": "javascript", ".jsx": "javascript", ".tsx": "javascript",
            ".java": "general", ".c": "general", ".cpp": "general", ".h": "general", ".hpp": "general",
            ".cs": "general", ".go": "general", ".rs": "general", ".php": "general", ".rb": "general",
            ".ps1": "general", ".sh": "general", ".bat": "general", ".cmd": "general",
            ".sql": "general", ".yaml": "general", ".yml": "general", ".toml": "general",
        }
        plain_exts = {".txt", ".md", ".eml", ".log", ".csv"}
        if ext in by_ext:
            return by_ext[ext]
        if ext in plain_exts:
            return None

        stripped = (content or "").strip()
        if not stripped:
            return None
        if re.search(r"(?is)^\s*<!doctype\s+html|<html\b|</\w+>|<\w+[\s>/]", stripped):
            return "html"
        if stripped.startswith(("{", "[")):
            try:
                json.loads(stripped)
                return "json"
            except Exception:
                pass
        if re.search(r"(?m)^\s*(def |class |import |from |function |const |let |var |#include|using |namespace |public |private )", stripped):
            return "general"
        if re.search(r"[{};]\s*$", stripped, re.MULTILINE) and re.search(r"\b(if|for|while|return|function|class|const|let|var)\b", stripped):
            return "general"
        return None

    def show_editor_context_menu(self, editor, point):
        menu = editor.createStandardContextMenu()
        menu.exec(editor.mapToGlobal(point))

    def _show_approval_dialog(self, request):
        d = QDialog(self)
        d.setWindowTitle(request["title"])
        d.resize(760, 520)
        v = QVBoxLayout(d)

        label = QLabel(request["title"])
        label.setStyleSheet(f"color:{self.ACCENT_YELLOW}; font-weight:bold;")
        v.addWidget(label)

        if request.get("filepath"):
            path_label = QLabel(request["filepath"])
            path_label.setStyleSheet("color:#64748b; font-family:Consolas;")
            v.addWidget(path_label)

        editor = QPlainTextEdit()
        editor.setPlainText(request["content"])
        editor.setReadOnly(not request.get("editable", True))
        editor.setStyleSheet("background:#000000; color:#d1d5db; font-family:Consolas;")
        editor.setContextMenuPolicy(Qt.CustomContextMenu)
        editor.customContextMenuRequested.connect(lambda point, ed=editor: self.show_editor_context_menu(ed, point))
        if request["title"] == "FILE WRITE REQUEST":
            language = self.detect_code_language(request.get("filepath", ""), request.get("content", ""))
            if language:
                editor._code_highlighter = CodeHighlighter(editor.document(), language)
        v.addWidget(editor, 1)

        buttons = QHBoxLayout()
        approve = QPushButton("APPROVE")
        approve.setStyleSheet(f"color:{self.ACCENT_EMERALD}; border:1px solid {self.ACCENT_EMERALD};")
        deny = QPushButton("DENY")
        deny.setStyleSheet(f"color:{self.ACCENT_ROSE}; border:1px solid {self.ACCENT_ROSE};")
        buttons.addWidget(approve)
        buttons.addWidget(deny)
        v.addLayout(buttons)

        approve.clicked.connect(d.accept)
        deny.clicked.connect(d.reject)

        accepted = d.exec() == QDialog.Accepted
        request["approved"] = accepted
        request["edited"] = editor.toPlainText() if accepted else request["content"]
        request["event"].set()

    def _approve_terminal(self, command):
        approved, _ = self._request_approval("TERMINAL COMMAND", command, editable=True)
        return approved

    def _approve_write(self, filepath, content):
        return self._request_approval("FILE WRITE REQUEST", content, editable=True, filepath=filepath)

    def show_tool_guide(self):
        guide = f"""{APP_NAME.upper()} TOOL GUIDE

Sigil shape
Every tool is a block:
~@toolname@~
arguments or payload
~@exit@~

How to add a new tool
1. Add a parser helper in core/sigil_parser.py if the payload needs structure.
2. Add the OS/API implementation in core/tools.py.
3. Add a dispatch branch in core/engine.py inside _execute_tool().
4. Add examples to datasets/ready_dual_tools.jsonl so models learn the new sigil.
5. Mention it in the Manager system prompt or fine-tuning dataset.

Current built-in sigils
~@read@~ absolute_or_relative_path ~@exit@~
~@write@~ filepath
content
~@exit@~
~@replace@~ filepath
---OLD---
exact existing snippet
---NEW---
replacement snippet
~@exit@~
~@terminal@~ Windows command ~@exit@~
~@explorer@~ directory ~@exit@~
~@search@~ query ~@exit@~     Uses the selected default provider: DuckDuckGo, Brave, or Google.
~@ddg@~ query ~@exit@~        Forces DuckDuckGo.
~@delegate@~ coding task ~@exit@~   Sends work to the Coder AI.

Suggested future sigil tools
~@patch@~ unified diff ~@exit@~       Apply safer, reviewable code edits.
~@test@~ command ~@exit@~             Run tests with structured pass/fail output.
~@lint@~ command ~@exit@~             Run linters/formatters separately from terminal.
~@http@~ method url json/body ~@exit@~ Call APIs without shelling out.
~@git@~ status/diff/branch args ~@exit@~ Restrict Git to safe operations.
~@memory@~ key/value ~@exit@~         Save durable project facts.
~@vision@~ image path + question ~@exit@~ Analyze screenshots or UI captures.
~@dataset@~ path/action ~@exit@~      Export or inject tool-learning datasets.
~@browser@~ url/task ~@exit@~         Controlled web navigation.

Image attachments
If Manager vision is off and Coder vision is on, image tasks are delegated directly to Coder.
If both are off, the app tells the user neither model can process images.
"""
        d = QDialog(self)
        d.setWindowTitle("TOOL CREATION GUIDE")
        d.resize(780, 680)
        v = QVBoxLayout(d)
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(guide)
        editor.setStyleSheet("background:#000000; color:#d1d5db; font-family:Consolas;")
        v.addWidget(editor, 1)
        close = QPushButton("CLOSE")
        close.clicked.connect(d.accept)
        v.addWidget(close)
        d.exec()

    def show_datasets_dialog(self):
        d = QDialog(self)
        d.setWindowTitle("AI DATASETS")
        d.resize(820, 680)
        v = QVBoxLayout(d)

        intro = QLabel("Datasets teach models how to use sigils, tools, and the Manager-to-Coder handoff.")
        intro.setStyleSheet(f"color:{self.ACCENT_YELLOW}; font-weight:bold;")
        v.addWidget(intro)

        datasets = self.engine.config.setdefault("datasets", [])
        dataset_list = QPlainTextEdit()
        dataset_list.setReadOnly(True)
        dataset_list.setMinimumHeight(120)
        v.addWidget(dataset_list)

        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setStyleSheet("background:#000000; color:#d1d5db; font-family:Consolas;")
        v.addWidget(preview, 1)

        path_row = QHBoxLayout()
        path_entry = QLineEdit()
        browse = QPushButton("BROWSE")
        path_row.addWidget(path_entry, 1)
        path_row.addWidget(browse)
        v.addLayout(path_row)

        def refresh():
            lines = []
            for item in datasets:
                if isinstance(item, dict):
                    lines.append(f"{'[ON]' if item.get('enabled', True) else '[OFF]'} {item.get('name', 'Dataset')} -> {item.get('path', '')}")
            dataset_list.setPlainText("\n".join(lines))
            default_path = self.default_dataset_path
            if os.path.exists(default_path):
                with open(default_path, "r", encoding="utf-8") as f:
                    preview.setPlainText(f.read())
            else:
                preview.setPlainText("Default dataset missing: " + default_path)

        def browse_dataset():
            path, _ = QFileDialog.getOpenFileName(
                d,
                "Select Dataset",
                SCRIPT_DIR,
                "Datasets (*.jsonl *.json *.csv *.txt);;All Files (*.*)"
            )
            if path:
                path_entry.setText(path)

        def add_dataset():
            path = path_entry.text().strip()
            if not path:
                return
            datasets.append({
                "name": os.path.basename(path),
                "path": path,
                "enabled": True
            })
            self.engine._save_config()
            path_entry.clear()
            refresh()
            self.add_log(f"[SYSTEM] Dataset added: {path}")

        browse.clicked.connect(browse_dataset)
        add = QPushButton("ADD DATASET")
        add.clicked.connect(add_dataset)
        v.addWidget(add)

        close = QPushButton("CLOSE")
        close.clicked.connect(d.accept)
        v.addWidget(close)
        refresh()
        d.exec()

    @Slot(str, str, str)
    def add_message(self, sender, text, color):
        if text.strip().upper() == "DONE":
            return
        if sender.lower() == "assistant":
            sender = "MANAGER"
        msg = MessageWidget(sender, text, color)
        self.chat_layout.insertWidget(self.chat_layout.count()-1, msg)
        self.chat_scroll.verticalScrollBar().setValue(self.chat_scroll.verticalScrollBar().maximum())

    @Slot(str)
    def add_log(self, text):
        self.console_edit.appendPlainText(text)
        self.console_edit.verticalScrollBar().setValue(self.console_edit.verticalScrollBar().maximum())

    @Slot(str, str)
    def update_status(self, target, text):
        t = text.upper()
        if t in ("READY", "ERROR", "STOPPED") and hasattr(self, "send_btn"):
            self.send_btn.setEnabled(True)
            QTimer.singleShot(500, self.populate_history)
        if target == "manager": 
            color = self.ACCENT_EMERALD if t == "READY" else self.ACCENT_YELLOW
            self.mgr_st.setText(f"● MANAGER: {t}")
            self.mgr_st.setStyleSheet(f"color: {color}")
        elif target == "coder": 
            color = "#64748b" if "STANDBY" in t else self.ACCENT_ORANGE
            self.cdr_st.setText(f"● CODER: {t}")
            self.cdr_st.setStyleSheet(f"color: {color}")

    @Slot(str, str, str)
    def update_canvas(self, title, content, path):
        self.canvas_edit.setPlainText(content)

    def closeEvent(self, event):
        self.save_layout_state()
        super().closeEvent(event)

if __name__ == "__main__":
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ReadyDualAI.StrategicConsole")
        except Exception:
            pass
    app = QApplication(sys.argv)
    window = ReadyDualAI()
    window.show()
    sys.exit(app.exec())
