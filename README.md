# Basic Python PDF Editor

A lightweight, modern desktop application for viewing, annotating, and signing PDF documents. Built with Python, PyQt6, and PyMuPDF.

## Features
* **Modern UI:** Clean, dark-mode document viewer with a flat-design toolbar and drop-shadows.
* **Text Tool:** Type custom text and drag it anywhere on the page before applying.
* **Signature Pad:** Draw your signature with a mouse/stylus or type it using a cursive font.
* **Draggable Elements:** Text and signatures float on the page allowing you to drag them into the perfect position before committing them to the document.
* **Undo System:** Made a mistake? Press `Ctrl+Z` (or `Cmd+Z`) or click the Undo button to revert your last action.

---

## Prerequisites

To run this application, you need **Python 3.8 or newer** installed on your computer.

### 1. Installing Python

**For Windows:**
1. Go to the official Python download page: [python.org/downloads](https://www.python.org/downloads/)
2. Download the latest Windows installer.
3. Run the installer. **CRITICAL:** Check the box at the bottom that says **"Add Python to PATH"** before clicking "Install Now".
4. Run the following commands "pip install PyQt6 pymupdf", may require python3 pip to install.

**For macOS:**
1. Download the macOS installer from [python.org/downloads](https://www.python.org/downloads/) OR use Homebrew:
   ```bash
   brew install python
