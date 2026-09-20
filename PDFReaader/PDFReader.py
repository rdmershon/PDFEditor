import sys
import pymupdf
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QScrollArea, QFileDialog, QToolBar
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

class PDFEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python PDF Editor")
        self.setGeometry(100, 100, 800, 1000)
        
        # 1. Setup the main viewing area
        self.scroll_area = QScrollArea()
        self.image_label = QLabel()
        self.scroll_area.setWidget(self.image_label)
        self.setCentralWidget(self.scroll_area)
        
        # 2. Setup the Toolbar and UI buttons
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # --- Open Button ---
        open_action = toolbar.addAction("Open PDF")
        open_action.triggered.connect(self.open_pdf)
        
        toolbar.addSeparator()
        
        # --- NEW: Navigation Buttons ---
        prev_action = toolbar.addAction("Previous Page")
        prev_action.triggered.connect(self.prev_page)
        
        next_action = toolbar.addAction("Next Page")
        next_action.triggered.connect(self.next_page)
        
        toolbar.addSeparator()
        
        # --- NEW: Edit Buttons ---
        watermark_action = toolbar.addAction("Add Watermark")
        watermark_action.triggered.connect(self.add_watermark)
        
        toolbar.addSeparator()
        
        # --- NEW: Save Button ---
        save_action = toolbar.addAction("Save As")
        save_action.triggered.connect(self.save_pdf)
        
        # State variables
        self.doc = None
        self.current_page = 0
        
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

    # --------------------------------------------------------
    # NEW FEATURE METHODS START HERE
    # --------------------------------------------------------
    
    def prev_page(self):
        # Ensure a document is open and we aren't on the first page
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            self.show_page()

    def next_page(self):
        # Ensure a document is open and we aren't on the last page
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1
            self.show_page()
            
    def add_watermark(self):
        if self.doc:
            page = self.doc[self.current_page]
            # Insert text at specific coordinates
            page.insert_text(pymupdf.Point(100, 100), "CONFIDENTIAL", fontsize=35, color=(1, 0, 0))
            # Refresh the screen so the user sees the new text immediately
            self.show_page()
            
    def save_pdf(self):
        if self.doc:
            # Prompt the user for where to save the file
            file_name, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
            if file_name:
                self.doc.save(file_name)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PDFEditor()
    window.show()
    sys.exit(app.exec())
