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

/* Scroll Area (The background behind the PDF) */
QScrollArea {
    background-color: #323639; /* Dark gray for modern document viewers */
    border: none;
}

/* Toolbar styling */
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

/* Tabs inside Dialogs */
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

/* Inputs */
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

/* Buttons */
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Signature")
        self.setFixedSize(450, 360) 
        
        self.signature_file_path = None
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        self.tabs = QTabWidget()
        
        # --- TAB 1: DRAW ---
        self.tab_draw = QWidget()
        draw_layout = QVBoxLayout()
        draw_layout.setSpacing(10)
        
        self.draw_canvas = DrawCanvas()
        draw_layout.addWidget(self.draw_canvas)
        
        clear_btn = QPushButton("🗑 Clear Canvas")
        clear_btn.clicked.connect(self.draw_canvas.clear_canvas)
        draw_layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.tab_draw.setLayout(draw_layout)
        
        # --- TAB 2: TYPE ---
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
        
        # --- Add Tabs to Layout ---
        self.tabs.addTab(self.tab_draw, "✍ Draw")
        self.tabs.addTab(self.tab_type, "⌨ Type")
        layout.addWidget(self.tabs)
        
        # --- Save Button ---
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
        temp_dir = tempfile.gettempdir()
        self.signature_file_path = os.path.join(temp_dir, "temp_signature.png")
        
        if self.tabs.currentIndex() == 0:
            self.draw_canvas.canvas.save(self.signature_file_path, "PNG")
        else:
            self.type_canvas.save(self.signature_file_path, "PNG")
            
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
        
        # UNDO State Variables
        self.undo_stack = []
        self.MAX_UNDO_STEPS = 5 # Prevent high memory usage on huge PDFs
        
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

        # Add Undo Action
        self.undo_action = toolbar.addAction("↩ Undo")
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo) # Ctrl+Z (or Cmd+Z on Mac)
        self.undo_action.triggered.connect(self.undo)
        self.undo_action.setEnabled(False) # Disabled initially
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
            self.doc = pymupdf.open(file_name)
            self.current_page = 0
            self.zoom_factor = 1.0 
            
            # Reset undo stack for the new document
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

    def prev_page(self):
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            self.show_page()

    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
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
        """Saves a snapshot of the current PDF to memory for undoing."""
        if self.doc:
            # tobytes() serializes the current state of the document
            current_state = self.doc.tobytes()
            self.undo_stack.append(current_state)
            
            # Keep stack limited to prevent memory bloat
            if len(self.undo_stack) > self.MAX_UNDO_STEPS:
                self.undo_stack.pop(0)
                
            self.undo_action.setEnabled(True)

    def undo(self):
        """Restores the last saved state of the PDF."""
        if self.undo_stack:
            last_state = self.undo_stack.pop()
            
            if self.doc:
                self.doc.close()
                
            # Reload document from the byte stream
            self.doc = pymupdf.open(stream=last_state, filetype="pdf")
            self.show_page()
            
            if not self.undo_stack:
                self.undo_action.setEnabled(False)

    def handle_click(self, x, y):
        if not self.doc:
            return

        page = self.doc[self.current_page]
        pdf_x = x / self.zoom_factor
        pdf_y = y / self.zoom_factor

        if self.text_tool_active:
            text, ok = QInputDialog.getText(self, "Input Text", "Enter text to insert:")
            if ok and text:
                self.save_state_for_undo() # Save state BEFORE making the change
                
                page.insert_text(pymupdf.Point(pdf_x, pdf_y), text, fontsize=12, color=(0, 0, 0))
                self.show_page()
                self.text_action.setChecked(False)
                self.toggle_text_tool(False)
                
        elif self.signature_tool_active and self.signature_file_path:
            self.save_state_for_undo() # Save state BEFORE making the change
            
            width = 120
            height = 60
            rect = pymupdf.Rect(pdf_x - (width/2), pdf_y - (height/2), pdf_x + (width/2), pdf_y + (height/2))
            
            page.insert_image(rect, filename=self.signature_file_path)
            self.show_page()

    def save_pdf(self):
        if self.doc:
            file_name, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
            if file_name:
                self.doc.save(file_name)

    def closeEvent(self, event):
        if self.signature_file_path:
            try:
                os.remove(self.signature_file_path)
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
