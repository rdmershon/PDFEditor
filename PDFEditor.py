import sys
import os
import tempfile
import pymupdf
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QScrollArea, 
                             QFileDialog, QToolBar, QInputDialog, QDialog, 
                             QVBoxLayout, QPushButton, QTabWidget,
                             QWidget, QLineEdit, QGraphicsDropShadowEffect,
                             QSpacerItem, QSizePolicy)
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QFont, QColor, QKeySequence
from PyQt6.QtCore import Qt

# ==========================================
# MODERN STYLESHEET (QSS)
# ==========================================
MODERN_STYLE = """
/* Main Window & Dialogs */
QMainWindow, QDialog {
    background-color: #f0f2f5;
    color: #333333;
}

QScrollArea {
    background-color: #323639;
    border: none;
}

QToolBar {
    background-color: #ffffff;
    border-bottom: 1px solid #dcdcdc;
    padding: 6px;
    spacing: 8px;
}
QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 12px;
    color: #333333;
    font-size: 13px;
}
QToolButton:hover {
    background-color: #f0f2f5;
    border: 1px solid #d0d0d0;
}
QToolButton:pressed {
    background-color: #e4e6e9;
}
QToolButton:checked {
    background-color: #e7f3ff;
    border: 1px solid #1877f2;
    color: #1877f2;
    font-weight: bold;
}
QToolButton:disabled {
    color: #b0b0b0;
    background-color: transparent;
    border: 1px solid transparent;
}
QToolBar::separator {
    background-color: #dcdcdc;
    width: 1px;
    margin: 4px 8px;
}

QTabWidget::pane {
    border: 1px solid #ccd0d5;
    background: #ffffff;
    border-radius: 6px;
    margin-top: -1px;
}
QTabBar::tab {
    background: #e4e6e9;
    color: #606770;
    padding: 8px 24px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-size: 13px;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #1877f2;
    border: 1px solid #ccd0d5;
    border-bottom-color: #ffffff;
    font-weight: bold;
}

QLineEdit {
    border: 1px solid #ccd0d5;
    border-radius: 6px;
    padding: 10px;
    font-size: 14px;
    background: #ffffff;
    color: #333333;
    selection-background-color: #1877f2;
    selection-color: #ffffff;
}
QLineEdit:focus {
    border: 1px solid #1877f2;
}

QPushButton {
    background-color: #ffffff;
    border: 1px solid #ccd0d5;
    border-radius: 6px;
    padding: 8px 16px;
    color: #4b4f56;
    font-size: 13px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #f5f6f7;
}
QPushButton#primaryBtn {
    background-color: #1877f2;
    color: #ffffff;
    border: none;
}
QPushButton#primaryBtn:hover {
    background-color: #166fe5;
}
"""

# ==========================================
# CUSTOM WIDGETS
# ==========================================

class DraggableSignature(QLabel):
    """A floating, draggable label that represents a signature before it's saved to the PDF."""
    def __init__(self, parent, file_path, pdf_x, pdf_y, editor):
        super().__init__(parent)
        self.editor = editor
        self.file_path = file_path
        
        # Center coordinates relative to the original unscaled PDF dimensions
        self.pdf_x = pdf_x
        self.pdf_y = pdf_y
        
        self.original_pixmap = QPixmap(file_path)
        
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Drag to move\nDouble-Click to Apply\nRight-Click to Cancel")
        
        # Visual feedback so the user knows it's a floating object
        self.setStyleSheet("border: 2px dashed #1877f2; background-color: rgba(24, 119, 242, 20);")
        
        self.drag_start_pos = None
        self.show()
        self.update_zoom(self.editor.zoom_factor)

    def update_zoom(self, zoom):
        """Resizes and repositions the widget when the document is zoomed in/out."""
        new_w = int(120 * zoom)
        new_h = int(60 * zoom)
        self.setFixedSize(new_w, new_h)
        
        scaled_pixmap = self.original_pixmap.scaled(
            new_w, new_h, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled_pixmap)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        new_x = int((self.pdf_x * zoom) - (new_w / 2))
        new_y = int((self.pdf_y * zoom) - (new_h / 2))
        self.move(new_x, new_y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.drag_start_pos = event.pos()
        elif event.button() == Qt.MouseButton.RightButton:
            # Right-click cancels the signature
            if self in self.editor.floating_signatures:
                self.editor.floating_signatures.remove(self)
            self.deleteLater()

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is not None:
            # Move the widget visually
            delta = event.pos() - self.drag_start_pos
            self.move(self.pos() + delta)
            
            # Update the underlying PDF coordinates so it stays in place if zoomed
            self.pdf_x = (self.x() + self.width() / 2) / self.editor.zoom_factor
            self.pdf_y = (self.y() + self.height() / 2) / self.editor.zoom_factor

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.drag_start_pos = None

    def mouseDoubleClickEvent(self, event):
        """Double clicking a floating signature permanently applies it."""
        self.editor.commit_single_signature(self)


class DrawCanvas(QLabel):
    def __init__(self):
        super().__init__()
        self.canvas = QPixmap(380, 180)
        self.canvas.fill(Qt.GlobalColor.transparent)
        self.setPixmap(self.canvas)
        self.setStyleSheet("background-color: #fafafa; border: 2px dashed #bbbbbb; border-radius: 8px;")
        self.last_point = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_point = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.last_point:
            painter = QPainter(self.canvas)
            pen = QPen(QColor(0, 0, 139), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            painter.drawLine(self.last_point, event.pos())
            painter.end()
            self.last_point = event.pos()
            self.setPixmap(self.canvas)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_point = None
            
    def clear_canvas(self):
        self.canvas.fill(Qt.GlobalColor.transparent)
        self.setPixmap(self.canvas)


class SignaturePad(QDialog):
    def __init__(self, parent_editor=None):
        super().__init__(parent_editor)
        self.editor = parent_editor
        self.setWindowTitle("Create Signature")
        self.setFixedSize(450, 360) 
        
        self.signature_file_path = None
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        self.tabs = QTabWidget()
        
        self.tab_draw = QWidget()
        draw_layout = QVBoxLayout()
        draw_layout.setSpacing(10)
        
        self.draw_canvas = DrawCanvas()
        draw_layout.addWidget(self.draw_canvas)
        
        clear_btn = QPushButton("🗑 Clear Canvas")
        clear_btn.clicked.connect(self.draw_canvas.clear_canvas)
        draw_layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.tab_draw.setLayout(draw_layout)
        
        self.tab_type = QWidget()
        type_layout = QVBoxLayout()
        type_layout.setSpacing(10)
        
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Type your name here...")
        self.text_input.textChanged.connect(self.update_type_canvas) 
        type_layout.addWidget(self.text_input)
        
        self.type_label = QLabel()
        self.type_label.setStyleSheet("background-color: #fafafa; border: 2px dashed #bbbbbb; border-radius: 8px;")
        self.type_canvas = QPixmap(380, 180)
        self.type_canvas.fill(Qt.GlobalColor.transparent)
        self.type_label.setPixmap(self.type_canvas)
        type_layout.addWidget(self.type_label)
        
        self.tab_type.setLayout(type_layout)
        
        self.tabs.addTab(self.tab_draw, "✍ Draw")
        self.tabs.addTab(self.tab_type, "⌨ Type")
        layout.addWidget(self.tabs)
        
        save_btn = QPushButton("Save Signature")
        save_btn.setObjectName("primaryBtn") 
        save_btn.setFixedHeight(40)
        save_btn.clicked.connect(self.save_signature)
        layout.addWidget(save_btn)
        
        self.setLayout(layout)

    def update_type_canvas(self, text):
        self.type_canvas.fill(Qt.GlobalColor.transparent)
        if text:
            painter = QPainter(self.type_canvas)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            
            font = QFont("Brush Script MT", 42, QFont.Weight.Normal)
            font.setItalic(True)
            font.setStyleHint(QFont.StyleHint.Cursive) 
            
            painter.setFont(font)
            painter.setPen(QColor(0, 0, 139))
            
            painter.drawText(self.type_canvas.rect(), Qt.AlignmentFlag.AlignCenter, text)
            painter.end()
            
        self.type_label.setPixmap(self.type_canvas)

    def save_signature(self):
        # Create a guaranteed unique temporary file for EVERY signature so they don't overwrite each other
        fd, self.signature_file_path = tempfile.mkstemp(suffix=".png")
        os.close(fd) # Close file descriptor, we just need the path
        
        if self.tabs.currentIndex() == 0:
            self.draw_canvas.canvas.save(self.signature_file_path, "PNG")
        else:
            self.type_canvas.save(self.signature_file_path, "PNG")
            
        # Register the file with the main editor so it can be deleted on exit
        if self.editor:
            self.editor.temp_files.append(self.signature_file_path)
            
        self.accept()


class PDFLabel(QLabel):
    def __init__(self, parent_editor):
        super().__init__()
        self.editor = parent_editor
        self.setStyleSheet("background-color: white;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.editor.text_tool_active or self.editor.signature_tool_active:
                self.editor.handle_click(event.pos().x(), event.pos().y())


# ==========================================
# MAIN APPLICATION
# ==========================================

class PDFEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pro Python PDF Editor")
        self.setGeometry(100, 100, 900, 1000)
        
        # State variables
        self.doc = None
        self.current_page = 0
        self.zoom_factor = 1.0 
        self.text_tool_active = False
        self.signature_tool_active = False
        self.signature_file_path = None
        
        self.floating_signatures = [] # Tracks currently dragged signatures
        self.temp_files = [] # Tracks all created temp image files for cleanup
        
        # UNDO State Variables
        self.undo_stack = []
        self.MAX_UNDO_STEPS = 5
        
        # UI Setup
        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.image_label = PDFLabel(self) 
        self.scroll_area.setWidget(self.image_label)
        self.setCentralWidget(self.scroll_area)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 4)
        self.image_label.setGraphicsEffect(shadow)
        self.image_label.hide() 
        
        # Toolbar Setup
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        open_action = toolbar.addAction("📂 Open")
        open_action.triggered.connect(self.open_pdf)
        toolbar.addSeparator()
        
        prev_action = toolbar.addAction("⬅ Previous")
        prev_action.triggered.connect(self.prev_page)
        
        next_action = toolbar.addAction("Next ➡")
        next_action.triggered.connect(self.next_page)
        toolbar.addSeparator()
        
        zoom_in_action = toolbar.addAction("🔍 In")
        zoom_in_action.triggered.connect(self.zoom_in)
        
        zoom_out_action = toolbar.addAction("🔎 Out")
        zoom_out_action.triggered.connect(self.zoom_out)
        toolbar.addSeparator()

        self.undo_action = toolbar.addAction("↩ Undo")
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo) 
        self.undo_action.triggered.connect(self.undo)
        self.undo_action.setEnabled(False) 
        toolbar.addSeparator()
        
        self.text_action = toolbar.addAction("📝 Text")
        self.text_action.setCheckable(True) 
        self.text_action.triggered.connect(self.toggle_text_tool)
        
        self.sign_action = toolbar.addAction("✍ Sign")
        self.sign_action.setCheckable(True)
        self.sign_action.triggered.connect(self.toggle_signature_tool)
        toolbar.addSeparator()
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        
        save_action = toolbar.addAction("💾 Save As")
        save_action.triggered.connect(self.save_pdf)
        
    def open_pdf(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_name:
            self.clear_floating_signatures() # Erase any unsaved floats from previous doc
            self.doc = pymupdf.open(file_name)
            self.current_page = 0
            self.zoom_factor = 1.0 
            
            self.undo_stack.clear()
            self.undo_action.setEnabled(False)
            
            self.image_label.show()
            self.show_page()
            
    def show_page(self):
        if self.doc:
            page = self.doc[self.current_page]
            
            mat = pymupdf.Matrix(self.zoom_factor, self.zoom_factor)
            pix = page.get_pixmap(matrix=mat)
            
            qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)
            self.image_label.setPixmap(pixmap)
            self.image_label.resize(pixmap.width(), pixmap.height())
            
            # Ensure any floating signatures update their scaling to match the document
            for sig in self.floating_signatures:
                sig.update_zoom(self.zoom_factor)
                sig.raise_() # Make sure they sit on top of the PDF

    def prev_page(self):
        if self.doc and self.current_page > 0:
            self.apply_all_floating_signatures() # Auto-commit before page turn
            self.current_page -= 1
            self.show_page()

    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
            self.apply_all_floating_signatures() # Auto-commit before page turn
            self.current_page += 1
            self.show_page()
            
    def zoom_in(self):
        if self.doc:
            self.zoom_factor *= 1.2 
            self.show_page()

    def zoom_out(self):
        if self.doc:
            self.zoom_factor /= 1.2
            self.show_page()
    
    def toggle_text_tool(self, checked):
        if checked and self.signature_tool_active:
            self.sign_action.setChecked(False)
            self.signature_tool_active = False
            
        self.text_tool_active = checked
        if checked:
            self.image_label.setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    def toggle_signature_tool(self, checked):
        if checked and self.text_tool_active:
            self.text_action.setChecked(False)
            self.text_tool_active = False
            
        self.signature_tool_active = checked
        if checked:
            if not self.signature_file_path:
                dialog = SignaturePad(self)
                if dialog.exec() == QDialog.DialogCode.Accepted and dialog.signature_file_path:
                    self.signature_file_path = dialog.signature_file_path
                    self.image_label.setCursor(Qt.CursorShape.CrossCursor)
                else:
                    self.sign_action.setChecked(False)
                    self.signature_tool_active = False
            else:
                self.image_label.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    def save_state_for_undo(self):
        if self.doc:
            current_state = self.doc.tobytes()
            self.undo_stack.append(current_state)
            
            if len(self.undo_stack) > self.MAX_UNDO_STEPS:
                self.undo_stack.pop(0)
                
            self.undo_action.setEnabled(True)

    def undo(self):
        if self.undo_stack:
            last_state = self.undo_stack.pop()
            
            if self.doc:
                self.doc.close()
                
            self.doc = pymupdf.open(stream=last_state, filetype="pdf")
            self.show_page()
            
            if not self.undo_stack:
                self.undo_action.setEnabled(False)

    def commit_single_signature(self, sig_widget):
        """Burns a single floating signature into the PDF."""
        self.save_state_for_undo()
        page = self.doc[self.current_page]
        
        # Calculate bounding box
        rect = pymupdf.Rect(sig_widget.pdf_x - 60, sig_widget.pdf_y - 30, 
                            sig_widget.pdf_x + 60, sig_widget.pdf_y + 30)
                            
        page.insert_image(rect, filename=sig_widget.file_path)
        
        # Clean up widget
        if sig_widget in self.floating_signatures:
            self.floating_signatures.remove(sig_widget)
        sig_widget.deleteLater()
        
        self.show_page()

    def apply_all_floating_signatures(self):
        """Burns ALL active floating signatures into the PDF."""
        if not self.floating_signatures:
            return
            
        self.save_state_for_undo()
        page = self.doc[self.current_page]
        
        for sig_widget in self.floating_signatures:
            rect = pymupdf.Rect(sig_widget.pdf_x - 60, sig_widget.pdf_y - 30, 
                                sig_widget.pdf_x + 60, sig_widget.pdf_y + 30)
            page.insert_image(rect, filename=sig_widget.file_path)
            sig_widget.deleteLater()
            
        self.floating_signatures.clear()
        # We purposely don't call show_page() here because the function calling this (like zoom/page turn) will do it.

    def clear_floating_signatures(self):
        """Deletes floats without saving them (used when opening a brand new PDF)."""
        for sig in self.floating_signatures:
            sig.deleteLater()
        self.floating_signatures.clear()

    def handle_click(self, x, y):
        if not self.doc:
            return

        page = self.doc[self.current_page]
        pdf_x = x / self.zoom_factor
        pdf_y = y / self.zoom_factor

        if self.text_tool_active:
            text, ok = QInputDialog.getText(self, "Input Text", "Enter text to insert:")
            if ok and text:
                self.save_state_for_undo()
                page.insert_text(pymupdf.Point(pdf_x, pdf_y), text, fontsize=12, color=(0, 0, 0))
                self.show_page()
                self.text_action.setChecked(False)
                self.toggle_text_tool(False)
                
        elif self.signature_tool_active and self.signature_file_path:
            # Spawn a draggable widget instead of burning it immediately
            sig_widget = DraggableSignature(self.image_label, self.signature_file_path, pdf_x, pdf_y, self)
            self.floating_signatures.append(sig_widget)
            
            # Deactivate tool immediately so user can safely click and drag the new element
            self.sign_action.setChecked(False)
            self.signature_tool_active = False
            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    def save_pdf(self):
        if self.doc:
            self.apply_all_floating_signatures() # Burn everything before saving!
            self.show_page() # Refresh visual
            
            file_name, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
            if file_name:
                self.doc.save(file_name)

    def closeEvent(self, event):
        """Clean up all temporary signature files that were generated during the session."""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except OSError:
                pass
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    app.setStyleSheet(MODERN_STYLE)
    window = PDFEditor()
    window.show()
    sys.exit(app.exec())
