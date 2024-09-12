from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QSplitter, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
from PyQt5.QtCore import pyqtSignal, Qt, pyqtSlot
from PyQt5.QtGui import QFont
from qfluentwidgets import (LineEdit, PushButton, InfoBar, InfoBarPosition, Theme, 
                            setTheme, IconWidget, ToolButton, CardWidget, TitleLabel, TextEdit, TableWidget)
from qfluentwidgets import FluentIcon as FIF
import logging

class JoinRoomWidget(QWidget):
    join_room_signal = pyqtSignal(str, str)
    refresh_signal = pyqtSignal()
    subscribe_track_signal = pyqtSignal(str, str)
    unsubscribe_track_signal = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()

    def initUI(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        left_widget = self.create_left_widget()
        right_widget = self.create_right_widget()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

    def create_left_widget(self):
        left_widget = CardWidget(self)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(20)

        title_label = TitleLabel("加入房间", self)
        title_label.setFont(QFont("Microsoft YaHei", 14))
        left_layout.addWidget(title_label)

        self.url_input = LineEdit(self)
        self.url_input.setPlaceholderText("输入 LiveKit 服务器 URL")
        left_layout.addWidget(self.url_input)

        self.token_input = LineEdit(self)
        self.token_input.setPlaceholderText("输入访问令牌")
        left_layout.addWidget(self.token_input)

        self.join_button = PushButton("加入房间", self)
        self.join_button.clicked.connect(self.on_join_clicked)
        left_layout.addWidget(self.join_button)

        left_layout.addStretch(1)

        return left_widget

    def create_right_widget(self):
        right_widget = CardWidget(self)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(20)

        chat_title = TitleLabel("聊天窗口", self)
        chat_title.setFont(QFont("Microsoft YaHei", 12))
        right_layout.addWidget(chat_title)

        self.chat_display = TextEdit(self)
        self.chat_display.setReadOnly(True)
        right_layout.addWidget(self.chat_display)

        tracks_title = TitleLabel("参与者和轨道", self)
        tracks_title.setFont(QFont("Microsoft YaHei", 12))
        right_layout.addWidget(tracks_title)

        self.tracks_table = TableWidget(self)
        self.tracks_table.setColumnCount(4)
        self.tracks_table.setHorizontalHeaderLabels(["参与者", "轨道ID", "类型", "操作"])
        self.tracks_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tracks_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.tracks_table.setColumnWidth(3, 100)
        right_layout.addWidget(self.tracks_table)

        refresh_button = QPushButton("刷新", self)
        refresh_button.clicked.connect(self.on_refresh_clicked)
        right_layout.addWidget(refresh_button)

        return right_widget

    def on_join_clicked(self):
        url = self.url_input.text()
        token = self.token_input.text()
        if not url or not token:
            self.show_error_message("URL 和令牌不能为空")
            return
        self.join_room_signal.emit(url, token)

    def on_refresh_clicked(self):
        self.refresh_signal.emit()

    def show_success_message(self, message):
        InfoBar.success(title='成功', content=message, orient=InfoBarPosition.TOP, parent=self)

    def show_error_message(self, message):
        InfoBar.error(title='错误', content=message, orient=InfoBarPosition.TOP, parent=self)

    def add_chat_message(self, message):
        self.chat_display.append(message)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
        logging.info(f"添加聊天消息: {message}")

    @pyqtSlot(list)
    def update_tracks_table(self, tracks_data):
        self.tracks_table.setRowCount(0)
        for track in tracks_data:
            row_position = self.tracks_table.rowCount()
            self.tracks_table.insertRow(row_position)
            
            self.tracks_table.setItem(row_position, 0, QTableWidgetItem(track['participant']))
            self.tracks_table.setItem(row_position, 1, QTableWidgetItem(track['id']))
            self.tracks_table.setItem(row_position, 2, QTableWidgetItem(track['type']))
            
            if track['subscribed']:
                unsubscribe_button = PushButton("取消订阅")
                unsubscribe_button.clicked.connect(lambda checked, p=track['participant'], t=track['id']: self.unsubscribe_track_signal.emit(p, t))
                self.tracks_table.setCellWidget(row_position, 3, unsubscribe_button)
            else:
                subscribe_button = PushButton("订阅")
                subscribe_button.clicked.connect(lambda checked, p=track['participant'], t=track['id']: self.subscribe_track_signal.emit(p, t))
                self.tracks_table.setCellWidget(row_position, 3, subscribe_button)

    def update_connection_status(self, is_connected):
        if is_connected:
            self.show_success_message("已成功连接到房间")
            self.join_button.setEnabled(False)
            self.join_button.setText("已连接")
            self.url_input.setReadOnly(True)
            self.token_input.setReadOnly(True)
        else:
            self.show_error_message("未连接到房间")
            self.join_button.setEnabled(True)
            self.join_button.setText("加入房间")
            self.url_input.setReadOnly(False)
            self.token_input.setReadOnly(False)

    def add_room_event(self, event_type, details):
        self.add_chat_message(f"房间事件: {event_type}\n详情: {details}")