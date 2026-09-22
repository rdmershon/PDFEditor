import sys
import pymupdf
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QScrollArea, QFileDialog, 
                             QToolBar, QInputDialog, QMessageBox, QDialog, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QSpinBox, QDialogButtonBox, QPushButton, QWidget, QComboBox)
from PyQt6.QtGui import (QImage, QPixmap, QPainter, QPen, QColor)
from PyQt6.QtCore import Qt, QPoint, QByteArray, QBuffer, QIODevice

class SignaturePad(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(400, 200)
        self.image = QImage(self.size(), QImage.Format.Format_ARGB32)
        self.image.fill(Qt.GlobalColor.transparent)
        
        self.drawing = False
        self.last_point = QPoint()
        self.pen = QPen(QColor(25, 25, 112), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    def paintEvent(self, event):
        canvas_painter = QPainter(self)
        canvas_painter.fillRect(self.rect(), Qt.GlobalColor.white)
        canvas_painter.drawImage(self.rect(), self.image, self.image.rect())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.last_point = event.pos()

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.MouseButton.LeftButton) and self.drawing:
            painter = QPainter(self.image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(self.pen)
            painter.drawLine(self.last_point, event.pos())
            self.last_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = False

    def clear(self):
        self.image.fill(Qt.GlobalColor.transparent)
        self.update()

    def get_image_bytes(self):
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self.image.save(buffer, "PNG")
        return byte_array.data()


class SignatureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Draw Signature")
        
        layout = QVBoxLayout(self)
        self.pad = SignaturePad()
        layout.addWidget(self.pad)
        
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.pad.clear)
        btn_layout.addWidget(clear_btn)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        btn_layout.addWidget(self.buttons)
        
        layout.addLayout(btn_layout)


class AddTextDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Text to PDF")
        self.resize(300, 250)
        layout = QVBoxLayout(self)
        
        format_layout = QHBoxLayout()
        
        format_layout.addWidget(QLabel("Font:"))
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Helvetica", "Times Roman", "Courier"])
        format_layout.addWidget(self.font_combo)
        
        format_layout.addWidget(QLabel("Size:"))
        self.font_spin = QSpinBox()
        self.font_spin.setValue(12) 
        self.font_spin.setRange(6, 144)
        format_layout.addWidget(self.font_spin)
        
        layout.addLayout(format_layout)
        
        layout.addWidget(QLabel("Text:"))
        self.text_edit = QTextEdit()
        layout.addWidget(self.text_edit)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_data(self):
        return self.text_edit.toPlainText(), self.font_spin.value(), self.font_combo.currentText()


class PDFLabel(QLabel):
    def __init__(self, parent_editor):
        super().__init__()
        self.editor = parent_editor

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and (self.editor.text_tool_active or self.editor.edit_tool_active or self.editor.sign_tool_active):
            self.editor.handle_click(event.pos().x(), event.pos().y())


class PDFEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python PDF Editor")
        self.setGeometry(100, 100, 800, 1000)
        
        self.doc = None
        self.current_page = 0
        
        self.text_tool_active = False 
        self.edit_tool_active = False 
        self.sign_tool_active = False
        
        # --- UPGRADED: Scroll Area Configuration ---
        self.scroll_area = QScrollArea()
        self.image_label = PDFLabel(self) 
        
        # Ensure the label can expand to the full size of the PDF image
        self.image_label.setScaledContents(False) 
        
        # Force scrollbars to always be available if the content exceeds the window
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setWidgetResizable(True) # Allows the inner widget to resize
        
        self.scroll_area.setWidget(self.image_label)
        self.setCentralWidget(self.scroll_area)
        
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
        
        self.text_action = toolbar.addAction("Add Text")
        self.text_action.setCheckable(True) 
        self.text_action.triggered.connect(self.toggle_text_tool)
        
        self.edit_action = toolbar.addAction("Edit Text")
        self.edit_action.setCheckable(True) 
        self.edit_action.triggered.connect(self.toggle_edit_tool)

        self.sign_action = toolbar.addAction("Sign Document")
        self.sign_action.setCheckable(True)
        self.sign_action.triggered.connect(self.toggle_sign_tool)

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
            # Crucial for scrolling: update the label's size to match the new image exactly
            self.image_label.resize(pixmap.width(), pixmap.height())
            self.image_label.setMinimumSize(pixmap.width(), pixmap.height())

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
            self.sign_action.setChecked(False)
            self.edit_tool_active = False
            self.sign_tool_active = False
            self.image_label.setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    def toggle_edit_tool(self, checked):
        self.edit_tool_active = checked
        if checked:
            self.text_action.setChecked(False) 
            self.sign_action.setChecked(False)
            self.text_tool_active = False
            self.sign_tool_active = False
            self.image_label.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    def toggle_sign_tool(self, checked):
        self.sign_tool_active = checked
        if checked:
            self.text_action.setChecked(False)
            self.edit_action.setChecked(False)
            self.text_tool_active = False
            self.edit_tool_active = False
            self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    def handle_click(self, x, y):
        if not self.doc:
            return

        page = self.doc[self.current_page]

        # --- ADD TEXT MODE ---
        if self.text_tool_active:
            dialog = AddTextDialog(self)
            if dialog.exec(): 
                text, font_size, font_name = dialog.get_data()
                
                font_map = {
                    "Helvetica": "helv",
                    "Times Roman": "tiro",
                    "Courier": "cour"
                }
                pdf_font = font_map.get(font_name, "helv")
                
                if text.strip():
                    insertion_point = pymupdf.Point(x, y + font_size)
                    page.insert_text(
                        insertion_point, 
                        text, 
                        fontsize=font_size, 
                        fontname=pdf_font,
                        color=(0, 0, 0)
                    )
                    self.show_page()
            
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
                    
                    page.insert_text(pymupdf.Point(word_rect.x0, baseline), new_text, fontsize=approx_fontsize, color=(0, 0, 0))
                    self.show_page()
            else:
                QMessageBox.information(self, "No text found", "You didn't click on an editable word.")
            
            self.edit_action.setChecked(False)
            self.toggle_edit_tool(False)

        # --- SIGNATURE MODE ---
        elif self.sign_tool_active:
            dialog = SignatureDialog(self)
            
            if dialog.exec():
                signature_bytes = dialog.pad.get_image_bytes()
                
                img_width = 150
                img_height = 75
                rect = pymupdf.Rect(x, y - img_height, x + img_width, y)
                
                page.insert_image(rect, stream=signature_bytes)
                self.show_page()

            self.sign_action.setChecked(False)
            self.toggle_sign_tool(False)

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
