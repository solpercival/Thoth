"""
Simplest PyQt App - Text and a Button
"""

import sys
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QCheckBox, QWidget, QVBoxLayout, QHBoxLayout, \
    QPushButton, QLabel, QFrame, QLineEdit, QTimeEdit, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QFont

import requests
import time
sys.path.insert(0, str(Path(__file__).parent.parent))
import utils


class PhoneList(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        line_edit_layout = QHBoxLayout()
        edit_buttons_layout = QHBoxLayout()
        
        # The list
        self.list_widget = QListWidget()
        list_title = QLabel("Call Queue")

        # Line edit
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("Enter number and press Enter")
        self.line_edit.returnPressed.connect(self.add_item)

        add_button = QPushButton("Add")
        add_button.pressed.connect(self.add_item)
        line_edit_layout.addWidget(self.line_edit)
        line_edit_layout.addWidget(add_button)

        # Edit buttons
        move_up_button = QPushButton("↑")
        move_up_button.setStyleSheet("background-color: #e8e9e8; color: black;")
        move_up_button.pressed.connect(self._move_entry_up)
        edit_buttons_layout.addWidget(move_up_button)

        move_down_button = QPushButton("↓")
        move_down_button.setStyleSheet("background-color: #e8e9e8; color: black;")
        move_down_button.pressed.connect(self._move_entry_down)
        edit_buttons_layout.addWidget(move_down_button)

        delete_button = QPushButton("Delete")
        delete_button.setStyleSheet("background-color: #ff2400;")
        delete_button.pressed.connect(self._delete_selected)
        edit_buttons_layout.addWidget(delete_button)


        # Assemble the final widget
        layout.addWidget(list_title)
        layout.addWidget(self.list_widget)
        layout.addLayout(line_edit_layout)
        layout.addLayout(edit_buttons_layout)

        # Load list
        self._load_list()
    
    def add_item(self):
        text = self.line_edit.text().strip()
        if text:
            self.list_widget.addItem(text)
            self.line_edit.clear()


    def take_top_number(self) -> str:
        first_item = self.list_widget.takeItem(0)  # Returns a QListWidgetItem (use .text() to retrieve content)

        # If exist return, else return None
        if first_item:
            return first_item
        return None
    
    
    def _load_list(self) -> None:
        try:
            with open("phone_numbers_in_queue.txt", "r") as f:
                for line in f:
                    line = line.strip()
                    if line:  # Skip empty lines
                        self.list_widget.addItem(line)
        except FileNotFoundError:
            pass  # File doesn't exist yet, that's fine

    def save_list(self) -> None:
        with open("phone_numbers_in_queue.txt", "w") as f:
            for i in range(self.list_widget.count()):
                f.write(self.list_widget.item(i).text() + "\n")


    ####################
    # SIGNAL CALL BACKS
    #####################
    def _delete_selected(self) -> None:
        current_item = self.list_widget.currentItem()
        if current_item:
            self.list_widget.takeItem(self.list_widget.row(current_item))

    def _move_entry_up(self) -> None:
        current_row = self.list_widget.currentRow()
        if current_row > 0:  # Can't move up if already at top
            item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row - 1, item)
            self.list_widget.setCurrentRow(current_row - 1)  # Keep it selected
    
    def _move_entry_down(self) -> None:
        current_row = self.list_widget.currentRow()
        if current_row < self.list_widget.count() - 1:  # Can't move down if at bottom
            item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row + 1, item)
            self.list_widget.setCurrentRow(current_row + 1)

    




    



################################################################################
# MAIN WINDOW
################################################################################

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        ###############################################################################
        # VARIABLES AND CLASS SETUP
        ###############################################################################
        # State variables
        self.is_backend_on = False
        self.process = None
        self.health_check_timer = None
        self.health_check_start_time = None
        self.health_check_timeout = 15  # seconds

        ###############################################################################
        # UI SETUP
        ###############################################################################
        # Window settings
        self.setWindowTitle("HAHS AI Odin Screening Assistant v0.5")
        self.setMinimumSize(400, 400)

        # Create layout (vertical stack)
        layout = QVBoxLayout()

        # Create widgets
        # Title
        title = QLabel("HAHS AI POWERED SCREENING ASSISTANT")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 512, 700))

        # HAHS Banner
        script_dir = Path(__file__).parent.parent  # frontend_qt folder
        image_path = script_dir / "hahs_logo.png"
        pixmap = QPixmap(str(image_path)).scaled(300, 75)
        app_banner = QLabel()
        app_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_banner.setPixmap(pixmap)

        # The start button
        self.button = QPushButton("Start")
        self.button.clicked.connect(self.on_button_click)  # Connect click to function
        self.button.setObjectName("startButton")

        self.status = QLabel("Status: Stopped")

        # The phone list widget
        self.phone_list = PhoneList()

        # Add widgets to layout
        layout.addWidget(title)
        layout.addWidget(app_banner)
        layout.addSpacing(40)
        layout.addWidget(self.button)
        layout.addSpacing(40)
        layout.addWidget(self.phone_list)
        layout.addStretch()  # Flexible space instead of fixed, do this to prevent elements not being squished
        layout.addWidget(self.status)
        self.setLayout(layout)

        # Basic dark styling
        ##ffffff; Black
        ##282c34; Greyish black
        ##2c041c; Wine purple
        self.setStyleSheet("""
            QWidget {
                background-color: #2c041c; 
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
        # BACKGROUND JOBS
        ###############################################################################


    ###############################################################################
    # SIGNAL CALL BACKS
    ###############################################################################
    def on_button_click(self) -> None:
        """
        Called when main start button clicked
        """
        print("Button clicked!")

        if not self.is_backend_on:
            # UI Changes, set it to starting... Let the functions inside _start_backend() change 
            # the button to either STOP or START (FAILED)
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
        # Get the path to odin app.py
        project_root = Path(__file__).parent.parent.parent  # odin -> frontend_qt -> Thoth
        script_path = project_root / "backend" / "odin" / "screening_agent" / "app.py"

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

        # Start health check polling
        self.health_check_start_time = time.time()
        self.health_check_timer = QTimer()
        self.health_check_timer.timeout.connect(self._check_backend_health)
        self.health_check_timer.start(500)  # Check every 500ms


    def _check_backend_health(self):
        """Poll the backend health endpoint until it responds or times out"""
        elapsed_time = time.time() - self.health_check_start_time

        # Check for timeout
        if elapsed_time > self.health_check_timeout:
            print("[FRONTEND QT] Backend startup timeout!")
            self.health_check_timer.stop()
            self.button.setText("Start (Failed)")
            self.button.setStyleSheet("background-color: #ffc107; padding: 10px; border-radius: 5px;")
            self.button.setEnabled(True)

            # Clean up the process
            if self.process:
                self.process.terminate()
                self.process = None
            return

        # Try to ping the health endpoint
        try:
            response = requests.get("http://localhost:5000/health", timeout=1)
            if response.status_code == 200:
                print(f"[FRONTEND QT] Backend started successfully in {elapsed_time:.2f}s")
                self.health_check_timer.stop()

                # Update state and UI to running
                self.is_backend_on = True
                self.button.setText("Stop")
                self.button.setStyleSheet("background-color: #dc3545; padding: 10px; border-radius: 5px;")
                self.button.setEnabled(True)
                self.status.setText("Status: Application is running!")
        except (requests.ConnectionError, requests.Timeout):
            # Backend not ready yet, keep polling
            pass
        except Exception as e:
            print(f"[FRONTEND QT] Error checking health: {e}")

    def _stop_backend(self):
        # Check if process is running and exists
        if hasattr(self, 'process') and self.process:
            print("[FRONTEND QT] Stopping backend...")
            self.process.terminate()

            # Wait for process to terminate (timeout after 3 seconds)
            try:
                self.process.wait(timeout=3)
                print("[FRONTEND QT] Backend stopped gracefully")
            except subprocess.TimeoutExpired:
                print("[FRONTEND QT] Force killing backend...")
                self.process.kill()
                self.process.wait()
                print("[FRONTEND QT] Backend force stopped")

            self.process = None
            self.status.setText("Status: Stopped")
    
    def _reset_button(self):
        self.button.setText("Start")
        self.button.setStyleSheet("background-color: #28a745; padding: 10px; border-radius: 5px;")
        self.button.setEnabled(True)

    def closeEvent(self, event):
        self.phone_list.save_list()
        event.accept()



# Run the app
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())