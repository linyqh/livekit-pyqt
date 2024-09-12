import traceback
import pyaudio
import numpy as np
import asyncio
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QScrollArea, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QColor
from PyQt5.QtMultimedia import QAudioOutput, QAudioFormat
from PyQt5.QtMultimediaWidgets import QVideoWidget
from qfluentwidgets import (CardWidget, TitleLabel, SubtitleLabel, BodyLabel, 
                            ScrollArea, PushButton, FluentIcon, Theme, setTheme, 
                            setThemeColor, isDarkTheme)

from livekit import rtc
from app.utils.logger import logger
import os
import wave
import cv2
import sounddevice as sd
import queue
import threading
import ctypes
import datetime

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 48000

class SubscribedTracksWidget(QWidget):
    play_track_signal = pyqtSignal(str, str)
    record_track_signal = pyqtSignal(str, str)
    stop_track_signal = pyqtSignal(str, str)  # 新增停止信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.tracks = {}
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.audio_output = None
        self.audio_buffer = None
        self.audio_queue = queue.Queue(maxsize=10)
        self.audio_thread = None
        self.is_playing = False
        self.video_playing = {}  # 用于跟踪每个视频流的播放状态

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(24)

        # 设置简单的背景色
        self.setStyleSheet("""
            QWidget {
                background-color: #2B2B2B;
                color: white;
            }
        """)

        # 标题
        title = TitleLabel("已订阅的轨道", self)
        title.setObjectName("subscribeTitle")
        layout.addWidget(title)

        # 副标题
        subtitle = SubtitleLabel("在这里查看和管理已订阅的音视频轨道", self)
        subtitle.setObjectName("subscribeSubtitle")
        layout.addWidget(subtitle)

        # 滚动区域
        scroll_area = ScrollArea(self)
        content_widget = QWidget()
        self.tracks_grid = QGridLayout(content_widget)
        self.tracks_grid.setSpacing(20)
        scroll_area.setWidget(content_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

    def add_track(self, participant, track_id, track_type):
        if track_id in self.tracks:
            return

        row = self.tracks_grid.rowCount()

        track_card = CardWidget(self)
        card_layout = QVBoxLayout(track_card)
        card_layout.setSpacing(12)

        # 参与者信息
        participant_label = SubtitleLabel(f"参与者: {participant}", self)
        card_layout.addWidget(participant_label)

        # 轨道信息
        track_info = BodyLabel(f"轨道ID: {track_id}\n类型: {track_type}", self)
        card_layout.addWidget(track_info)

        if track_type == "Video":
            video_label = QLabel(self)
            video_label.setAlignment(Qt.AlignCenter)
            video_label.setMinimumSize(320, 240)
            card_layout.addWidget(video_label)
            self.tracks[track_id] = {'card': track_card, 'video_label': video_label}
        elif track_type == "Audio":
            audio_label = BodyLabel("音频轨道", self)
            card_layout.addWidget(audio_label)
            self.tracks[track_id] = {'card': track_card, 'audio_label': audio_label}

        # 按钮布局
        button_layout = QHBoxLayout()
        play_button = PushButton("播放直播", self, FluentIcon.PLAY)
        play_button.clicked.connect(lambda: self.play_track_signal.emit(track_id, track_type))
        stop_button = PushButton("停止播放", self, FluentIcon.STOP_WATCH)  # 新增停止按钮
        stop_button.clicked.connect(lambda: self.stop_track_signal.emit(track_id, track_type))
        record_button = PushButton("录制存储", self, FluentIcon.SAVE)
        record_button.clicked.connect(lambda: self.record_track_signal.emit(track_id, track_type))

        button_layout.addWidget(play_button)
        button_layout.addWidget(stop_button)  # 添加停止按钮到布局
        button_layout.addWidget(record_button)
        card_layout.addLayout(button_layout)

        self.tracks_grid.addWidget(track_card, row, 0)

    def remove_track(self, track_id):
        if track_id in self.tracks:
            track_card = self.tracks[track_id]
            self.tracks_grid.removeWidget(track_card)
            track_card.deleteLater()
            del self.tracks[track_id]

    def update_track_status(self, track_id, status):
        if track_id in self.tracks:
            track_card = self.tracks[track_id]
            info_label = track_card.findChild(QLabel)
            if info_label:
                current_text = info_label.text()
                new_text = current_text + f"\n状态: {status}"
                info_label.setText(new_text)

    async def play_audio_stream(self, audio_stream):
        try:
            self.is_playing = True
            self.audio_thread = threading.Thread(target=self._audio_playback_thread)
            self.audio_thread.start()

            async for frame_event in audio_stream:
                audio_frame = frame_event.frame
                audio_data = audio_frame.data

                if isinstance(audio_data, memoryview):
                    audio_data = np.frombuffer(audio_data, dtype=np.int16)
                elif isinstance(audio_data, np.ndarray):
                    audio_data = audio_data.astype(np.int16)
                else:
                    audio_data = np.frombuffer(audio_data, dtype=np.int16)

                self.audio_queue.put(audio_data)
                await asyncio.sleep(0)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"播放音频时发生错误: {traceback.format_exc()}")
        finally:
            self.is_playing = False
            if self.audio_thread:
                self.audio_thread.join()
            await audio_stream.aclose()

    async def play_video_stream(self, video_stream):
        try:
            async for frame_event in video_stream:
                buffer = frame_event.frame

                # 将视频帧转换为 numpy 数组
                arr = np.frombuffer(buffer.data, dtype=np.uint8)
                arr = arr.reshape((buffer.height, buffer.width, 3))

                # 将 RGB 转换为 BGR（OpenCV 使用 BGR 格式）
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

                # 将 numpy 数组转换为 QImage
                height, width, channel = arr.shape
                bytes_per_line = 3 * width
                q_img = QImage(arr.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()

                # 将 QImage 转换为 QPixmap 并设置到 QLabel
                pixmap = QPixmap.fromImage(q_img)
                video_label = self.tracks[video_stream._track.sid]['video_label']
                video_label.setPixmap(pixmap.scaled(video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

                # 给 Qt 事件循环一些时间来更新 UI
                await asyncio.sleep(0.01)  # 增加一个小的延迟以避免UI卡顿

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"播放视频时发生错误: \n{traceback.format_exc()}")
        finally:
            await video_stream.aclose()


    async def record_audio_stream(self, audio_stream: rtc.AudioStream, track_id):
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audio_{track_id}_{timestamp}.wav"
            filepath = os.path.join("recorded_audio", filename)
            os.makedirs("recorded_audio", exist_ok=True)

            with wave.open(filepath, 'wb') as wav_file:
                wav_file.setnchannels(1)  # 假设为单声道
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(48000)  # 假设采样率为 48kHz

                async for audio_frame_event in audio_stream:
                    audio_frame = audio_frame_event.frame
                    audio_data = audio_frame.data

                    if isinstance(audio_data, memoryview):
                        audio_data = audio_data.tobytes()
                    elif isinstance(audio_data, np.ndarray):
                        audio_data = audio_data.astype(np.int16).tobytes()

                    wav_file.writeframes(audio_data)

            logger.info(f"音频已录制并保存到 {filepath}")

        except asyncio.CancelledError:
            logger.info("频录制已取消")
        except Exception as e:
            logger.error(f"录制音频时发生错误: \n{traceback.format_exc()}")
        finally:
            await audio_stream.aclose()

    async def record_video_stream(self, video_stream, track_id):
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"video_{track_id}_{timestamp}.mp4"
            filepath = os.path.join("recorded_video", filename)
            os.makedirs("recorded_video", exist_ok=True)

            # 这里应该添加视频录制的逻辑
            # 例如，如果使用 OpenCV：
            # fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            # out = cv2.VideoWriter(filepath, fourcc, 30.0, (frame_width, frame_height))

            async for video_frame_event in video_stream:
                video_frame = video_frame_event.frame
                # 这里应该添加将视频帧写入文件的逻辑
                # 例如，如果使用 OpenCV：
                # out.write(video_frame.to_ndarray())
                logger.info(f"录制视频帧: {video_frame}")

            logger.info(f"视频已录制并保存到 {filepath}")

        except asyncio.CancelledError:
            logger.info("视频录制已取消")
        except Exception as e:
            logger.error(f"录制视频时发生错误: \n{traceback.format_exc()}")
        finally:
            # 如果使用了 OpenCV 的 VideoWriter，应该在这里释放：
            # out.release()
            await video_stream.aclose()

    async def stop_audio_stream(self):
        self.is_playing = False
        if self.audio_thread:
            self.audio_thread.join()
        self.audio_queue.queue.clear()
        logger.info("音频流已停止")

    async def stop_video_stream(self, video_stream):
        try:
            track_id = video_stream._track.sid if video_stream else None
            if track_id:
                self.video_playing[track_id] = False
            if video_stream:
                await video_stream.aclose()
            if track_id in self.tracks:
                video_label = self.tracks[track_id]['video_label']
                video_label.clear()  # 清除视频标签的内容
                video_label.setText("视频已停止")  # 添加一个文本提示
            logger.info(f"视频流已停止: {track_id}")
        except Exception as e:
            logger.error(f"停止视频流时发生错误: {str(e)}")
            logger.error(traceback.format_exc())

    def pause_audio(self):
        if self.audio_output:
            self.audio_output.suspend()

    def resume_audio(self):
        if self.audio_output:
            self.audio_output.resume()

    def set_audio_volume(self, volume):
        if self.audio_output:
            self.audio_output.setVolume(volume)

    def _audio_playback_thread(self):
        with sd.OutputStream(samplerate=RATE, channels=CHANNELS, dtype='int16') as stream:
            while self.is_playing:
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.1)
                    stream.write(audio_chunk)
                except queue.Empty:
                    continue

    def closeEvent(self, event):
        self.is_playing = False
        if self.audio_thread:
            self.audio_thread.join()
        super().closeEvent(event)

    def __del__(self):
        try:
            self.is_playing = False
            if hasattr(self, 'audio_thread') and self.audio_thread:
                self.audio_thread.join()
            if hasattr(self, 'p') and self.p:
                self.p.terminate()
        except:
            pass  # 忽略在删除过程中可能发生的任何错误
