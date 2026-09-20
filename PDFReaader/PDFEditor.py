import sys
import pymupdf
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QScrollArea, QFileDialog, QToolBar, QInputDialog
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

# 1. Create a custom QLabel to capture mouse clicks
class PDFLabel(QLabel):
    def __init__(self, parent_editor):
        super().__init__()
        self.editor = parent_editor # Reference back to the main window

    # Override the mousePressEvent
    def mousePressEvent(self, event):
        # Only process clicks if the left button is clicked AND the text tool is active
        if event.button() == Qt.MouseButton.LeftButton and self.editor.text_tool_active:
            # Pass the click coordinates to the editor
            self.editor.handle_click(event.pos().x(), event.pos().y())

class PDFEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python PDF Editor")
        self.setGeometry(100, 100, 800, 1000)
        
        # State variables
        self.doc = None
        self.current_page = 0
        self.text_tool_active = False # Tracks if we are in "typing mode"
        
        # Setup the main viewing area
        self.scroll_area = QScrollArea()
        # Use our custom PDFLabel instead of a standard QLabel
        self.image_label = PDFLabel(self) 
        self.scroll_area.setWidget(self.image_label)
        self.setCentralWidget(self.scroll_area)
        
        # Setup the Toolbar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # Open
        open_action = toolbar.addAction("Open PDF")
        open_action.triggered.connect(self.open_pdf)
        toolbar.addSeparator()
        
        # Navigation
        prev_action = toolbar.addAction("Previous Page")
        prev_action.triggered.connect(self.prev_page)
        next_action = toolbar.addAction("Next Page")
        next_action.triggered.connect(self.next_page)
        toolbar.addSeparator()
        
        # --- NEW: Text Tool Button ---
        # Make it checkable so it acts like a toggle (on/off)
        self.text_action = toolbar.addAction("Text Tool")
        self.text_action.setCheckable(True) 
        self.text_action.triggered.connect(self.toggle_text_tool)
        
        toolbar.addSeparator()
        
        # Save
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
            
    # --- NEW FEATURE LOGIC ---
    
    def toggle_text_tool(self, checked):
        # Update our state variable based on the button's checked state
        self.text_tool_active = checked
        if checked:
            # Change the cursor to indicate we are in typing mode
            self.image_label.setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    def handle_click(self, x, y):
        """Called by the custom PDFLabel when the user clicks the image."""
        if not self.doc:
            return

        # 1. Prompt the user for what text they want to type
        text, ok = QInputDialog.getText(self, "Input Text", "Enter text to insert:")
        
        if ok and text:
            page = self.doc[self.current_page]
            
            # 2. Insert the text using PyMuPDF coordinates (Points)
            # In this unzoomed MVP, 1 screen pixel = 1 PDF point, 
            # so we can use the x and y directly.
            page.insert_text(
                pymupdf.Point(x, y), 
                text, 
                fontsize=12, 
                color=(0, 0, 0) # Black text
            )
            
            # 3. Refresh to see the new text
            self.show_page()
            
            # 4. (Optional) Turn the tool off after one use
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
