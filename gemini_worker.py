"""
Worker class for handling Gemini API interactions.
"""

import asyncio
import base64
import io
import traceback
import cv2
import PIL.Image
import mss
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage

from config import (
    get_or_create_client, MODEL, CONFIG, DEFAULT_MODE, 
    FORMAT, CHANNELS, SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE, CHUNK_SIZE, pya
)

class GeminiWorker(QThread):
    text_update = pyqtSignal(str)
    new_message = pyqtSignal()  # Signal to indicate a new message/response is starting
    frame_update = pyqtSignal(QImage)
    response_complete = pyqtSignal(str)  # Signal for when a complete response is ready
    api_key_required = pyqtSignal()  # Neues Signal für fehlenden API Key
    
    def __init__(self, video_mode=DEFAULT_MODE, api_key=None):
        super().__init__()
        self.video_mode = video_mode
        self.api_key = api_key
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
        
        # Track current response
        self.current_response = ""
        self.response_in_progress = False
        
    def run(self):
        asyncio.run(self.run_async())
        
    async def run_async(self):
        try:
            # Stelle sicher, dass wir einen Client haben
            client = get_or_create_client(self.api_key)
            
            # Der Client hat keinen direkten API-Key-Zugriff
            # Prüfen wir stattdessen, ob ein API-Key für diesen Worker vorhanden ist
            if not self.api_key:
                self.text_update.emit("Kein API-Key konfiguriert. Bitte konfigurieren Sie einen API-Key in den Einstellungen.")
                self.api_key_required.emit()
                return
            
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
        except ValueError as e:
            if "Missing key inputs" in str(e):
                self.text_update.emit("Kein gültiger API-Key konfiguriert. Bitte überprüfen Sie Ihren API-Key in den Einstellungen.")
                self.api_key_required.emit()
            else:
                self.text_update.emit(f"Fehler: {str(e)}")
                traceback.print_exc()
        except Exception as e:
            self.text_update.emit(f"Error: {str(e)}")
            traceback.print_exc()
        finally:
            if self.audio_stream:
                self.audio_stream.close()
                
    def update_api_key(self, api_key):
        """API-Key aktualisieren und Worker neu starten, wenn nötig"""
        self.api_key = api_key
        
        # Wenn der Worker läuft und ein API-Key gesetzt wird, starten wir neu
        if self.running and self.isRunning():
            self.stop()
            self.start()

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
            # Reset the current response for this turn
            self.current_response = ""
            self.response_in_progress = True
            
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    self.text_update.emit(text)
                    # Accumulate the full response text
                    self.current_response += text

            # End of turn reached - signal that the response is complete
            if self.current_response:
                self.response_complete.emit(self.current_response)
            
            self.response_in_progress = False
            
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