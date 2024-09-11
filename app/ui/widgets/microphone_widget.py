import traceback
import asyncio

from PyQt5.QtCore import Qt, QTimer, QUrl, QSize
from PyQt5.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout, QLabel
from PyQt5.QtMultimedia import QAudioRecorder, QMediaPlayer, QMediaContent, QAudioEncoderSettings, QMultimedia
from qfluentwidgets import (SwitchButton, ProgressBar, PushButton, ComboBox, Slider, InfoBar, InfoBarPosition,
                            BodyLabel, CardWidget, FlowLayout, IconWidget, Theme, toggleTheme, setTheme)
from qfluentwidgets import FluentIcon as FIF
import tempfile
import os
from app.utils.logger import logger
from livekit.rtc import LocalAudioTrack, TrackPublishOptions, AudioSource, TrackSource

class MicrophoneWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_audio_recorder()  # 移到这里
        self.setup_ui()
        self.init_microphone()
        self.init_media_player()
        self.room_connected = False
        self.audio_track = None  # 新增：用于存储创建的音频 track
        setTheme(Theme.DARK)  # 设置深色主题，您可以根据需要更改

        # 打印所有可用的 FluentIcon
        # print("Available FluentIcons:")
        # for icon in FIF:
        #     print(icon.name)

    def setup_ui(self):
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(36, 36, 36, 36)
        self.vBoxLayout.setSpacing(20)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

        self.setup_title()
        self.setup_connection_status()
        self.setup_microphone_controls()
        self.setup_recording_controls()

    def setup_title(self):
        self.titleLabel = BodyLabel('麦克风设置', self)
        self.titleLabel.setObjectName('titleLabel')
        self.titleLabel.setStyleSheet("color: white; font-size: 24px;")  # 设置标题颜色和大小
        self.vBoxLayout.addWidget(self.titleLabel)

    def setup_connection_status(self):
        self.connectionCard = CardWidget(self)
        self.connectionLayout = QHBoxLayout(self.connectionCard)
        self.connectionStatusIcon = IconWidget(FIF.LINK, self)  # 使用 LINK 图标
        self.connectionStatusIcon.setFixedSize(24, 24)  # 设置图标大小
        self.connectionStatusLabel = QLabel("未连接到房间", self)
        self.connectionStatusLabel.setStyleSheet("color: white;")  # 设置标签颜色
        self.connectionLayout.addWidget(self.connectionStatusIcon)
        self.connectionLayout.addWidget(self.connectionStatusLabel)
        self.vBoxLayout.addWidget(self.connectionCard)

    def setup_microphone_controls(self):
        self.microphoneCard = CardWidget(self)
        self.microphoneLayout = QVBoxLayout(self.microphoneCard)

        self.mic_switch = SwitchButton('麦克风')
        self.mic_switch.checkedChanged.connect(self.toggle_microphone)
        self.mic_switch.setStyleSheet("color: white;")  # 设置开关文字颜色

        self.input_device_combo = ComboBox()
        self.input_device_combo.addItems(self.get_input_devices())
        self.input_device_combo.currentIndexChanged.connect(self.change_input_device)
        self.input_device_combo.setStyleSheet("color: white;")  # 设置下拉框文字颜色

        self.volume_slider = Slider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.change_volume)

        self.volume_bar = ProgressBar()
        self.volume_bar.setRange(0, 100)

        self.microphoneLayout.addWidget(self.mic_switch)
        self.microphoneLayout.addWidget(self.input_device_combo)
        self.microphoneLayout.addWidget(self.volume_slider)
        self.microphoneLayout.addWidget(self.volume_bar)

        self.vBoxLayout.addWidget(self.microphoneCard)

    def setup_recording_controls(self):
        self.recordingCard = CardWidget(self)
        self.recordingLayout = QHBoxLayout(self.recordingCard)

        self.record_button = PushButton('录制')
        self.record_button.setIcon(FIF.MICROPHONE)  # 使用 MICROPHONE 图标
        self.record_button.setIconSize(QSize(20, 20))  # 设置图标大小
        self.record_button.clicked.connect(self.toggle_recording)

        self.play_button = PushButton('播放')
        self.play_button.setIcon(FIF.PLAY)  # 保持 PLAY 图标不变
        self.play_button.setIconSize(QSize(20, 20))  # 设置图标大小
        self.play_button.clicked.connect(self.play_audio)
        self.play_button.setEnabled(False)

        self.recordingLayout.addWidget(self.record_button)
        self.recordingLayout.addWidget(self.play_button)

        self.vBoxLayout.addWidget(self.recordingCard)

    def init_microphone(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_volume)

    def init_audio_recorder(self):
        self.audio_recorder = QAudioRecorder()
        self.is_recording = False
        self.recorded_file = None
        
        # 设置音频编码
        settings = QAudioEncoderSettings()
        settings.setCodec("audio/pcm")
        settings.setSampleRate(44100)
        settings.setBitRate(16)
        settings.setChannelCount(1)
        settings.setQuality(QMultimedia.HighQuality)
        self.audio_recorder.setEncodingSettings(settings)

    def init_media_player(self):
        self.media_player = QMediaPlayer()

    def get_input_devices(self):
        return self.audio_recorder.audioInputs()

    def change_input_device(self, index):
        device_name = self.input_device_combo.itemText(index)
        self.audio_recorder.setAudioInput(device_name)

    def change_volume(self, value):
        self.audio_recorder.setVolume(value / 100)

    def toggle_microphone(self, checked):
        if checked:
            self.start_microphone()
            if self.room_connected and self.audio_track:
                asyncio.create_task(self._enable_audio_track())
        else:
            self.stop_microphone()
            if self.audio_track:
                asyncio.create_task(self._disable_audio_track())

    def start_microphone(self):
        self.timer.start(100)  # 更新音量显示的频率

    def stop_microphone(self):
        self.timer.stop()
        self.volume_bar.setValue(0)

    def update_volume(self):
        # 使用随机值模拟音量
        import random
        volume = random.randint(0, 100)
        self.volume_bar.setValue(volume)

    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self.recorded_file = tempfile.mktemp(suffix='.wav')
        self.audio_recorder.setOutputLocation(QUrl.fromLocalFile(self.recorded_file))
        self.audio_recorder.record()
        self.is_recording = True
        self.record_button.setText('停止录制')
        self.record_button.setIcon(FIF.CANCEL)  # 使用 CANCEL 图标替代 STOP
        self.record_button.setIconSize(QSize(20, 20))  # 设置图标大小
        self.play_button.setEnabled(False)

    def stop_recording(self):
        self.audio_recorder.stop()
        self.is_recording = False
        self.record_button.setText('录制')
        self.record_button.setIcon(FIF.MICROPHONE)  # 恢复使用 MICROPHONE 图标
        self.record_button.setIconSize(QSize(20, 20))  # 设置图标大小
        self.play_button.setEnabled(True)

    def play_audio(self):
        if self.recorded_file and os.path.exists(self.recorded_file):
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(self.recorded_file)))
            self.media_player.play()

    def update_room_status(self, connected):
        self.room_connected = connected
        if connected:
            self.connectionStatusLabel.setText("已连接到房间")
            self.connectionStatusIcon.setIcon(FIF.LINK)
            self.create_and_publish_audio_track()  # 新增：创建并发布音频 track
        else:
            self.connectionStatusLabel.setText("未连接到房间")
            self.connectionStatusIcon.setIcon(FIF.CANCEL)  # 使用 CANCEL 图标替代 LINK_OFF
            self.unpublish_audio_track()  # 新增：取消发布音频 track
        self.connectionStatusIcon.setFixedSize(24, 24)  # 重新设置图标大小

    def create_and_publish_audio_track(self):
        if self.room_connected and not self.audio_track:
            asyncio.create_task(self._async_create_and_publish_audio_track())

    async def _async_create_and_publish_audio_track(self):
        try:
            # 创建音频源
            audio_source = AudioSource(48000, 1)
            
            # 创建音频 track
            self.audio_track = LocalAudioTrack.create_audio_track("microphone", source=audio_source)
            
            # 获取当前房间对象
            main_window = self.window()
            if hasattr(main_window, 'get_current_room'):
                room = main_window.get_current_room()
            else:
                raise AttributeError("无法找到 get_current_room 方法")
            
            if room:
                # 发布音频 track
                options = TrackPublishOptions()
                options.source = TrackSource.SOURCE_MICROPHONE
                await room.local_participant.publish_track(self.audio_track, options)
                self.show_info_bar("成功", "麦克风音频已发布到房间", InfoBarPosition.TOP)
            else:
                self.show_info_bar("错误", "无法获取当前房间", InfoBarPosition.TOP, duration=3000, style='error')
        except Exception as e:
            logger.error(f"创建或发布音频 track 失败: \n{traceback.format_exc()}")
            self.show_info_bar("错误", f"创建或发布音频 track 失败: {str(e)}", InfoBarPosition.TOP, duration=3000, style='error')

    def unpublish_audio_track(self):
        if self.audio_track:
            try:
                main_window = self.window()
                if hasattr(main_window, 'get_current_room'):
                    room = main_window.get_current_room()
                else:
                    raise AttributeError("无法找到 get_current_room 方法")
                
                if room:
                    room.local_participant.unpublish_track(self.audio_track)
                self.audio_track = None
                self.show_info_bar("信息", "麦克风音频已从房间中移除", InfoBarPosition.TOP)
            except Exception as e:
                self.show_info_bar("错误", f"取消发布音频 track 失败: {str(e)}", InfoBarPosition.TOP, duration=3000, style='error')

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

    def closeEvent(self, event):
        self.timer.stop()
        if self.recorded_file and os.path.exists(self.recorded_file):
            os.remove(self.recorded_file)
        super().closeEvent(event)

    async def _enable_audio_track(self):
        if self.room_connected and self.audio_track:
            try:
                main_window = self.window()
                if hasattr(main_window, 'get_current_room'):
                    room = main_window.get_current_room()
                    if room:
                        # 增加超时时间
                        options = TrackPublishOptions()
                        options.source = TrackSource.SOURCE_MICROPHONE
                        await room.local_participant.publish_track(self.audio_track, options)
                        self.show_info_bar("成功", "麦克风已启用", InfoBarPosition.TOP)
                    else:
                        self.show_info_bar("错误", "无法获取当前房间", InfoBarPosition.TOP, duration=3000, style='error')
                else:
                    raise AttributeError("无法找到 get_current_room 方法")
            except Exception as e:
                logger.error(f"启用音频 track 失败: \n{traceback.format_exc()}")
                self.show_info_bar("错误", f"启用麦克风失败: {str(e)}", InfoBarPosition.TOP, duration=3000, style='error')

    async def _disable_audio_track(self):
        if self.room_connected and self.audio_track:
            try:
                main_window = self.window()
                if hasattr(main_window, 'get_current_room'):
                    room = main_window.get_current_room()
                    if room:
                        # 检查 audio_track 是否有 sid 属性
                        if hasattr(self.audio_track, 'sid'):
                            await room.local_participant.unpublish_track(self.audio_track.sid)
                        else:
                            # 如果没有 sid，尝试直接传递 audio_track 对象
                            await room.local_participant.unpublish_track(self.audio_track)
                        self.show_info_bar("成功", "麦克风已禁用", InfoBarPosition.TOP)
                    else:
                        self.show_info_bar("错误", "无法获取当前房间", InfoBarPosition.TOP, duration=3000, style='error')
                else:
                    raise AttributeError("无法找到 get_current_room 方法")
            except Exception as e:
                logger.error(f"禁用音频 track 失败: \n{traceback.format_exc()}")
                self.show_info_bar("错误", f"禁用麦克风失败: {str(e)}", InfoBarPosition.TOP, duration=3000, style='error')

    def disable_microphone(self):
        if self.mic_switch.isChecked():
            self.mic_switch.setChecked(False)
        if self.audio_track:
            asyncio.create_task(self._disable_audio_track())
        self.show_info_bar("信息", "麦克风已禁用", InfoBarPosition.TOP)