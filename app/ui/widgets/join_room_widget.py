from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor
from qfluentwidgets import (LineEdit, PushButton, InfoBar, InfoBarPosition, Theme, 
                            setTheme, ListWidget, IconWidget, ToolButton, BodyLabel)
from qfluentwidgets import FluentIcon as FIF

class ParticipantItem(QWidget):
    def __init__(self, participant_name, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        icon = IconWidget(FIF.PEOPLE, self)
        layout.addWidget(icon)

        name_label = BodyLabel(participant_name, self)
        layout.addWidget(name_label)

        layout.addStretch(1)

        self.mic_button = ToolButton(FIF.MICROPHONE, self)
        self.camera_button = ToolButton(FIF.CAMERA, self)

        self.mic_button.clicked.connect(lambda: self.toggle_mic(participant_name))
        self.camera_button.clicked.connect(lambda: self.toggle_camera(participant_name))

        layout.addWidget(self.mic_button)
        layout.addWidget(self.camera_button)

    def toggle_mic(self, participant_name):
        print(f"Toggle mic for {participant_name}")

    def toggle_camera(self, participant_name):
        print(f"Toggle camera for {participant_name}")

class JoinRoomWidget(QWidget):
    join_room_signal = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("joinRoomWidget")
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        left_layout.setContentsMargins(50, 50, 50, 50)
        left_layout.setSpacing(20)

        self.url_input = LineEdit(self)
        self.url_input.setPlaceholderText("输入 LiveKit 服务器 URL")
        left_layout.addWidget(self.url_input)

        self.token_input = LineEdit(self)
        self.token_input.setPlaceholderText("输入访问令牌")
        left_layout.addWidget(self.token_input)

        join_button = PushButton("加入房间", self)
        join_button.clicked.connect(self.on_join_clicked)
        left_layout.addWidget(join_button)

        left_layout.addStretch(1)

        self.member_list = ListWidget(self)
        self.member_list.setObjectName("memberList")
        self.member_list.setStyleSheet("""
            QListWidget#memberList {
                background-color: transparent;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget#memberList::item {
                background-color: transparent;
            }
        """)
        right_layout.addWidget(self.member_list)

        main_layout.addLayout(left_layout, 2)
        main_layout.addLayout(right_layout, 1)

    def on_join_clicked(self):
        url = self.url_input.text()
        token = self.token_input.text()
        if not url or not token:
            InfoBar.error(
                title='错误',
                content="URL 和令牌不能为空",
                orient=InfoBarPosition.TOP,
                parent=self
            )
            return
        self.join_room_signal.emit(url, token)

    def show_success_message(self, message):
        InfoBar.success(
            title='成功',
            content=message,
            orient=InfoBarPosition.TOP,
            parent=self
        )

    def show_error_message(self, message):
        InfoBar.error(
            title='错误',
            content=message,
            orient=InfoBarPosition.TOP,
            parent=self
        )

    def update_member_list(self, members):
        self.member_list.clear()
        for member in members:
            item = QListWidgetItem(self.member_list)
            participant_widget = ParticipantItem(member)
            item.setSizeHint(participant_widget.sizeHint())
            self.member_list.setItemWidget(item, participant_widget)