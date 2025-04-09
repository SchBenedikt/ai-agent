"""
UI components for the Gemini Assistant application.
"""

import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, 
    QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, 
    QSystemTrayIcon, QStyle, QSizePolicy, QDialog,
    QLineEdit, QFormLayout, QDialogButtonBox, QAction,
    QMenu
)
from PyQt5.QtCore import Qt, QPoint, QDateTime, QTimer
from PyQt5.QtGui import QPixmap, QPalette, QTextCursor, QIcon

from utils import speak_text_macos
from gemini_worker import GeminiWorker
from env_manager import save_api_key, load_env_variables
from config import client

class SettingsDialog(QDialog):
    """Einstellungsdialog zur Konfiguration des API-Keys"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gemini Einstellungen")
        self.setMinimumWidth(400)
        
        # Layout erstellen
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        # Formular für die Einstellungen
        form_layout = QFormLayout()
        
        # API Key Eingabefeld
        self.api_key_input = QLineEdit()
        # Passwort-Modus für den API-Key verwenden
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setMinimumWidth(300)
        
        # Aktuelle Werte laden
        env_vars = load_env_variables()
        self.api_key_input.setText(env_vars.get('api_key', ''))
        
        form_layout.addRow("Gemini API Key:", self.api_key_input)
        self.layout.addLayout(form_layout)
        
        # Info-Text
        info_label = QLabel("Der API Key wird lokal in einer .env-Datei gespeichert.")
        info_label.setWordWrap(True)
        self.layout.addWidget(info_label)
        
        # Buttons (OK/Abbrechen)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)
    
    def get_api_key(self):
        """Gibt den eingegebenen API-Key zurück"""
        return self.api_key_input.text().strip()

class CompactGeminiAppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemini")
        # Updated window flags to remove WindowStaysOnTopHint
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Set initial size - compact overlay
        self.setGeometry(0, 0, 380, 480)
        
        # Detect dark mode or light mode from system
        self.is_dark_mode = self.detect_dark_mode()
        
        # Create main widget with rounded corners and background
        main_widget = QWidget()
        main_widget.setObjectName("mainWidget")
        
        # Apply the appropriate style based on the detected mode
        self.apply_theme(main_widget)
        
        # Main layout
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Header area with logo and title
        header_layout = QHBoxLayout()
        
        # Add Gemini icon/logo
        logo_label = QLabel()
        logo_label.setFixedSize(24, 24)
        icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation)
        logo_label.setPixmap(icon.pixmap(24, 24))
        header_layout.addWidget(logo_label)
        
        # Title with gradient text
        title_label = QLabel("Gemini Assistant")
        title_label.setObjectName("titleLabel")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Status indicator
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        header_layout.addWidget(self.status_label)
        
        # Settings button
        settings_button = QPushButton("⚙")
        settings_button.setFixedSize(26, 26)
        settings_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 100, 120, 0.8);
                border-radius: 13px;
                font-weight: bold;
                font-size: 16px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(120, 120, 140, 0.9);
            }
        """)
        settings_button.clicked.connect(self.show_settings)
        header_layout.addWidget(settings_button)
        
        # Close button
        close_button = QPushButton("×")
        close_button.setFixedSize(26, 26)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(200, 70, 70, 0.8);
                border-radius: 13px;
                font-weight: bold;
                font-size: 18px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(230, 80, 80, 0.9);
            }
        """)
        close_button.clicked.connect(self.hide_and_stop_listening)
        header_layout.addWidget(close_button)
        self.close_button = close_button
        
        main_layout.addLayout(header_layout)
        
        # Horizontal divider
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        divider.setStyleSheet("background-color: rgba(100, 100, 200, 0.3);")
        main_layout.addWidget(divider)
        
        # Content area - split into two columns
        content_layout = QHBoxLayout()
        
        # Left column: Camera preview
        left_column = QVBoxLayout()
        left_column.setSpacing(8)
        
        camera_label = QLabel("Camera Feed")
        camera_label.setAlignment(Qt.AlignCenter)
        left_column.addWidget(camera_label)
        
        self.video_label = QLabel("Camera")
        self.video_label.setObjectName("cameraLabel")
        self.video_label.setFixedSize(140, 105)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setScaledContents(True)
        left_column.addWidget(self.video_label)
        
        # Add listening indicator below camera
        self.listening_indicator = QWidget()
        self.listening_indicator.setFixedSize(10, 10)
        self.listening_indicator.setStyleSheet("""
            background-color: #ff4040;
            border-radius: 5px;
        """)
        
        indicator_layout = QHBoxLayout()
        indicator_layout.addStretch()
        indicator_layout.addWidget(self.listening_indicator)
        indicator_layout.addWidget(QLabel("Live"))
        indicator_layout.addStretch()
        
        left_column.addLayout(indicator_layout)
        left_column.addStretch()
        
        content_layout.addLayout(left_column)
        
        # Right column: Chat area
        right_column = QVBoxLayout()
        
        chat_label = QLabel("Conversation")
        chat_label.setAlignment(Qt.AlignLeft)
        right_column.addWidget(chat_label)
        
        # Text output area with improved styling for conversations
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setMinimumHeight(220)
        self.response_text.setPlaceholderText("Gemini's responses will appear here...")
        right_column.addWidget(self.response_text)
        
        content_layout.addLayout(right_column, 1)  # Give chat area more space
        main_layout.addLayout(content_layout)
        
        # Controls at the bottom
        controls_layout = QHBoxLayout()
        
        # Listening button with improved design
        self.ask_button = QPushButton("Start Listening")
        self.ask_button.setCheckable(True)
        self.ask_button.setChecked(False)
        self.ask_button.setMinimumHeight(40)
        self.ask_button.clicked.connect(self.toggle_listening)
        controls_layout.addWidget(self.ask_button)
        
        main_layout.addLayout(controls_layout)
        
        # Set the main widget
        self.setCentralWidget(main_widget)
        
        # Position in the center of the screen
        self.center_on_screen()
        
        # Store initial position for dragging
        self.old_pos = self.pos()
        
        # Initialize Gemini worker with current API-Key
        env_vars = load_env_variables()
        api_key = env_vars.get('api_key', '')
        self.worker = GeminiWorker(video_mode="camera", api_key=api_key)
        self.worker.text_update.connect(self.update_response)
        self.worker.new_message.connect(self.prepare_new_message)
        self.worker.frame_update.connect(self.update_frame)
        self.worker.response_complete.connect(self.speak_response)
        self.worker.api_key_required.connect(self.show_settings)  # Verbinde das neue Signal
        self.worker.start()
        
        # Add a flag to track if this is a new message
        self.is_new_message = True
        
        # Setup system tray
        self.setup_tray()
        self.hide()  # Start hidden
        
        # Update UI state
        self.update_ui_listening_state(False)

        # Remove always-on-top functionality
        # The timer and ensure_on_top method are no longer needed
        
        # Prüfen, ob ein API-Key vorhanden ist
        env_vars = load_env_variables()
        if not env_vars.get('api_key'):
            # Bei fehlendem API-Key direkt die Einstellungen anzeigen
            self.show_settings()

    def show_settings(self):
        """Zeigt den Einstellungsdialog an"""
        dialog = SettingsDialog(self)
        if dialog.exec_():
            # Wenn OK gedrückt wurde, API-Key speichern
            api_key = dialog.get_api_key()
            if api_key:
                save_api_key(api_key)
                # API-Key im Worker aktualisieren
                self.worker.update_api_key(api_key)
                # Erfolgsmeldung anzeigen
                self.status_label.setText("API Key gespeichert")
                # Nach 3 Sekunden wieder auf "Ready" zurücksetzen
                QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
            else:
                self.status_label.setText("Kein API Key")

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Try to get a better icon - using a speech bubble icon if available
        icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation)
        self.tray_icon.setIcon(icon)
        
        # Create context menu for the tray icon
        tray_menu = QMenu()
        settings_action = tray_menu.addAction("Einstellungen")
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Beenden")
        quit_action.triggered.connect(self.quit_app)
        self.tray_icon.setContextMenu(tray_menu)
        
        # Handle direct clicks on the tray icon
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        
        self.tray_icon.show()
        
        # Show notification about keyboard shortcut
        self.tray_icon.showMessage(
            "Gemini Assistant",
            "Press Cmd+Shift+Space to show the assistant or click the menu bar icon",
            QSystemTrayIcon.Information,
            2000
        )

    def detect_dark_mode(self):
        """Detect if the system is using dark mode"""
        if sys.platform == "darwin":  # macOS specific
            try:
                # Use PyObjC to detect dark mode
                from Foundation import NSUserDefaults
                standardDefaults = NSUserDefaults.standardUserDefaults()
                appleInterfaceStyle = standardDefaults.stringForKey_("AppleInterfaceStyle")
                return appleInterfaceStyle == "Dark"
            except:
                pass
        
        # Fallback: use QApplication palette to guess
        app = QApplication.instance()
        palette = app.palette()
        bg_color = palette.color(QPalette.Window)
        return bg_color.lightness() < 128  # If background is dark, assume dark mode

    def apply_theme(self, widget):
        """Apply the appropriate theme based on system settings"""
        if self.is_dark_mode:
            self.apply_dark_theme(widget)
        else:
            self.apply_light_theme(widget)

    def apply_dark_theme(self, widget):
        """Apply dark theme styles"""
        widget.setStyleSheet("""
            QWidget#mainWidget {
                background-color: rgba(20, 20, 30, 0.92);
                border-radius: 20px;
                border: 1px solid rgba(100, 100, 200, 0.5);
            }
            QLabel {
                color: white;
            }
            QTextEdit {
                background-color: rgba(40, 40, 60, 0.7);
                color: #e0e0e0;
                border-radius: 12px;
                padding: 10px;
                font-size: 14px;
                selection-background-color: rgba(70, 130, 180, 0.5);
                border: 1px solid rgba(70, 70, 120, 0.5);
                line-height: 1.4;
            }
            QPushButton {
                background-color: rgba(90, 120, 200, 0.8);
                color: white;
                border-radius: 12px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(100, 140, 220, 0.9);
            }
            QPushButton:checked {
                background-color: rgba(40, 180, 100, 0.8);
            }
            QPushButton:checked:hover {
                background-color: rgba(50, 200, 120, 0.9);
            }
            QLabel#cameraLabel {
                background-color: rgba(30, 30, 40, 0.8);
                border-radius: 10px;
                border: 1px solid rgba(70, 70, 120, 0.5);
            }
            QLabel#statusLabel {
                color: rgba(180, 180, 200, 0.9);
                font-size: 12px;
                font-style: italic;
            }
            QLabel#titleLabel {
                font-size: 16px;
                font-weight: bold;
                color: #d0d0ff;
            }
        """)
        
        # Update close button color for dark mode
        self.close_button_style = """
            QPushButton {
                background-color: rgba(200, 70, 70, 0.8);
                border-radius: 13px;
                font-weight: bold;
                font-size: 18px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(230, 80, 80, 0.9);
            }
        """

    def apply_light_theme(self, widget):
        """Apply light theme styles"""
        widget.setStyleSheet("""
            QWidget#mainWidget {
                background-color: rgba(245, 245, 250, 0.92);
                border-radius: 20px;
                border: 1px solid rgba(180, 180, 210, 0.5);
            }
            QLabel {
                color: #333333;
            }
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.7);
                color: #333333;
                border-radius: 12px;
                padding: 10px;
                font-size: 14px;
                selection-background-color: rgba(70, 130, 180, 0.3);
                border: 1px solid rgba(180, 180, 210, 0.5);
                line-height: 1.4;
            }
            QPushButton {
                background-color: rgba(70, 120, 200, 0.8);
                color: white;
                border-radius: 12px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(80, 140, 220, 0.9);
            }
            QPushButton:checked {
                background-color: rgba(40, 160, 80, 0.8);
            }
            QPushButton:checked:hover {
                background-color: rgba(50, 180, 100, 0.9);
            }
            QLabel#cameraLabel {
                background-color: rgba(240, 240, 245, 0.8);
                border-radius: 10px;
                border: 1px solid rgba(180, 180, 210, 0.5);
                color: #333333;
            }
            QLabel#statusLabel {
                color: rgba(100, 100, 130, 0.9);
                font-size: 12px;
                font-style: italic;
            }
            QLabel#titleLabel {
                font-size: 16px;
                font-weight: bold;
                color: #3040a0;
            }
        """)
        
        # Update close button color for light mode
        self.close_button_style = """
            QPushButton {
                background-color: rgba(200, 70, 70, 0.8);
                border-radius: 13px;
                font-weight: bold;
                font-size: 18px;
                padding: 0px;
                color: white;
            }
            QPushButton:hover {
                background-color: rgba(230, 80, 80, 0.9);
            }
        """

    def center_on_screen(self):
        screen_geometry = QApplication.desktop().availableGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
    
    def force_show_window(self):
        """More aggressive method to ensure window appears"""
        self.setVisible(True)  # Make sure it's visible
        self.show()  # Standard show
        self.showNormal()  # Ensure it's not minimized
        self.raise_()  # Bring to front
        self.activateWindow()  # Set as active window
        
        # Reapply window flags to ensure it stays on top
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint
        )
        self.show()
        
        # Activate hardware when showing the window
        self.activate_hardware_and_listen()
        
    def activate_hardware_and_listen(self):
        """Start hardware and listening separately from showing window"""
        # Start hardware and listening
        self.worker.activate_hardware()
        self.worker.listening = True
        self.update_ui_listening_state(True)
        self.response_text.clear()
        
    def hide_and_stop_listening(self):
        self.hide()
        # Stop both listening and hardware access
        self.worker.listening = False
        self.worker.deactivate_hardware()
        self.update_ui_listening_state(False)

    def toggle_listening(self, checked):
        if checked:
            self.worker.listening = True
            self.update_ui_listening_state(True)
            self.response_text.clear()
        else:
            self.worker.listening = False
            self.update_ui_listening_state(False)

    def update_ui_listening_state(self, is_listening):
        """Update UI elements to reflect listening state"""
        if is_listening:
            self.ask_button.setText("Listening...")
            self.status_label.setText("Active")
            self.listening_indicator.setStyleSheet("""
                background-color: #40ff40;
                border-radius: 5px;
            """)
        else:
            self.ask_button.setText("Start Listening")
            self.status_label.setText("Ready")
            self.listening_indicator.setStyleSheet("""
                background-color: #ff4040;
                border-radius: 5px;
            """)

    def prepare_new_message(self):
        """Prepare the text area for a new message from Gemini"""
        self.is_new_message = True
        # If there's already text, add two newlines to separate messages clearly
        if self.response_text.toPlainText().strip():
            cursor = self.response_text.textCursor()
            cursor.movePosition(cursor.End)
            self.response_text.setTextCursor(cursor)
            self.response_text.insertHtml("<br><br>")

    def update_response(self, text):
        """Update the response text with formatting"""
        # If it's a new message, add the Gemini label
        if self.is_new_message:
            self.is_new_message = False
            color = "#a0a0ff" if self.is_dark_mode else "#3040a0"
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.response_text.insertHtml(
                f'<div style="margin-top:10px;">'
                f'<span style="color:{color}; font-weight:bold;">Gemini</span> '
                f'<span style="color:#888888; font-size:11px;">({timestamp})</span>:<br>'
                f'{text}</div>'
            )
        else:
            # Continue the existing message
            cursor = self.response_text.textCursor()
            cursor.movePosition(cursor.End)
            self.response_text.setTextCursor(cursor)
            self.response_text.insertPlainText(text)
        
        # Auto scroll to bottom
        self.response_text.verticalScrollBar().setValue(
            self.response_text.verticalScrollBar().maximum()
        )

    def update_frame(self, image):
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(
            self.video_label.width(), 
            self.video_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)

    def speak_response(self, response):
        """
        Diese Methode wurde deaktiviert, da die Sprachausgabe entfernt wurde.
        Sie bleibt als leere Methode erhalten, um mit dem Signal response_complete kompatibel zu sein.
        """
        # Sprachausgabe deaktiviert
        pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()
            
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            delta = QPoint(event.globalPos() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide_and_stop_listening()
        super().keyPressEvent(event)

    def showEvent(self, event):
        """Called when window is shown"""
        self.worker.activate_hardware()
        super().showEvent(event)

    def hideEvent(self, event):
        """Called when window is hidden"""
        self.worker.deactivate_hardware()
        super().hideEvent(event)

    def closeEvent(self, event):
        # Just hide instead of close when the X is clicked
        if self.tray_icon.isVisible():
            self.hide_and_stop_listening()
            event.ignore()
        else:
            self.quit_app()
            event.accept()

    def quit_app(self):
        self.worker.stop()
        QApplication.quit()

    def on_tray_icon_activated(self, reason):
        """Handle activation of the tray icon"""
        if reason == QSystemTrayIcon.Trigger:  # Click on the icon
            if self.isVisible():
                self.hide_and_stop_listening()
            else:
                self.force_show_window()