from PyQt5.QtWidgets import QWidget


class CameraPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cameraPreviewWidget")
        # 在这里添加摄像头预览的 UI 元素和逻辑
