"""
Simplest PyQt App - Text and a Button
"""

import sys
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt
import requests


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        ###############################################################################
        # VARIABLES AND CLASS SETUP
        ###############################################################################
        # State variables
        self.is_backend_on = False
        self.process = None

        ###############################################################################
        # UI SETUP
        ###############################################################################
        # Window settings
        self.setWindowTitle("HAHS AI Call Assistant")
        self.setMinimumSize(400, 300)

        # Create layout (vertical stack)
        layout = QVBoxLayout()

        # Create widgets
        title = QLabel("HAHS AI POWERED CALL ASSISTANT")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.button = QPushButton("Start")
        self.button.clicked.connect(self.on_button_click)  # Connect click to function
        self.button.setObjectName("startButton")

        status = QLabel("Status: Stopped")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Add widgets to layout
        layout.addWidget(title)
        layout.addWidget(self.button)
        layout.addWidget(status)

        self.setLayout(layout)

        # Basic dark styling
        self.setStyleSheet("""
            QWidget {
                background-color: #282c34;
                color: white;
                font-size: 16px;
            }
            QPushButton {
                background-color: #28a745;
                padding: 10px;
                border-radius: 5px;
            }
                           

        """)


    ###############################################################################
    # SIGNAL CALL BACKS
    ###############################################################################
    def on_button_click(self):
        print("Button clicked!")

        if not self.is_backend_on:
            # UI Changes
            self.button.setText("Starting...")
            self.button.setStyleSheet("background-color: #6c757d; padding: 10px; border-radius: 5px;")
            self.button.setEnabled(False)

            # Logic
            self._start_backend()
        else:
            # UI Changes
            self.button.setText("Start")
            self.button.setStyleSheet("background-color: #28a745; padding: 10px; border-radius: 5px;")

            # Logic
            self._stop_backend()
            self.is_backend_on = False

    ###############################################################################
    # ACTION FUNCTIONS
    ###############################################################################
    def _start_backend(self):
        # Get the path to app_v3.py
        project_root = Path(__file__).parent.parent  # frontend_qt -> Thoth
        script_path = project_root / "backend" / "thoth" / "core" / "call_assistant" / "app_v3.py"

        # Get python from venv
        if sys.platform == "win32":
            python_exe = project_root / ".venv" / "Scripts" / "python.exe"
        else:
            python_exe = project_root / ".venv" / "bin" / "python"

        print(f"[FRONTEND QT] Starting: {python_exe} {script_path}")

        # Start the process (non-blocking)
        self.process = subprocess.Popen(
            [str(python_exe), str(script_path)],
            cwd=str(script_path.parent),  # Run from the script's directory
        )


    def _stop_backend(self):
        # Check if process is running and exists
        if hasattr(self, 'process') and self.process:
            print("[FRONTEND QT] Stopping backend...")
            self.process.terminate()
            self.process = None
    
    def _reset_button(self):
        self.button.setText("Start")
        self.button.setStyleSheet("background-color: #28a745; padding: 10px; border-radius: 5px;")
        self.button.setEnabled(True)

# Run the app
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())