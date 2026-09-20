import sys
import pymupdf
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QScrollArea, QFileDialog, QToolBar, QInputDialog
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

class PDFLabel(QLabel):
    def __init__(self, parent_editor):
        super().__init__()
        self.editor = parent_editor

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.editor.text_tool_active:
            self.editor.handle_click(event.pos().x(), event.pos().y())

class PDFEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python PDF Editor")
        self.setGeometry(100, 100, 800, 1000)
        
        # --- NEW: Zoom State Variable ---
        self.zoom_factor = 1.0  # 1.0 means 100% scale
        
        self.doc = None
        self.current_page = 0
        self.text_tool_active = False
        
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
        
        # --- NEW: Zoom Buttons ---
        zoom_in_action = toolbar.addAction("Zoom In")
        zoom_in_action.triggered.connect(self.zoom_in)
        
        zoom_out_action = toolbar.addAction("Zoom Out")
        zoom_out_action.triggered.connect(self.zoom_out)
        toolbar.addSeparator()
        
        self.text_action = toolbar.addAction("Text Tool")
        self.text_action.setCheckable(True) 
        self.text_action.triggered.connect(self.toggle_text_tool)
        toolbar.addSeparator()
        
        save_action = toolbar.addAction("Save As")
        save_action.triggered.connect(self.save_pdf)
        
    def open_pdf(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_name:
            self.doc = pymupdf.open(file_name)
            self.current_page = 0
            self.zoom_factor = 1.0 # Reset zoom when opening a new file
            self.show_page()
            
    def show_page(self):
        if self.doc:
            page = self.doc[self.current_page]
            
            # --- NEW: Apply the zoom matrix ---
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
            
    # --- NEW: Zoom Logic ---
    def zoom_in(self):
        if self.doc:
            self.zoom_factor *= 1.2  # Increase size by 20%
            self.show_page()

    def zoom_out(self):
        if self.doc:
            self.zoom_factor /= 1.2  # Decrease size by 20%
            self.show_page()
    
    def toggle_text_tool(self, checked):
        self.text_tool_active = checked
        if checked:
            self.image_label.setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    def handle_click(self, x, y):
        if not self.doc:
            return

        text, ok = QInputDialog.getText(self, "Input Text", "Enter text to insert:")
        
        if ok and text:
            page = self.doc[self.current_page]
            
            # --- NEW: Coordinate Translation Math ---
            # Convert the screen pixel click to the actual PDF document point
            pdf_x = x / self.zoom_factor
            pdf_y = y / self.zoom_factor
            
            # Note: We also scale the font size slightly based on zoom so 
            # it doesn't look massive when typed while zoomed out.
            # You can keep this static (e.g., 12) if you prefer absolute font sizes.
            page.insert_text(
                pymupdf.Point(pdf_x, pdf_y), 
                text, 
                fontsize=12, 
                color=(0, 0, 0)
            )
            
            self.show_page()
            self.text_action.setChecked(False)
            self.toggle_text_tool(False)
            
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
