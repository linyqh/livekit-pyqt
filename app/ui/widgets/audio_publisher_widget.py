import os
import asyncio
import traceback
from PyQt5.QtCore import Qt, QUrl, QBuffer, QIODevice
from PyQt5.QtWidgets import QVBoxLayout, QWidget, QLabel, QPushButton
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from qfluentwidgets import CardWidget, BodyLabel, PushButton, InfoBar, InfoBarPosition
from livekit.rtc import LocalAudioTrack, TrackPublishOptions, AudioSource, TrackSource, ChatManager, AudioFrame
from app.utils.logger import logger
from pydub import AudioSegment
import numpy as np


class AudioPublisherWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.audio_track = None
        self.room_connected = False
        self.media_player = QMediaPlayer()
        self.media_player.stateChanged.connect(self.on_media_state_changed)
        self.audio_buffer = QBuffer()
        self.is_publishing = False
        self.chat_manager = None
        self.current_room = None  # 添加这行

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignTop)

        self.title_label = BodyLabel('发布音频文件', self)
        self.title_label.setObjectName('titleLabel')

        self.status_card = CardWidget(self)
        self.status_layout = QVBoxLayout(self.status_card)
        self.status_label = QLabel("未连接到房间", self)
        self.status_layout.addWidget(self.status_label)

        self.publish_button = PushButton('发布音频', self)
        self.publish_button.clicked.connect(self.publish_audio)
        self.publish_button.setEnabled(False)

        layout.addWidget(self.title_label)
        layout.addWidget(self.status_card)
        layout.addWidget(self.publish_button)

    def update_room_status(self, connected, room=None):
        self.room_connected = connected
        if connected:
            self.status_label.setText("已连接到房间")
            self.publish_button.setEnabled(True)
            self.current_room = room  # 存储 room 对象
            if room:
                self.chat_manager = ChatManager(room)
        else:
            self.status_label.setText("未连接到房间")
            self.publish_button.setEnabled(False)
            self.chat_manager = None
            self.current_room = None  # 清除 room 对象
            if self.audio_track:
                asyncio.create_task(self.unpublish_audio())

    def publish_audio(self):
        asyncio.create_task(self.async_publish_audio())

    async def async_publish_audio(self):
        if not self.room_connected or not self.current_room:
            self.show_info_bar("错误", "未连接到房间", InfoBarPosition.TOP, duration=3000, style='error')
            return

        if self.is_publishing:
            await self.unpublish_audio()
            return

        try:
            # 发送测试消息
            await self.chat_manager.send_message("测试连接")
            self.show_info_bar("成功", "已发送测试消息", InfoBarPosition.TOP)

            audio_file = os.path.join('app', 'test.mp3')
            if not os.path.exists(audio_file):
                raise FileNotFoundError(f"音频文件不存在: {audio_file}")

            # 读取音频文件
            audio = AudioSegment.from_mp3(audio_file)
            audio = audio.set_channels(1).set_frame_rate(48000)  # 转换为单声道和48kHz采样率
            self.audio_buffer = QBuffer(self)
            self.audio_buffer.open(QIODevice.ReadWrite)
            self.audio_buffer.write(audio.raw_data)
            self.audio_buffer.seek(0)

            # 创建音频源和轨道
            self.audio_source = AudioSource(sample_rate=48000, num_channels=1)  # 提供必需的参数
            self.audio_track = LocalAudioTrack.create_audio_track("file_audio", source=self.audio_source)

            # 发布音频轨道
            options = TrackPublishOptions()
            options.source = TrackSource.SOURCE_MICROPHONE
            await self.current_room.local_participant.publish_track(self.audio_track, options)

            # 开始播放音频
            self.is_publishing = True
            self.publish_button.setText("停止发布")
            asyncio.create_task(self.stream_audio())

            self.show_info_bar("成功", "音频文件已发布到房间并开始播放", InfoBarPosition.TOP)
        except Exception as e:
            logger.error(f"发布音频文件失败: \n{traceback.format_exc()}")
            self.show_info_bar("错误", f"发布音频文件失败: {str(e)}", InfoBarPosition.TOP, duration=3000, style='error')

    async def stream_audio(self):
        chunk_size = 960  # 20ms at 48kHz
        while self.is_publishing:
            chunk = self.audio_buffer.read(chunk_size * 2)  # 16-bit audio, so 2 bytes per sample
            if not chunk:
                self.audio_buffer.seek(0)
                chunk = self.audio_buffer.read(chunk_size * 2)
            if chunk:
                # 将字节数据转换为 numpy 数组
                audio_data = np.frombuffer(chunk, dtype=np.int16)
                # 创建 AudioFrame 对象
                frame = AudioFrame(
                    data=audio_data,
                    samples_per_channel=chunk_size,
                    sample_rate=48000,
                    num_channels=1  # 使用 num_channels 替代 number_of_channels
                )
                await self.audio_source.capture_frame(frame)
            await asyncio.sleep(0.02)  # 20ms

    async def unpublish_audio(self):
        self.is_publishing = False
        if self.audio_track:
            try:
                main_window = self.window()
                room = main_window.get_current_room()
                if room:
                    await room.local_participant.unpublish_track(self.audio_track)
                self.audio_track = None
                self.audio_source = None
                if self.audio_buffer:
                    self.audio_buffer.close()
                    self.audio_buffer = None
                self.publish_button.setText("发布音频")
                self.show_info_bar("信息", "音频文件已从房间中移除", InfoBarPosition.TOP)
            except Exception as e:
                logger.error(f"取消发布音频文件失败: \n{traceback.format_exc()}")
                self.show_info_bar("错误", f"取消发布音频文件失败: {str(e)}", InfoBarPosition.TOP, duration=3000, style='error')

    def on_media_state_changed(self, state):
        if state == QMediaPlayer.StoppedState and self.is_publishing:
            asyncio.create_task(self.unpublish_audio())

    def show_info_bar(self, title, content, position, duration=2000, style='success'):
        if style == 'error':
            InfoBar.error(
                title=title,
                content=content,
                orient=Qt.Horizontal,
                isClosable=True,
                position=position,
                duration=duration,
                parent=self
            )
        else:
            InfoBar.success(
                title=title,
                content=content,
                orient=Qt.Horizontal,
                isClosable=True,
                position=position,
                duration=duration,
                parent=self
            )