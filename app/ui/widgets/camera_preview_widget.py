from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtMultimedia import QCamera, QCameraInfo
from PyQt5.QtMultimediaWidgets import QCameraViewfinder
from qfluentwidgets import (SwitchButton, InfoBar, InfoBarPosition, IconWidget,
                            FluentIcon as FIF, SubtitleLabel, ToolButton, CardWidget)
from app.utils.logger import logger

class CameraPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()
        self.is_connected = False
        self.camera = None
        self.initialize_camera()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # 状态卡片
        status_card = self.create_status_card()
        main_layout.addWidget(status_card)

        # 视频预览卡片
        preview_card = self.create_preview_card()
        main_layout.addWidget(preview_card)

    def create_status_card(self):
        status_card = CardWidget(self)
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(16, 16, 16, 16)
        status_layout.setSpacing(16)

        self.status_icon = IconWidget(FIF.QUESTION, self)
        self.status_icon.setFixedSize(24, 24)
        self.status_label = SubtitleLabel("未连接到房间")
        
        self.refresh_button = ToolButton(FIF.SYNC, self)
        self.refresh_button.clicked.connect(self.refresh_status)
        
        self.camera_switch = SwitchButton("摄像头", self)
        self.camera_switch.checkedChanged.connect(self.toggle_camera)

        status_layout.addWidget(self.status_icon)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.refresh_button)
        status_layout.addWidget(self.camera_switch)

        return status_card

    def create_preview_card(self):
        preview_card = CardWidget(self)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self.viewfinder = QCameraViewfinder(self)
        self.viewfinder.setMinimumHeight(400)
        preview_layout.addWidget(self.viewfinder)

        return preview_card

    def initialize_camera(self):
        available_cameras = QCameraInfo.availableCameras()
        if available_cameras:
            self.camera = QCamera(available_cameras[0])
            self.camera.setViewfinder(self.viewfinder)
            logger.info(f"摄像头已初始化: {available_cameras[0].description()}")
        else:
            logger.warning("未检测到可用的摄像头")
            self.show_error_message("未检测到可用的摄像头")

    def toggle_camera(self, checked):
        if self.camera:
            if checked:
                self.camera.start()
                self.create_and_publish_video_track()
            else:
                self.camera.stop()
                self.unpublish_video_track()

    def create_and_publish_video_track(self):
        if self.parent.get_current_room():
            try:
                from livekit import rtc
                self.video_track = rtc.LocalVideoTrack.create_video_track("camera")
                self.parent.get_current_room().local_participant.publish_track(self.video_track)
                logger.info("视频轨道已创建并发布")
            except Exception as e:
                logger.error(f"创建或发布视频轨道时出错: {str(e)}")

    def unpublish_video_track(self):
        if hasattr(self, 'video_track') and self.parent.get_current_room():
            try:
                self.parent.get_current_room().local_participant.unpublish_track(self.video_track)
                self.video_track = None
                logger.info("视频轨道已取消发布")
            except Exception as e:
                logger.error(f"取消发布视频轨道时出错: {str(e)}")

    def update_room_status(self, is_connected):
        self.is_connected = is_connected
        if is_connected:
            self.status_label.setText("已连接到房间")
            self.status_icon.setIcon(FIF.ACCEPT_MEDIUM)
        else:
            self.status_label.setText("未连接到房间")
            self.status_icon.setIcon(FIF.CANCEL_MEDIUM)

    def refresh_status(self):
        if hasattr(self.parent, 'get_room_connection_status'):
            is_connected = self.parent.get_room_connection_status()
            self.update_room_status(is_connected)
        else:
            self.show_error_message("无法获取房间连接状态")

    def show_error_message(self, message):
        InfoBar.error(
            title='错误',
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = CameraPreviewWidget()
    widget.show()
    sys.exit(app.exec_())
