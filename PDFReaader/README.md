Python PDF Editor 📄🖋️

A lightweight, desktop-based PDF viewer and editor built with Python. This application uses PyQt6 for a modern graphical user interface and PyMuPDF for high-performance PDF rendering and manipulation.

Features

Currently, the application supports the following functionality:

View PDFs: Open and display PDF documents.

Page Navigation: Move between pages using "Next Page" and "Previous Page" controls.

Add Watermarks: Insert text (e.g., "CONFIDENTIAL") directly onto the current PDF page.

Save Modifications: Save the edited document to a new file using a "Save As" dialogue.

Prerequisites

To run this project, you will need Python 3 installed on your machine. The application relies on two external libraries:

PyQt6: For the desktop window, toolbars, and UI components.

pymupdf: For reading, modifying, and rendering the PDF files.

Installation

Clone or Download the Repository:
Download the project files to your local machine.

Install the Required Libraries:
Open your terminal or command prompt and run the following command:

pip install pymupdf PyQt6


Note for Windows Users: If you see a warning stating that the scripts are installed in a directory that is not on your PATH (e.g., C:\Users\<YourUser>\AppData\Local\Python\...\Scripts), you will need to add that specific directory path to your Windows Environment Variables for PyQt6 to function correctly.

Usage

To start the application, navigate to the folder containing your script in the terminal and run:

python main.py 


(Replace main.py with the actual name of your Python file).

How to Edit a PDF

Click Open PDF in the toolbar and select a file.

Navigate to the page you want to edit using Next Page or Previous Page.

Click Add Watermark to stamp the page. (Currently configured to add red text at the top left).

Click Save As to export your modified document.

Next Steps / Roadmap

Future updates to this project could include:

Interactive click-to-type text insertion.

Zoom In / Zoom Out functionality.

Text highlighting tools.

A sidebar with page thumbnails.
