import sys
import pymupdf
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QScrollArea, QFileDialog, 
                             QToolBar, QInputDialog, QMessageBox, QDialog, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QSpinBox, QDialogButtonBox)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

# --- NEW: Custom Dialog for Adding Multi-line Text & Font Size ---
class AddTextDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Text to PDF")
        self.resize(300, 200)
        layout = QVBoxLayout(self)
        
        # Font size selector
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Font Size:"))
        self.font_spin = QSpinBox()
        self.font_spin.setValue(12) # Default size
        self.font_spin.setRange(6, 144)
        font_layout.addWidget(self.font_spin)
        layout.addLayout(font_layout)
        
        # Text input area (supports multiple lines)
        layout.addWidget(QLabel("Text:"))
        self.text_edit = QTextEdit()
        layout.addWidget(self.text_edit)
        
        # OK and Cancel buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_data(self):
        """Returns the text entered and the chosen font size."""
        return self.text_edit.toPlainText(), self.font_spin.value()

# 1. Create a custom QLabel to capture mouse clicks
class PDFLabel(QLabel):
    def __init__(self, parent_editor):
        super().__init__()
        self.editor = parent_editor

    def mousePressEvent(self, event):
        # Process clicks if the left button is clicked AND either tool is active
        if event.button() == Qt.MouseButton.LeftButton and (self.editor.text_tool_active or self.editor.edit_tool_active):
            self.editor.handle_click(event.pos().x(), event.pos().y())

class PDFEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python PDF Editor")
        self.setGeometry(100, 100, 800, 1000)
        
        # State variables
        self.doc = None
        self.current_page = 0
        self.text_tool_active = False 
        self.edit_tool_active = False 
        
        # Setup the main viewing area
        self.scroll_area = QScrollArea()
        self.image_label = PDFLabel(self) 
        self.scroll_area.setWidget(self.image_label)
        self.setCentralWidget(self.scroll_area)
        
        # Setup the Toolbar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        open_action = toolbar.addAction("Open PDF")
        open_action.triggered.connect(self.open_pdf)
        toolbar.addSeparator()
        
        prev_action = toolbar.addAction("Previous Page")
        prev_action.triggered.connect(self.prev_page)
        next_action = toolbar.addAction("Next Page")
        next_action.triggered.connect(self.next_page)
        toolbar.addSeparator()
        
        # --- Add Text Button ---
        self.text_action = toolbar.addAction("Add Text")
        self.text_action.setCheckable(True) 
        self.text_action.triggered.connect(self.toggle_text_tool)
        
        # --- Edit Text Button ---
        self.edit_action = toolbar.addAction("Edit Text")
        self.edit_action.setCheckable(True) 
        self.edit_action.triggered.connect(self.toggle_edit_tool)

        toolbar.addSeparator()
        
        save_action = toolbar.addAction("Save As")
        save_action.triggered.connect(self.save_pdf)
        
    def open_pdf(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_name:
            self.doc = pymupdf.open(file_name)
            self.current_page = 0
            self.show_page()
            
    def show_page(self):
        if self.doc:
            page = self.doc[self.current_page]
            pix = page.get_pixmap()
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
            
    def toggle_text_tool(self, checked):
        self.text_tool_active = checked
        if checked:
            self.edit_action.setChecked(False) 
            self.edit_tool_active = False
            self.image_label.setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    def toggle_edit_tool(self, checked):
        self.edit_tool_active = checked
        if checked:
            self.text_action.setChecked(False) 
            self.text_tool_active = False
            self.image_label.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    def handle_click(self, x, y):
        """Called by the custom PDFLabel when the user clicks the image."""
        if not self.doc:
            return

        page = self.doc[self.current_page]

        # --- UPGRADED ADD TEXT MODE ---
        if self.text_tool_active:
            dialog = AddTextDialog(self)
            
            # If the user clicks "OK" in the custom dialog
            if dialog.exec(): 
                text, font_size = dialog.get_data()
                
                if text.strip():
                    # PyMuPDF's Point(x,y) anchors to the BOTTOM-left of the first line of text.
                    # By adding the font size to the Y coordinate, the text drops down naturally 
                    # from exactly where the user's mouse clicked.
                    insertion_point = pymupdf.Point(x, y + font_size)
                    
                    page.insert_text(
                        insertion_point, 
                        text, 
                        fontsize=font_size, 
                        color=(0, 0, 0)
                    )
                    self.show_page()
            
            # Turn the tool off after one use to prevent accidental clicks
            self.text_action.setChecked(False)
            self.toggle_text_tool(False)

        # --- EDIT TEXT MODE ---
        elif self.edit_tool_active:
            words = page.get_text("words")
            clicked_word = None
            word_rect = None
            
            tolerance = 2 
            for w in words:
                x0, y0, x1, y1, word_text = w[0], w[1], w[2], w[3], w[4]
                if (x0 - tolerance <= x <= x1 + tolerance) and (y0 - tolerance <= y <= y1 + tolerance):
                    clicked_word = word_text
                    word_rect = pymupdf.Rect(x0, y0, x1, y1)
                    break
            
            if clicked_word:
                new_text, ok = QInputDialog.getText(self, "Edit Text", f"Edit word:", text=clicked_word)
                
                if ok and new_text:
                    page.add_redact_annot(word_rect)
                    page.apply_redactions() 
                    
                    approx_fontsize = word_rect.height * 0.75
                    baseline = word_rect.y1 - (word_rect.height * 0.2)
                    
                    page.insert_text(
                        pymupdf.Point(word_rect.x0, baseline), 
                        new_text, 
                        fontsize=approx_fontsize, 
                        color=(0, 0, 0)
                    )
                    
                    self.show_page()
            else:
                QMessageBox.information(self, "No text found", "You didn't click on an editable word.")
            
            self.edit_action.setChecked(False)
            self.toggle_edit_tool(False)

    def save_pdf(self):
        if self.doc:
            file_name, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
            if file_name:
                self.doc.save(file_name)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PDFEditor()
    window.show()
    sys.exit(app.exec())
