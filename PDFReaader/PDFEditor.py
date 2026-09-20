import sys
import os
import tempfile
import pymupdf
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QScrollArea, 
                             QFileDialog, QToolBar, QInputDialog, QDialog, 
                             QVBoxLayout, QPushButton, QHBoxLayout)
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen
from PyQt6.QtCore import Qt

# ==========================================
# CUSTOM WIDGETS
# ==========================================

class SignaturePad(QDialog):
    """A pop-up dialog that allows the user to draw a signature."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Draw Signature")
        self.setFixedSize(400, 200)
        
        self.canvas = QPixmap(400, 200)
        self.canvas.fill(Qt.GlobalColor.white)
        self.last_point = None
        self.signature_file_path = None
        
        layout = QVBoxLayout()
        
        self.canvas_label = QLabel()
        self.canvas_label.setPixmap(self.canvas)
        layout.addWidget(self.canvas_label)
        
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_canvas)
        btn_layout.addWidget(clear_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_signature)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_point = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.last_point:
            painter = QPainter(self.canvas)
            pen = QPen(Qt.GlobalColor.black, 3, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawLine(self.last_point, event.pos())
            painter.end()
            self.last_point = event.pos()
            self.canvas_label.setPixmap(self.canvas)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_point = None

    def clear_canvas(self):
        self.canvas.fill(Qt.GlobalColor.white)
        self.canvas_label.setPixmap(self.canvas)

    def save_signature(self):
        temp_dir = tempfile.gettempdir()
        self.signature_file_path = os.path.join(temp_dir, "temp_signature.png")
        self.canvas.save(self.signature_file_path, "PNG")
        self.accept()


class PDFLabel(QLabel):
    """A custom label that catches mouse clicks and passes them to the editor."""
    def __init__(self, parent_editor):
        super().__init__()
        self.editor = parent_editor

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Only trigger click handling if one of our click tools is active
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
        
        # Open
        open_action = toolbar.addAction("Open")
        open_action.triggered.connect(self.open_pdf)
        toolbar.addSeparator()
        
        # Navigation
        prev_action = toolbar.addAction("Previous")
        prev_action.triggered.connect(self.prev_page)
        next_action = toolbar.addAction("Next")
        next_action.triggered.connect(self.next_page)
        toolbar.addSeparator()
        
        # Zoom
        zoom_in_action = toolbar.addAction("Zoom In")
        zoom_in_action.triggered.connect(self.zoom_in)
        zoom_out_action = toolbar.addAction("Zoom Out")
        zoom_out_action.triggered.connect(self.zoom_out)
        toolbar.addSeparator()
        
        # Text Tool (Checkable)
        self.text_action = toolbar.addAction("Text Tool")
        self.text_action.setCheckable(True) 
        self.text_action.triggered.connect(self.toggle_text_tool)
        
        # Signature Tool (Checkable)
        self.sign_action = toolbar.addAction("Signature Tool")
        self.sign_action.setCheckable(True)
        self.sign_action.triggered.connect(self.toggle_signature_tool)
        toolbar.addSeparator()
        
        # Save
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
            
            # Apply Zoom
            mat = pymupdf.Matrix(self.zoom_factor, self.zoom_factor)
            pix = page.get_pixmap(matrix=mat)
            
            qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)
            self.image_label.setPixmap(pixmap)
            self.image_label.resize(pixmap.width(), pixmap.height())

    # --- Navigation & Zoom ---
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
    
    # --- Tool Toggles ---
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
            # If we don't have a signature saved yet, prompt the user to draw one
            if not self.signature_file_path:
                dialog = SignaturePad(self)
                if dialog.exec() == QDialog.DialogCode.Accepted and dialog.signature_file_path:
                    self.signature_file_path = dialog.signature_file_path
                    self.image_label.setCursor(Qt.CursorShape.CrossCursor)
                else:
                    # User cancelled drawing, turn the tool back off
                    self.sign_action.setChecked(False)
                    self.signature_tool_active = False
            else:
                self.image_label.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    # --- Click Handling ---
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
                # Turn off text tool after one use
                self.text_action.setChecked(False)
                self.toggle_text_tool(False)
                
        elif self.signature_tool_active and self.signature_file_path:
            # The signature pad is 400x200. We insert it at half scale (200x100) 
            # starting exactly at the point where the user clicked.
            width = 200
            height = 100
            rect = pymupdf.Rect(pdf_x, pdf_y, pdf_x + width, pdf_y + height)
            
            page.insert_image(rect, filename=self.signature_file_path)
            self.show_page()
            # Notice we do NOT turn off the signature tool here, 
            # allowing the user to stamp it multiple times.

    # --- Cleanup & Saving ---
    def save_pdf(self):
        if self.doc:
            file_name, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
            if file_name:
                self.doc.save(file_name)

    def closeEvent(self, event):
        """Delete the temporary signature image when the app closes."""
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
