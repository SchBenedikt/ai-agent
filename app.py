"""
## Documentation
Quickstart: https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_LiveAPI.py

## Setup

To install the dependencies for this script, run:

```
pip install google-genai opencv-python pyaudio pillow mss PyQt5 py2app pynput
```
"""

import asyncio
import base64
import io
import traceback
import sys
import os

import cv2
import pyaudio
import PIL.Image
import mss

import argparse
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton, 
                            QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, 
                            QSystemTrayIcon, QMenu, QAction, QStyle, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QPoint, QRect, QDateTime
from PyQt5.QtGui import QPixmap, QImage, QIcon, QCursor, QPalette, QTextCursor

from pynput import keyboard

from google import genai
from google.genai import types

# Get API key from environment or ask user
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

MODEL = "models/gemini-2.0-flash-exp"

DEFAULT_MODE = "camera"

# Initialize client with API key
client = genai.Client(http_options={"api_version": "v1alpha"}, api_key=GEMINI_API_KEY)

tools = [
    types.Tool(google_search=types.GoogleSearch()),
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="getWeather",
                description="gets the weather for a requested city",
                parameters=genai.types.Schema(
                        type = genai.types.Type.OBJECT,
                        properties = {
                            "city": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                        },
                    ),
            ),
        ]
    ),
]

CONFIG = types.LiveConnectConfig(
    response_modalities=[
        "text",
    ],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
        )
    ),
    tools=tools,
)

pya = pyaudio.PyAudio()

# Global hotkey combination
HOTKEY_COMBINATION = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.Key.space}
current_keys = set()

class GeminiWorker(QThread):
    text_update = pyqtSignal(str)
    new_message = pyqtSignal()  # New signal to indicate a new message/response is starting
    frame_update = pyqtSignal(QImage)
    
    def __init__(self, video_mode=DEFAULT_MODE):
        super().__init__()
        self.video_mode = video_mode
        self.audio_in_queue = asyncio.Queue()
        self.out_queue = asyncio.Queue(maxsize=5)
        self.session = None
        self.audio_stream = None
        self.running = True
        self.listening = False
        self.current_question = ""
        
        # Add flags to control hardware access
        self.camera_active = False
        self.mic_active = False
        self.cap = None  # Store camera object
        
    def run(self):
        asyncio.run(self.run_async())
        
    async def run_async(self):
        try:
            async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
                self.session = session
                
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self.send_realtime())
                    tg.create_task(self.listen_audio())
                    
                    if self.video_mode == "camera":
                        tg.create_task(self.get_frames())
                    elif self.video_mode == "screen":
                        tg.create_task(self.get_screen())
                        
                    tg.create_task(self.receive_audio())
                    tg.create_task(self.play_audio())
                    
                    # Let the tasks run until the thread is stopped
                    while self.running:
                        await asyncio.sleep(0.1)
                    
                    raise asyncio.CancelledError("User requested exit")
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.text_update.emit(f"Error: {str(e)}")
            traceback.print_exc()
        finally:
            if self.audio_stream:
                self.audio_stream.close()

    def _get_frame(self, cap):
        ret, frame = cap.read()
        if not ret:
            return None
            
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        qt_img = QImage(frame_rgb.data, w, h, w * ch, QImage.Format_RGB888)
        self.frame_update.emit(qt_img)
        
        # Resize the image to be smaller to save bandwidth
        img = PIL.Image.fromarray(frame_rgb)
        img.thumbnail([512, 512])  # Smaller size for API

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        mime_type = "image/jpeg"
        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_frames(self):
        while self.running:
            if self.camera_active:
                # Only open the camera if it's not already open
                if self.cap is None or not self.cap.isOpened():
                    self.cap = await asyncio.to_thread(cv2.VideoCapture, 0)
                
                frame = await asyncio.to_thread(self._get_frame, self.cap)
                if frame is None:
                    # Camera error - release and try again next loop
                    if self.cap:
                        await asyncio.to_thread(self.cap.release)
                        self.cap = None
                    await asyncio.sleep(1.0)
                    continue

                if self.listening:
                    await self.out_queue.put(frame)
            else:
                # Release camera when not active
                if self.cap is not None and self.cap.isOpened():
                    await asyncio.to_thread(self.cap.release)
                    self.cap = None
                
            await asyncio.sleep(0.2)  # Maintain reasonable frame rate

        # Clean up
        if self.cap is not None:
            self.cap.release()

    def _get_screen(self):
        sct = mss.mss()
        monitor = sct.monitors[0]

        i = sct.grab(monitor)

        mime_type = "image/jpeg"
        image_bytes = mss.tools.to_png(i.rgb, i.size)
        img = PIL.Image.open(io.BytesIO(image_bytes))

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_screen(self):
        while self.running:
            frame = await asyncio.to_thread(self._get_screen)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            if self.listening:
                await self.out_queue.put(frame)

    async def send_realtime(self):
        while self.running:
            msg = await self.out_queue.get()
            await self.session.send(input=msg)
    
    def send_question(self, question):
        self.current_question = question
        asyncio.create_task(self.send_question_async(question))
        
    async def send_question_async(self, question):
        if self.session:
            await self.session.send(input=question, end_of_turn=True)

    async def listen_audio(self):
        while self.running:
            if self.mic_active:
                # Only open the microphone if it's not already open
                if self.audio_stream is None or not self.audio_stream.is_active():
                    mic_info = pya.get_default_input_device_info()
                    self.audio_stream = await asyncio.to_thread(
                        pya.open,
                        format=FORMAT,
                        channels=CHANNELS,
                        rate=SEND_SAMPLE_RATE,
                        input=True,
                        input_device_index=mic_info["index"],
                        frames_per_buffer=CHUNK_SIZE,
                    )
                
                kwargs = {"exception_on_overflow": False}
                try:
                    data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
                    if self.listening:
                        await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
                except:
                    # Error with audio - close and retry
                    if self.audio_stream:
                        self.audio_stream.close()
                        self.audio_stream = None
            else:
                # Close microphone when not active
                if self.audio_stream is not None:
                    self.audio_stream.close()
                    self.audio_stream = None
                await asyncio.sleep(0.5)
                
            if not self.mic_active:
                await asyncio.sleep(0.5)  # Don't busy-wait when mic is off

    async def receive_audio(self):
        while self.running:
            turn = self.session.receive()
            # Signal that a new message is starting
            self.new_message.emit()
            
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    self.text_update.emit(text)

            # Clear audio queue for interruptions
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        
        while self.running:
            try:
                bytestream = await self.audio_in_queue.get()
                await asyncio.to_thread(stream.write, bytestream)
            except Exception as e:
                self.text_update.emit(f"Audio playback error: {str(e)}")
    
    def activate_hardware(self):
        """Activate camera and microphone access"""
        self.camera_active = True
        self.mic_active = True
    
    def deactivate_hardware(self):
        """Stop camera and microphone access"""
        self.camera_active = False
        self.mic_active = False
    
    def stop(self):
        self.running = False
        self.deactivate_hardware()


class CompactGeminiAppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemini")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
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
        
        # Initialize Gemini worker
        self.worker = GeminiWorker(video_mode="camera")
        self.worker.text_update.connect(self.update_response)
        self.worker.new_message.connect(self.prepare_new_message)
        self.worker.frame_update.connect(self.update_frame)
        self.worker.start()
        
        # Add a flag to track if this is a new message
        self.is_new_message = True
        
        # Setup system tray
        self.setup_tray()
        self.hide()  # Start hidden
        
        # Update UI state
        self.update_ui_listening_state(False)

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

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Try to get a better icon - using a speech bubble icon if available
        icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation)
        self.tray_icon.setIcon(icon)
        
        # Create tray menu with macOS-friendly styling
        self.tray_menu = QMenu()  # Store reference as instance variable
        
        # Apply styling suitable for macOS menu bar
        if sys.platform == "darwin":
            self.tray_menu.setStyleSheet("""
                QMenu {
                    background-color: white;
                    border: 1px solid #cccccc;
                }
                QMenu::item {
                    background-color: transparent;
                    padding: 5px 12px 5px 12px;
                    color: black;
                }
                QMenu::item:selected {
                    background-color: #3778c0;
                    color: white;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #cccccc;
                    margin: 5px 2px 5px 2px;
                }
            """)
        
        # Create actions and explicitly set them as enabled
        show_action = QAction("Open Gemini", self)
        show_action.triggered.connect(self.force_show_window)
        show_action.setEnabled(True)
        self.tray_menu.addAction(show_action)
        
        theme_action = QAction("Toggle Theme", self)
        theme_action.triggered.connect(self.toggle_theme)
        theme_action.setEnabled(True)
        self.tray_menu.addAction(theme_action)
        
        self.tray_menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        quit_action.setEnabled(True)
        self.tray_menu.addAction(quit_action)
        
        # Set the menu and make it accessible
        self.tray_icon.setContextMenu(self.tray_menu)
        
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

    def on_tray_icon_activated(self, reason):
        """Handle activation of the tray icon"""
        if reason == QSystemTrayIcon.Trigger:  # Click on the icon
            if self.isVisible():
                self.hide_and_stop_listening()
            else:
                self.force_show_window()

    def toggle_theme(self):
        """Toggle between light and dark themes"""
        self.is_dark_mode = not self.is_dark_mode
        main_widget = self.centralWidget()
        self.apply_theme(main_widget)
        
        # Update close button style
        if hasattr(self, 'close_button'):
            self.close_button.setStyleSheet(self.close_button_style)
        
        # Update indicator colors based on the current listening state
        self.update_ui_listening_state(self.worker.listening)

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

def on_press(key):
    try:
        current_keys.add(key)
        if all(k in current_keys for k in HOTKEY_COMBINATION):
            # Show the app window when hotkey is pressed
            if window.isVisible():
                window.hide_and_stop_listening()
            else:
                window.force_show_window()
    except:
        pass

def on_release(key):
    try:
        current_keys.discard(key)
    except:
        pass

if __name__ == "__main__":
    # Set Qt attributes before creating QApplication
    if sys.platform == "darwin":  # macOS specific
        QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_MacPluginApplication, True)
    
    # Initialize QApplication
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running when window is closed
    
    try:
        # For macOS: Hide the dock icon properly using PyObjC
        if sys.platform == "darwin":
            try:
                # Try PyObjC approach:
                from Foundation import NSBundle
                info = NSBundle.mainBundle().infoDictionary()
                info["LSBackgroundOnly"] = "1"
                
                # Additional approach - more radical
                import objc
                from AppKit import NSApplication
                NSApplication.sharedApplication().setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory
            except ImportError:
                # If PyObjC is not available, we already used Qt approach as fallback
                pass
        
        # Check API key
        if not GEMINI_API_KEY:
            from PyQt5.QtWidgets import QInputDialog
            GEMINI_API_KEY, ok = QInputDialog.getText(
                None, 
                "Gemini API Key", 
                "Enter your Gemini API Key:", 
                echo=QInputDialog.Password
            )
            if not ok or not GEMINI_API_KEY:
                sys.exit(1)
            client = genai.Client(http_options={"api_version": "v1alpha"}, api_key=GEMINI_API_KEY)
        
        # Create main window
        window = CompactGeminiAppWindow()
        
        # Setup global hotkey listener
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        
        # Start event loop
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
