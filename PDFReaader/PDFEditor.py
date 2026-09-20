import sys
import os
import tempfile
import pymupdf
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QScrollArea, 
                             QFileDialog, QToolBar, QInputDialog, QDialog, 
                             QVBoxLayout, QPushButton, QHBoxLayout, QTabWidget,
                             QWidget, QLineEdit)
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QFont, QColor
from PyQt6.QtCore import Qt

# ==========================================
# CUSTOM WIDGETS
# ==========================================

class DrawCanvas(QLabel):
    """A sub-component for the Draw tab that handles mouse drawing."""
    def __init__(self):
        super().__init__()
        self.canvas = QPixmap(380, 180)
        # Use a completely transparent background so it doesn't block PDF text
        self.canvas.fill(Qt.GlobalColor.transparent)
        self.setPixmap(self.canvas)
        # Set a white background for the UI ONLY, so the user can see what they are drawing
        self.setStyleSheet("background-color: white; border: 1px dotted #ccc;")
        self.last_point = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_point = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.last_point:
            painter = QPainter(self.canvas)
            # Use dark blue ink with a slightly thinner pen for realism
            pen = QPen(QColor(0, 0, 139), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            
            # Use antialiasing to make the drawn lines much smoother
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
    """A pop-up dialog with tabs for Drawing or Typing a signature."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Signature")
        self.setFixedSize(420, 320)
        
        self.signature_file_path = None
        layout = QVBoxLayout()
        self.tabs = QTabWidget()
        
        # --- TAB 1: DRAW ---
        self.tab_draw = QWidget()
        draw_layout = QVBoxLayout()
        
        self.draw_canvas = DrawCanvas()
        draw_layout.addWidget(self.draw_canvas)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.draw_canvas.clear_canvas)
        draw_layout.addWidget(clear_btn)
        self.tab_draw.setLayout(draw_layout)
        
        # --- TAB 2: TYPE ---
        self.tab_type = QWidget()
        type_layout = QVBoxLayout()
        
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Type your name here...")
        self.text_input.textChanged.connect(self.update_type_canvas) 
        type_layout.addWidget(self.text_input)
        
        self.type_label = QLabel()
        self.type_label.setStyleSheet("background-color: white; border: 1px dotted #ccc;")
        self.type_canvas = QPixmap(380, 180)
        self.type_canvas.fill(Qt.GlobalColor.transparent)
        self.type_label.setPixmap(self.type_canvas)
        type_layout.addWidget(self.type_label)
        
        self.tab_type.setLayout(type_layout)
        
        # --- Add Tabs to Layout ---
        self.tabs.addTab(self.tab_draw, "Draw")
        self.tabs.addTab(self.tab_type, "Type")
        layout.addWidget(self.tabs)
        
        # --- Save Button ---
        save_btn = QPushButton("Save Signature")
        save_btn.clicked.connect(self.save_signature)
        layout.addWidget(save_btn)
        
        self.setLayout(layout)

    def update_type_canvas(self, text):
        """Renders the typed text onto a blank image canvas."""
        self.type_canvas.fill(Qt.GlobalColor.transparent)
        if text:
            painter = QPainter(self.type_canvas)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            
            font = QFont("Brush Script MT", 38, QFont.Weight.Normal)
            font.setItalic(True)
            font.setStyleHint(QFont.StyleHint.Cursive) 
            
            painter.setFont(font)
            # Match the dark blue ink of the pen
            painter.setPen(QColor(0, 0, 139))
            
            painter.drawText(self.type_canvas.rect(), Qt.AlignmentFlag.AlignCenter, text)
            painter.end()
            
        self.type_label.setPixmap(self.type_canvas)

    def save_signature(self):
        """Saves whichever tab is currently active to a temp PNG file (preserves transparency)."""
        temp_dir = tempfile.gettempdir()
        self.signature_file_path = os.path.join(temp_dir, "temp_signature.png")
        
        if self.tabs.currentIndex() == 0:
            self.draw_canvas.canvas.save(self.signature_file_path, "PNG")
        else:
            self.type_canvas.save(self.signature_file_path, "PNG")
            
        self.accept()


class PDFLabel(QLabel):
    """A custom label that catches mouse clicks and passes them to the editor."""
    def __init__(self, parent_editor):
        super().__init__()
        self.editor = parent_editor

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
        self.setWindowTitle("Python PDF Editor")
        self.setGeometry(100, 100, 800, 1000)
        
        # State variables
        self.doc = None
        self.current_page = 0
        self.zoom_factor = 1.0 
        self.text_tool_active = False
        self.signature_tool_active = False
        self.signature_file_path = None
        
        # UI Setup
        self.scroll_area = QScrollArea()
        self.image_label = PDFLabel(self) 
        self.scroll_area.setWidget(self.image_label)
        self.setCentralWidget(self.scroll_area)
        
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        open_action = toolbar.addAction("Open")
        open_action.triggered.connect(self.open_pdf)
        toolbar.addSeparator()
        
        prev_action = toolbar.addAction("Previous")
        prev_action.triggered.connect(self.prev_page)
        next_action = toolbar.addAction("Next")
        next_action.triggered.connect(self.next_page)
        toolbar.addSeparator()
        
        zoom_in_action = toolbar.addAction("Zoom In")
        zoom_in_action.triggered.connect(self.zoom_in)
        zoom_out_action = toolbar.addAction("Zoom Out")
        zoom_out_action.triggered.connect(self.zoom_out)
        toolbar.addSeparator()
        
        self.text_action = toolbar.addAction("Text Tool")
        self.text_action.setCheckable(True) 
        self.text_action.triggered.connect(self.toggle_text_tool)
        
        self.sign_action = toolbar.addAction("Signature Tool")
        self.sign_action.setCheckable(True)
        self.sign_action.triggered.connect(self.toggle_signature_tool)
        toolbar.addSeparator()
        
        save_action = toolbar.addAction("Save As")
        save_action.triggered.connect(self.save_pdf)
        
    def open_pdf(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_name:
            self.doc = pymupdf.open(file_name)
            self.current_page = 0
            self.zoom_factor = 1.0 
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

    def handle_click(self, x, y):
        if not self.doc:
            return

        page = self.doc[self.current_page]
        pdf_x = x / self.zoom_factor
        pdf_y = y / self.zoom_factor

        if self.text_tool_active:
            text, ok = QInputDialog.getText(self, "Input Text", "Enter text to insert:")
            if ok and text:
                page.insert_text(pymupdf.Point(pdf_x, pdf_y), text, fontsize=12, color=(0, 0, 0))
                self.show_page()
                self.text_action.setChecked(False)
                self.toggle_text_tool(False)
                
        elif self.signature_tool_active and self.signature_file_path:
            # Much smaller dimensions (roughly 33% of the original dialog size)
            width = 120
            height = 60
            
            # Offset the math so the signature is centered vertically and horizontally on your mouse click
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
    window = PDFEditor()
    window.show()
    sys.exit(app.exec())
