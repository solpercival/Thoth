"""
Simplest PyQt App - Text and a Button
"""

import sys
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QCheckBox, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QTimeEdit
from PyQt6.QtCore import Qt, QTimer, QTime, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont

import requests
import time

AUTO_START_CHECK_FREQ = 20000  #ms

################################################################################
# SUB WIDGETS
################################################################################
class AfterHourTimeSelect(QWidget):
    def __init__(self):
        super().__init__()

        # UI
        layout = QVBoxLayout()
        # Put these next two lines in because for whatever reason they keep
        # disappearing when the button is clicked
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        layout.setSpacing(5)  # Tighter spacing
        start_time_layout = QHBoxLayout()
        stop_time_layout = QHBoxLayout()

        # Start time
        start_label = QLabel("Start:")
        self.start_time = QTimeEdit()
        self.start_time.setTime(QTime(17, 30))  # 5:00 PM default
        self.start_time.setDisplayFormat("HH:mm")  # 24-hour format

        start_time_layout.addWidget(start_label)
        start_time_layout.addWidget(self.start_time)

        # Stop time
        stop_label = QLabel("Stop:")
        self.stop_time = QTimeEdit()
        self.stop_time.setTime(QTime(8, 30))  # 9:00 AM default
        self.stop_time.setDisplayFormat("HH:mm")

        stop_time_layout.addWidget(stop_label)
        stop_time_layout.addWidget(self.stop_time)

        # Add to main layout
        layout.addLayout(start_time_layout)
        layout.addLayout(stop_time_layout)
        self.setLayout(layout)
        self.setMinimumHeight(80)  # Ensure enough space for both rows

    # Getter for start time
    # Returns start time [hour, minute]
    def get_start_time(self) -> list[int]:
        return[self.start_time.time().hour(), self.start_time.time().minute()]

    # Getter for stop time
    # Returns stop time [hour, minute]
    def get_stop_time(self) -> list[int]:
        return[self.stop_time.time().hour(), self.stop_time.time().minute()]

        
class AutoStartWidget(QWidget):
    # Signals must be class attributes (not in __init__)
    auto_start_enabled = pyqtSignal(list, list)  # (start_time, stop_time)
    auto_start_disabled = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        # These next two lines are for so that the time select remains visible
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # UI
        self.autostart_checkbox = QCheckBox("Auto-start at after hours")
        self.autostart_checkbox.stateChanged.connect(self.on_autostart_changed)

        # Time select
        self.time_select = AfterHourTimeSelect()
        self.time_select.setVisible(False)

        # Add to layout
        layout.addWidget(self.autostart_checkbox)
        layout.addWidget(self.time_select)
        self.setLayout(layout)


    # Logic
    def on_autostart_changed(self, state):
        # Get curent time
        start_time: list = self.time_select.get_start_time()
        stop_time: list = self.time_select.get_stop_time()


        # 2 is enabled, 0 disabled
        if state == 2:
            self.time_select.show()
            self.auto_start_enabled.emit(start_time, stop_time)

        else:
            self.time_select.hide()
            self.auto_start_disabled.emit()

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
        self.setWindowTitle("HAHS AI Call Assistant v0.5")
        self.setMinimumSize(400, 400)

        # Create layout (vertical stack)
        layout = QVBoxLayout()

        # Create widgets
        # Title
        title = QLabel("HAHS AI POWERED CALL ASSISTANT")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 512, 700))

        # HAHS Banner
        script_dir = Path(__file__).parent
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
        #self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Add widgets to layout
        layout.addWidget(title)
        layout.addWidget(app_banner)
        layout.addSpacing(40)
        layout.addWidget(self.button)

        self.autostart_widget = AutoStartWidget()
        layout.addWidget(self.autostart_widget)
        self.autostart_widget.auto_start_enabled.connect(self._on_auto_start_enabled)
        self.autostart_widget.auto_start_disabled.connect(self._on_auto_start_disabled)

        layout.addStretch()  # Flexible space instead of fixed
        layout.addWidget(self.status)
        self.setLayout(layout)

        # Basic dark styling
        ##ffffff;
        ##282c34
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
        # BACKGROUND JOBS
        ###############################################################################
        self.autostart_timer = QTimer()
        self.autostart_timer.timeout.connect(self._check_autostart_time)
        # Don't start timer here - it starts when checkbox is enabled via signal



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
        


    def _on_auto_start_enabled(self, start_time:list, stop_time:list) -> None:
        """
        When the auto start check box is enabled
        """
        print(f"Auto-start enabled. Start: {start_time}. Stop: {stop_time}")
        self.autostart_timer.start(AUTO_START_CHECK_FREQ)
        pass


    def _on_auto_start_disabled(self) -> None:
        """
        When the auto start check box is disabled
        """
        print("Auto-start disabled")
        self.autostart_timer.stop()
        pass
        

    def _check_autostart_time(self) -> None:
        """
        Called everytime auto_start_timer has timed out. This is the loop that checks the auto start
        It imitates a user pressing the start button.
        """
        # [Hour, Minute] in 24h format
        current_time: list = [QTime.currentTime().hour(), QTime.currentTime().minute()]
        time_select_menu: AfterHourTimeSelect = self.autostart_widget.time_select
        start_time: list = time_select_menu.get_start_time()
        stop_time: list = time_select_menu.get_stop_time()

        print(f"Checking for auto times. Current time: {current_time}. Start time: {start_time}. Stop time: {stop_time}.")

        # Check START
        start_time: list = time_select_menu.get_start_time()
        stop_time: list = time_select_menu.get_stop_time()
        if start_time[0] == current_time[0] and start_time[1] == current_time[1]:
            if not self.is_backend_on:
                self.on_button_click()

        # Check STOP
        elif stop_time[0] == current_time[0] and stop_time[1] == current_time[1]:
            if self.is_backend_on:
                self.on_button_click()



    ###############################################################################
    # ACTION FUNCTIONS
    ###############################################################################
    def _start_backend(self):
        # Get the path to app_v3.py
        project_root = Path(__file__).parent.parent  # frontend_qt -> Thoth
        script_path = project_root / "backend" / "thoth" / "core" / "call_assistant" / "app_v5.py"

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





# Run the app
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())