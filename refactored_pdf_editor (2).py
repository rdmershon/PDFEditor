import hashlib
import os
import sys
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

import pymupdf

from PyQt6.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QPoint,
    QStandardPaths,
    Qt,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSizePolicy,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "Python Pro PDF Editor"
MAX_UNDO_STATES = 20


# ============================================================
# APPLICATION STYLE
# ============================================================

MODERN_STYLE = """
QMainWindow {
    background-color: #2b2b2b;
}
QToolBar {
    background-color: #3c3f41;
    border-bottom: 1px solid #222222;
    padding: 5px;
    spacing: 8px;
}
QToolBar QToolButton {
    color: #e0e0e0;
    font-size: 13px;
    font-weight: bold;
    padding: 8px 12px;
    border-radius: 4px;
    border: 1px solid transparent;
}
QToolBar QToolButton:hover {
    background-color: #4b4d4f;
    border: 1px solid #5c5e60;
}
QToolBar QToolButton:checked {
    background-color: #007acc;
    color: white;
    border: 1px solid #005a9e;
}
QScrollArea {
    background-color: #525659;
    border: none;
}
QDialog {
    background-color: #2b2b2b;
}
QLabel {
    font-size: 13px;
    color: #e0e0e0;
}
QCheckBox {
    color: #e0e0e0;
    font-size: 13px;
}
QPushButton {
    background-color: #007acc;
    color: white;
    border-radius: 5px;
    padding: 6px 15px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #0098ff;
}
QTextEdit, QSpinBox, QComboBox, QLineEdit {
    border: 1px solid #555;
    border-radius: 4px;
    padding: 4px;
    background-color: #ffffff;
    color: #000000;
    font-size: 13px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #000000;
    selection-background-color: #007acc;
}
"""


# ============================================================
# TOOL STATE
# ============================================================

class Tool(Enum):
    NONE = auto()
    ADD_TEXT = auto()
    EDIT_TEXT = auto()
    SIGN = auto()


# ============================================================
# SIGNATURE STORAGE
# ============================================================

class SignatureManager:
    """Owns the location and persistence of the user's saved signature."""

    def __init__(self) -> None:
        base_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )

        if not base_dir:
            base_dir = str(Path.home() / f".{APP_NAME.lower().replace(' ', '_')}")

        self.app_dir = Path(base_dir)
        self.app_dir.mkdir(parents=True, exist_ok=True)

        self.signature_path = self.app_dir / "saved_signature.png"

    def exists(self) -> bool:
        return self.signature_path.is_file()

    def load(self) -> bytes:
        if not self.exists():
            raise FileNotFoundError("No saved signature exists.")

        return self.signature_path.read_bytes()

    def save(self, data: bytes) -> None:
        temp_path = self.signature_path.with_suffix(".tmp")

        try:
            temp_path.write_bytes(data)
            os.replace(temp_path, self.signature_path)
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise


# ============================================================
# SIGNATURE DRAWING WIDGET
# ============================================================

class SignaturePad(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setFixedSize(400, 200)

        self.image = QImage(
            self.size(),
            QImage.Format.Format_ARGB32,
        )
        self.image.fill(Qt.GlobalColor.transparent)

        self.drawing = False
        self.last_point = QPoint()

        self.pen = QPen(
            QColor(25, 25, 112),
            3,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )

    def paintEvent(self, event) -> None:
        del event

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(
            self.rect(),
            Qt.GlobalColor.white,
        )

        painter.setPen(
            QPen(QColor("#cccccc"), 2)
        )
        painter.drawRect(
            0,
            0,
            self.width() - 1,
            self.height() - 1,
        )

        painter.drawImage(
            self.rect(),
            self.image,
            self.image.rect(),
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.last_point = event.position().toPoint()

    def mouseMoveEvent(self, event) -> None:
        if (
            self.drawing
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            current_point = event.position().toPoint()

            painter = QPainter(self.image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(self.pen)
            painter.drawLine(
                self.last_point,
                current_point,
            )
            painter.end()

            self.last_point = current_point
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = False

    def clear(self) -> None:
        self.image.fill(Qt.GlobalColor.transparent)
        self.update()

    def get_image_bytes(self) -> bytes:
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)

        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            raise RuntimeError("Could not create an in-memory signature buffer.")

        try:
            if not self.image.save(buffer, "PNG"):
                raise RuntimeError("Could not encode the signature as PNG.")
        finally:
            buffer.close()

        return bytes(byte_array)


# ============================================================
# SIGNATURE DIALOG
# ============================================================

class SignatureDialog(QDialog):
    def __init__(
        self,
        signature_manager: SignatureManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.signature_manager = signature_manager
        self.final_signature_bytes: Optional[bytes] = None

        self.setWindowTitle("Sign Document")

        layout = QVBoxLayout(self)

        if self.signature_manager.exists():
            self.load_btn = QPushButton("✅ Use Saved Signature")
            self.load_btn.setStyleSheet(
                "background-color: #27ae60; color: white; "
                "padding: 10px; font-size: 14px;"
            )
            self.load_btn.clicked.connect(self.use_saved_signature)
            layout.addWidget(self.load_btn)

            separator = QLabel("— OR DRAW A NEW ONE —")
            separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
            separator.setStyleSheet(
                "color: #888888; margin: 10px 0px;"
            )
            layout.addWidget(separator)

        header = QLabel("Draw your signature smoothly below:")
        header.setFont(
            QFont("Arial", 11, QFont.Weight.Bold)
        )
        layout.addWidget(header)

        self.pad = SignaturePad()
        layout.addWidget(self.pad)

        self.save_checkbox = QCheckBox(
            "Save this signature for future use"
        )
        layout.addWidget(self.save_checkbox)

        button_layout = QHBoxLayout()

        clear_btn = QPushButton("Clear Pad")
        clear_btn.setStyleSheet(
            "background-color: #e74c3c; color: white;"
        )
        clear_btn.clicked.connect(self.pad.clear)
        button_layout.addWidget(clear_btn)

        button_layout.addStretch()

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.process_new_signature)
        self.buttons.rejected.connect(self.reject)

        button_layout.addWidget(self.buttons)
        layout.addLayout(button_layout)

    def use_saved_signature(self) -> None:
        try:
            self.final_signature_bytes = self.signature_manager.load()
            self.accept()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Signature Error",
                f"Could not load the saved signature:\n{exc}",
            )

    def process_new_signature(self) -> None:
        try:
            signature_bytes = self.pad.get_image_bytes()

            if not signature_bytes:
                QMessageBox.information(
                    self,
                    "Empty Signature",
                    "Please draw a signature before accepting.",
                )
                return

            if self.save_checkbox.isChecked():
                self.signature_manager.save(signature_bytes)

            self.final_signature_bytes = signature_bytes
            self.accept()

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Signature Error",
                f"Could not save the signature:\n{exc}",
            )


# ============================================================
# FONT SELECTION / ADD TEXT DIALOG
# ============================================================

class AddTextDialog(QDialog):
    """Collects text formatting without coupling font storage to the main window."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Add Text")
        self.resize(420, 280)

        self.previous_font_index = 0

        layout = QVBoxLayout(self)

        format_layout = QHBoxLayout()

        format_layout.addWidget(QLabel("Font:"))

        self.font_combo = QComboBox()
        self.font_combo.addItem("Helvetica", "helv")
        self.font_combo.addItem("Times Roman", "tiro")
        self.font_combo.addItem("Courier", "cour")
        self.font_combo.addItem("📂 Select Custom Font...", None)

        self.font_combo.currentIndexChanged.connect(
            self.handle_font_selection
        )

        format_layout.addWidget(self.font_combo)

        format_layout.addWidget(QLabel("Size:"))

        self.font_spin = QSpinBox()
        self.font_spin.setRange(6, 144)
        self.font_spin.setValue(12)

        format_layout.addWidget(self.font_spin)
        layout.addLayout(format_layout)

        layout.addWidget(QLabel("Enter your text here:"))

        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        layout.addWidget(self.text_edit)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)

        layout.addWidget(self.buttons)

    def handle_font_selection(self, index: int) -> None:
        selected_text = self.font_combo.itemText(index)

        if selected_text != "📂 Select Custom Font...":
            self.previous_font_index = index
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Font File",
            "",
            "Font Files (*.ttf *.otf)",
        )

        if not file_path:
            self.font_combo.blockSignals(True)
            self.font_combo.setCurrentIndex(self.previous_font_index)
            self.font_combo.blockSignals(False)
            return

        path = Path(file_path)
        display_name = path.name

        # Avoid duplicate display labels in the same dialog.
        existing_names = {
            self.font_combo.itemText(i)
            for i in range(self.font_combo.count())
        }

        if display_name in existing_names:
            stem = path.stem
            suffix = path.suffix
            counter = 2

            while f"{stem} ({counter}){suffix}" in existing_names:
                counter += 1

            display_name = f"{stem} ({counter}){suffix}"

        insert_at = self.font_combo.count() - 1
        self.font_combo.insertItem(
            insert_at,
            display_name,
            file_path,
        )

        self.font_combo.setCurrentIndex(insert_at)
        self.previous_font_index = insert_at

    def validate_and_accept(self) -> None:
        if not self.text_edit.toPlainText().strip():
            QMessageBox.information(
                self,
                "No Text",
                "Please enter some text.",
            )
            return

        self.accept()

    def get_data(self) -> tuple[str, int, Optional[str], Optional[str]]:
        display_name = self.font_combo.currentText()
        data = self.font_combo.currentData()

        if isinstance(data, str) and data:
            # Built-in font code.
            return (
                self.text_edit.toPlainText(),
                self.font_spin.value(),
                data,
                None,
            )

        if display_name == "📂 Select Custom Font...":
            return (
                self.text_edit.toPlainText(),
                self.font_spin.value(),
                "helv",
                None,
            )

        # Custom font path is stored as item data.
        return (
            self.text_edit.toPlainText(),
            self.font_spin.value(),
            display_name,
            str(data) if data else None,
        )


# ============================================================
# PDF DOCUMENT CONTROLLER
# ============================================================

class PDFDocumentController:
    """
    Owns the PyMuPDF document and its history.

    The UI should not manipulate self.doc directly.
    """

    def __init__(self, max_undo_states: int = MAX_UNDO_STATES) -> None:
        self.doc: Optional[pymupdf.Document] = None
        self.file_path: Optional[Path] = None
        self.current_page = 0

        self.max_undo_states = max(1, max_undo_states)
        self.undo_stack: list[bytes] = []
        self.redo_stack: list[bytes] = []

        self._state_token: Optional[str] = None
        self._saved_token: Optional[str] = None

    @property
    def has_document(self) -> bool:
        return self.doc is not None

    @property
    def page_count(self) -> int:
        return len(self.doc) if self.doc else 0

    @property
    def is_modified(self) -> bool:
        return (
            self.doc is not None
            and self._state_token != self._saved_token
        )

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def _snapshot(self) -> bytes:
        if self.doc is None:
            raise RuntimeError("No PDF is open.")

        return self.doc.tobytes(
            garbage=4,
            deflate=True,
        )

    @staticmethod
    def _token(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _set_state_from_bytes(self, data: bytes) -> None:
        old_doc = self.doc

        new_doc = pymupdf.open(
            stream=data,
            filetype="pdf",
        )

        self.doc = new_doc

        if old_doc is not None:
            old_doc.close()

        self.current_page = min(
            self.current_page,
            max(0, len(new_doc) - 1),
        )

        self._state_token = self._token(data)

    def open(self, file_path: str) -> pymupdf.Document:
        path = Path(file_path)
        new_doc = pymupdf.open(str(path))

        # Keep the document open so callers can authenticate encrypted PDFs.
        if new_doc.needs_pass:
            if self.doc:
                self.doc.close()
            self.doc = new_doc
            self.file_path = path
            self.current_page = 0
            self.undo_stack.clear()
            self.redo_stack.clear()
            self._state_token = None
            self._saved_token = None
            return new_doc

        data = new_doc.tobytes()
        new_doc.close()

        self._set_state_from_bytes(data)

        self.file_path = path
        self.current_page = 0

        self.undo_stack.clear()
        self.redo_stack.clear()

        self._saved_token = self._state_token

        return self.doc

    def authenticate(self, password: str) -> bool:
        if self.doc is None or not self.doc.needs_pass:
            return True

        if self.doc.authenticate(password):
            data = self.doc.tobytes()

            self.doc.close()
            self.doc = pymupdf.open(
                stream=data,
                filetype="pdf",
            )

            self._state_token = self._token(data)
            self._saved_token = self._state_token

            return True

        return False

    def close(self) -> None:
        if self.doc is not None:
            self.doc.close()

        self.doc = None
        self.file_path = None
        self.current_page = 0

        self.undo_stack.clear()
        self.redo_stack.clear()
        self._state_token = None
        self._saved_token = None

    def mutate(self, operation: Callable[[], None]) -> None:
        """
        Run a document mutation and automatically create an undo point.
        On failure, the original document is restored.
        """
        if self.doc is None:
            raise RuntimeError("No PDF is open.")

        before = self._snapshot()

        try:
            operation()
            after = self._snapshot()

            if before == after:
                return

            self.undo_stack.append(before)

            if len(self.undo_stack) > self.max_undo_states:
                self.undo_stack.pop(0)

            self.redo_stack.clear()
            self._state_token = self._token(after)

        except Exception:
            self._set_state_from_bytes(before)
            raise

    def undo(self) -> bool:
        if not self.undo_stack or self.doc is None:
            return False

        current = self._snapshot()
        target = self.undo_stack.pop()

        self.redo_stack.append(current)
        self._set_state_from_bytes(target)

        return True

    def redo(self) -> bool:
        if not self.redo_stack or self.doc is None:
            return False

        current = self._snapshot()
        target = self.redo_stack.pop()

        self.undo_stack.append(current)
        self._set_state_from_bytes(target)

        return True

    def save_as(self, file_path: str) -> None:
        if self.doc is None:
            raise RuntimeError("No PDF is open.")

        destination = Path(file_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        temp_path = destination.with_suffix(
            destination.suffix + ".tmp"
        )

        current_page = self.current_page

        try:
            self.doc.save(
                str(temp_path),
                garbage=4,
                deflate=True,
            )

            self.doc.close()

            os.replace(temp_path, destination)

            self.doc = pymupdf.open(str(destination))
            self.current_page = min(
                current_page,
                max(0, len(self.doc) - 1),
            )

            data = self._snapshot()
            self._state_token = self._token(data)
            self._saved_token = self._state_token
            self.file_path = destination

            self.undo_stack.clear()
            self.redo_stack.clear()

        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

            # Re-open the original file if we closed the current document.
            if self.doc is None and self.file_path and self.file_path.exists():
                try:
                    self.doc = pymupdf.open(str(self.file_path))
                    self.current_page = min(
                        current_page,
                        max(0, len(self.doc) - 1),
                    )
                except Exception:
                    pass

            raise

    def save(self) -> None:
        if self.file_path is None:
            raise RuntimeError("No destination path is associated with this PDF.")

        self.save_as(str(self.file_path))

    def page(self) -> pymupdf.Page:
        if self.doc is None:
            raise RuntimeError("No PDF is open.")

        return self.doc[self.current_page]


# ============================================================
# PDF RENDERER
# ============================================================

class PDFRenderer:
    """Renders pages and owns the PDF-point <-> screen-pixel mapping."""

    def __init__(self, zoom: float = 1.25) -> None:
        self.zoom = zoom

    def render(self, page: pymupdf.Page) -> QPixmap:
        matrix = pymupdf.Matrix(
            self.zoom,
            self.zoom,
        )

        pix = page.get_pixmap(
            matrix=matrix,
            alpha=False,
        )

        qimage = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format.Format_RGB888,
        ).copy()

        return QPixmap.fromImage(qimage)

    def screen_to_pdf(
        self,
        x: float,
        y: float,
    ) -> pymupdf.Point:
        return pymupdf.Point(
            x / self.zoom,
            y / self.zoom,
        )

    def pdf_to_screen(
        self,
        x: float,
        y: float,
    ) -> QPoint:
        return QPoint(
            round(x * self.zoom),
            round(y * self.zoom),
        )


# ============================================================
# PDF EDITING SERVICE
# ============================================================

class PDFEditingService:
    """Contains PDF-specific operations used by the UI."""

    BUILTIN_FONT_MAP = {
        "Helvetica": "helv",
        "Times Roman": "tiro",
        "Courier": "cour",
    }

    @staticmethod
    def _font_name_from_file(font_path: str) -> str:
        """
        Create a stable, low-collision PDF internal font name.
        The actual font file is still embedded in the PDF.
        """
        data = Path(font_path).read_bytes()
        digest = hashlib.sha1(data).hexdigest()[:10]
        return f"F_{digest}"

    @classmethod
    def insert_text(
        cls,
        page: pymupdf.Page,
        point: pymupdf.Point,
        text: str,
        font_size: int,
        font_choice: str,
        custom_font_path: Optional[str] = None,
    ) -> None:
        if custom_font_path:
            internal_name = cls._font_name_from_file(custom_font_path)

            page.insert_text(
                point,
                text,
                fontsize=font_size,
                fontname=internal_name,
                fontfile=custom_font_path,
                color=(0, 0, 0),
            )
            return

        font_name = cls.BUILTIN_FONT_MAP.get(
            font_choice,
            "helv",
        )

        page.insert_text(
            point,
            text,
            fontsize=font_size,
            fontname=font_name,
            color=(0, 0, 0),
        )

    @staticmethod
    def find_clicked_span(
        page: pymupdf.Page,
        point: pymupdf.Point,
        tolerance: float = 2.0,
    ) -> Optional[dict]:
        """
        Find a text span rather than merely a word, so we have
        access to font size/color and more reliable layout information.
        """
        page_dict = page.get_text("dict")

        best_span: Optional[dict] = None
        best_distance = float("inf")

        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    bbox = span.get("bbox")
                    if not bbox:
                        continue

                    rect = pymupdf.Rect(bbox)

                    expanded = pymupdf.Rect(
                        rect.x0 - tolerance,
                        rect.y0 - tolerance,
                        rect.x1 + tolerance,
                        rect.y1 + tolerance,
                    )

                    if not expanded.contains(point):
                        continue

                    # Prefer the span whose center is closest to the click.
                    center = pymupdf.Point(
                        (rect.x0 + rect.x1) / 2,
                        (rect.y0 + rect.y1) / 2,
                    )

                    distance = (
                        (center.x - point.x) ** 2
                        + (center.y - point.y) ** 2
                    )

                    if distance < best_distance:
                        best_distance = distance
                        best_span = span

        return best_span

    @staticmethod
    def replace_text(
        page: pymupdf.Page,
        span: dict,
        new_text: str,
    ) -> None:
        bbox = span.get("bbox")
        if not bbox:
            raise ValueError("The selected text has no bounding box.")

        rect = pymupdf.Rect(bbox)

        font_size = float(span.get("size", max(6, rect.height * 0.75)))

        # Reinsert using the original text color when available.
        color_value = span.get("color", 0)

        # PyMuPDF's text color is commonly represented as packed RGB.
        red = ((color_value >> 16) & 255) / 255.0
        green = ((color_value >> 8) & 255) / 255.0
        blue = (color_value & 255) / 255.0

        page.add_redact_annot(
            rect,
            fill=(1, 1, 1),
        )
        page.apply_redactions()

        baseline = rect.y1 - (rect.height * 0.20)

        page.insert_text(
            pymupdf.Point(rect.x0, baseline),
            new_text,
            fontsize=font_size,
            color=(red, green, blue),
        )

    @staticmethod
    def insert_signature(
        page: pymupdf.Page,
        point: pymupdf.Point,
        signature_bytes: bytes,
        width: float = 150,
        height: float = 75,
    ) -> None:
        # Preserve the original behavior where the click is the lower-right anchor.
        rect = pymupdf.Rect(
            point.x,
            point.y - height,
            point.x + width,
            point.y,
        )

        page.insert_image(
            rect,
            stream=signature_bytes,
        )


# ============================================================
# PDF VIEW
# ============================================================

class PDFView(QLabel):
    """Display widget that reports page-space clicks to the editor."""

    def __init__(
        self,
        click_handler: Callable[[float, float], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.click_handler = click_handler

        self.setStyleSheet("background-color: white;")
        self.setScaledContents(False)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.click_handler(
                event.position().x(),
                event.position().y(),
            )


# ============================================================
# MAIN WINDOW
# ============================================================

class PDFEditor(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, 1000, 800)

        self.controller = PDFDocumentController()
        self.renderer = PDFRenderer(zoom=1.25)
        self.signature_manager = SignatureManager()

        self.active_tool = Tool.NONE

        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.image_label = PDFView(
            self.handle_page_click,
            self,
        )

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 5)
        self.image_label.setGraphicsEffect(shadow)

        self.scroll_area.setWidget(self.image_label)
        self.setCentralWidget(self.scroll_area)

        self._build_toolbar()
        self._build_status_bar()
        self._update_ui()

    # --------------------------------------------------------
    # UI construction
    # --------------------------------------------------------

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.open_action = QAction("📂 Open PDF", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_pdf)
        toolbar.addAction(self.open_action)

        toolbar.addSeparator()

        self.prev_action = QAction("◀ Prev", self)
        self.prev_action.triggered.connect(self.prev_page)
        toolbar.addAction(self.prev_action)

        self.page_label = QLabel(" Page 0 / 0 ")
        self.page_label.setStyleSheet(
            "color: white; font-weight: bold; margin: 0 10px;"
        )
        toolbar.addWidget(self.page_label)

        self.next_action = QAction("Next ▶", self)
        self.next_action.triggered.connect(self.next_page)
        toolbar.addAction(self.next_action)

        toolbar.addSeparator()

        self.text_action = QAction("📝 Add Text", self)
        self.text_action.setCheckable(True)
        self.text_action.triggered.connect(
            lambda checked: self.set_tool(
                Tool.ADD_TEXT if checked else Tool.NONE
            )
        )
        toolbar.addAction(self.text_action)

        self.edit_action = QAction("✏️ Edit Text", self)
        self.edit_action.setCheckable(True)
        self.edit_action.triggered.connect(
            lambda checked: self.set_tool(
                Tool.EDIT_TEXT if checked else Tool.NONE
            )
        )
        toolbar.addAction(self.edit_action)

        self.sign_action = QAction("✍️ Sign", self)
        self.sign_action.setCheckable(True)
        self.sign_action.triggered.connect(
            lambda checked: self.set_tool(
                Tool.SIGN if checked else Tool.NONE
            )
        )
        toolbar.addAction(self.sign_action)

        toolbar.addSeparator()

        self.undo_action = QAction("↶ Undo", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.undo)
        toolbar.addAction(self.undo_action)

        self.redo_action = QAction("↷ Redo", self)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.triggered.connect(self.redo)
        toolbar.addAction(self.redo_action)

        toolbar.addSeparator()

        zoom_out_action = QAction("−", self)
        zoom_out_action.triggered.connect(
            lambda: self.set_zoom(
                max(0.50, self.renderer.zoom - 0.10)
            )
        )
        toolbar.addAction(zoom_out_action)

        self.zoom_label = QLabel(" 125% ")
        self.zoom_label.setStyleSheet(
            "color: white; font-weight: bold;"
        )
        toolbar.addWidget(self.zoom_label)

        zoom_in_action = QAction("+", self)
        zoom_in_action.triggered.connect(
            lambda: self.set_zoom(
                min(3.00, self.renderer.zoom + 0.10)
            )
        )
        toolbar.addAction(zoom_in_action)

        empty_spacer = QWidget()
        empty_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        toolbar.addWidget(empty_spacer)

        self.save_action = QAction("💾 Save", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_pdf)
        toolbar.addAction(self.save_action)

        self.save_as_action = QAction("💾 Save As", self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(self.save_pdf_as)
        toolbar.addAction(self.save_as_action)

    def _build_status_bar(self) -> None:
        self.status_label = QLabel("No PDF open")
        self.statusBar().addWidget(self.status_label)

    # --------------------------------------------------------
    # State/UI helpers
    # --------------------------------------------------------

    def set_tool(self, tool: Tool) -> None:
        self.active_tool = tool

        self.text_action.blockSignals(True)
        self.edit_action.blockSignals(True)
        self.sign_action.blockSignals(True)

        self.text_action.setChecked(tool == Tool.ADD_TEXT)
        self.edit_action.setChecked(tool == Tool.EDIT_TEXT)
        self.sign_action.setChecked(tool == Tool.SIGN)

        self.text_action.blockSignals(False)
        self.edit_action.blockSignals(False)
        self.sign_action.blockSignals(False)

        cursor = Qt.CursorShape.ArrowCursor

        if tool == Tool.ADD_TEXT:
            cursor = Qt.CursorShape.IBeamCursor
        elif tool == Tool.EDIT_TEXT:
            cursor = Qt.CursorShape.CrossCursor
        elif tool == Tool.SIGN:
            cursor = Qt.CursorShape.PointingHandCursor

        self.image_label.setCursor(cursor)

    def _update_ui(self) -> None:
        count = self.controller.page_count
        current = (
            self.controller.current_page + 1
            if count
            else 0
        )

        self.page_label.setText(
            f" Page {current} / {count} "
        )

        self.prev_action.setEnabled(
            self.controller.has_document
            and self.controller.current_page > 0
        )
        self.next_action.setEnabled(
            self.controller.has_document
            and self.controller.current_page < count - 1
        )

        self.undo_action.setEnabled(
            self.controller.can_undo
        )
        self.redo_action.setEnabled(
            self.controller.can_redo
        )

        self.save_action.setEnabled(
            self.controller.has_document
            and self.controller.is_modified
        )
        self.save_as_action.setEnabled(
            self.controller.has_document
        )

        if self.controller.has_document:
            filename = (
                self.controller.file_path.name
                if self.controller.file_path
                else "Untitled"
            )

            marker = "*" if self.controller.is_modified else ""

            self.setWindowTitle(
                f"{APP_NAME} — {filename}{marker}"
            )

            self.status_label.setText(
                f"Page {current} of {count}"
            )
        else:
            self.setWindowTitle(APP_NAME)
            self.status_label.setText("No PDF open")

        self.zoom_label.setText(
            f" {round(self.renderer.zoom * 100)}% "
        )

    def _show_error(
        self,
        title: str,
        message: str,
    ) -> None:
        QMessageBox.critical(
            self,
            title,
            message,
        )

    # --------------------------------------------------------
    # Rendering/navigation
    # --------------------------------------------------------

    def show_page(self) -> None:
        if not self.controller.has_document:
            self.image_label.clear()
            self.image_label.resize(1, 1)
            self._update_ui()
            return

        try:
            page = self.controller.page()
            pixmap = self.renderer.render(page)

            self.image_label.setPixmap(pixmap)
            self.image_label.resize(
                pixmap.size()
            )
            self.image_label.setMinimumSize(
                pixmap.size()
            )

            self._update_ui()

        except Exception as exc:
            self._show_error(
                "Render Error",
                f"Could not render the page:\n{exc}",
            )

    def set_zoom(self, zoom: float) -> None:
        self.renderer.zoom = zoom
        self.show_page()

    def prev_page(self) -> None:
        if (
            self.controller.has_document
            and self.controller.current_page > 0
        ):
            self.controller.current_page -= 1
            self.set_tool(Tool.NONE)
            self.show_page()

    def next_page(self) -> None:
        if (
            self.controller.has_document
            and self.controller.current_page
            < self.controller.page_count - 1
        ):
            self.controller.current_page += 1
            self.set_tool(Tool.NONE)
            self.show_page()

    # --------------------------------------------------------
    # File management
    # --------------------------------------------------------

    def _maybe_save(self) -> bool:
        if not self.controller.is_modified:
            return True

        answer = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Save changes before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

        if answer == QMessageBox.StandardButton.Cancel:
            return False

        if answer == QMessageBox.StandardButton.Discard:
            return True

        return self.save_pdf()

    def open_pdf(self) -> None:
        if not self._maybe_save():
            return

        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF",
            "",
            "PDF Files (*.pdf)",
        )

        if not file_name:
            return

        try:
            doc = self.controller.open(file_name)

            if doc.needs_pass:
                password, ok = QInputDialog.getText(
                    self,
                    "Password Required",
                    "Enter the PDF password:",
                )

                if not ok:
                    self.controller.close()
                    self.show_page()
                    return

                if not self.controller.authenticate(password):
                    QMessageBox.warning(
                        self,
                        "Incorrect Password",
                        "The PDF password was incorrect.",
                    )
                    self.controller.close()
                    self.show_page()
                    return

            self.set_tool(Tool.NONE)
            self.show_page()

        except Exception as exc:
            self._show_error(
                "Open Error",
                f"Could not open the PDF:\n{exc}",
            )

    def save_pdf(self) -> bool:
        if not self.controller.has_document:
            return False

        try:
            if self.controller.file_path is None:
                return self.save_pdf_as()

            self.controller.save()
            self._update_ui()

            self.status_label.setText(
                f"Saved: {self.controller.file_path.name}"
            )
            return True

        except Exception as exc:
            self._show_error(
                "Save Error",
                f"Could not save the PDF:\n{exc}",
            )
            return False

    def save_pdf_as(self) -> bool:
        if not self.controller.has_document:
            return False

        suggested_name = (
            self.controller.file_path.name
            if self.controller.file_path
            else "document.pdf"
        )

        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF As",
            suggested_name,
            "PDF Files (*.pdf)",
        )

        if not file_name:
            return False

        if not file_name.lower().endswith(".pdf"):
            file_name += ".pdf"

        try:
            self.controller.save_as(file_name)
            self._update_ui()

            self.status_label.setText(
                f"Saved: {Path(file_name).name}"
            )
            return True

        except Exception as exc:
            self._show_error(
                "Save Error",
                f"Could not save the PDF:\n{exc}",
            )
            return False

    # --------------------------------------------------------
    # Undo/redo
    # --------------------------------------------------------

    def undo(self) -> None:
        if self.controller.undo():
            self.set_tool(Tool.NONE)
            self.show_page()

    def redo(self) -> None:
        if self.controller.redo():
            self.set_tool(Tool.NONE)
            self.show_page()

    # --------------------------------------------------------
    # Page click handling
    # --------------------------------------------------------

    def handle_page_click(
        self,
        screen_x: float,
        screen_y: float,
    ) -> None:
        if not self.controller.has_document:
            return

        pdf_point = self.renderer.screen_to_pdf(
            screen_x,
            screen_y,
        )

        try:
            if self.active_tool == Tool.ADD_TEXT:
                self._handle_add_text(pdf_point)
            elif self.active_tool == Tool.EDIT_TEXT:
                self._handle_edit_text(pdf_point)
            elif self.active_tool == Tool.SIGN:
                self._handle_signature(pdf_point)

        except Exception as exc:
            self._show_error(
                "Edit Error",
                f"The operation could not be completed:\n{exc}",
            )
        finally:
            self.set_tool(Tool.NONE)

    def _handle_add_text(
        self,
        pdf_point: pymupdf.Point,
    ) -> None:
        dialog = AddTextDialog(self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        text, font_size, font_choice, custom_path = dialog.get_data()

        if not text.strip():
            return

        insertion_point = pymupdf.Point(
            pdf_point.x,
            pdf_point.y + font_size,
        )

        def operation() -> None:
            page = self.controller.page()

            PDFEditingService.insert_text(
                page=page,
                point=insertion_point,
                text=text,
                font_size=font_size,
                font_choice=font_choice,
                custom_font_path=custom_path,
            )

        self.controller.mutate(operation)
        self.show_page()

    def _handle_edit_text(
        self,
        pdf_point: pymupdf.Point,
    ) -> None:
        page = self.controller.page()

        span = PDFEditingService.find_clicked_span(
            page,
            pdf_point,
        )

        if span is None:
            QMessageBox.information(
                self,
                "No Text Found",
                "You didn't click on editable text.",
            )
            return

        old_text = span.get("text", "")

        input_dialog = QInputDialog(self)
        input_dialog.setStyleSheet(MODERN_STYLE)
        input_dialog.setWindowTitle("Edit Text")
        input_dialog.setLabelText("Edit text:")
        input_dialog.setTextValue(old_text)

        if input_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_text = input_dialog.textValue()

        if not new_text:
            return

        # Use the span information captured before the mutation.
        def operation() -> None:
            PDFEditingService.replace_text(
                self.controller.page(),
                span,
                new_text,
            )

        self.controller.mutate(operation)
        self.show_page()

    def _handle_signature(
        self,
        pdf_point: pymupdf.Point,
    ) -> None:
        dialog = SignatureDialog(
            self.signature_manager,
            self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        signature_bytes = dialog.final_signature_bytes

        if not signature_bytes:
            return

        def operation() -> None:
            PDFEditingService.insert_signature(
                self.controller.page(),
                pdf_point,
                signature_bytes,
            )

        self.controller.mutate(operation)
        self.show_page()

    # --------------------------------------------------------
    # Window lifecycle
    # --------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._maybe_save():
            self.controller.close()
            event.accept()
        else:
            event.ignore()


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(MODERN_STYLE)

    window = PDFEditor()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
