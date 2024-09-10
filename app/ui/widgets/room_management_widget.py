from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidgetItem, QApplication, QMessageBox, QHeaderView
from PyQt5.QtCore import QProcess, QTimer, pyqtSlot
from qfluentwidgets import (LineEdit, PushButton, TableWidget, ComboBox, 
                            MessageBox, InfoBar, InfoBarPosition, RadioButton,
                            BodyLabel, StrongBodyLabel, TextEdit)
from livekit import api
import asyncio
import traceback
from qasync import asyncSlot, asyncClose
import aiohttp
from app.utils.logger import logger

class RoomManagementWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("roomManagementWidget")
        self.livekit_process = None
        self.livekit_client = None
        self.session = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # LiveKit 服务选择
        self.service_selection = QHBoxLayout()
        self.local_radio = RadioButton("本地 LiveKit 服务", self)
        self.cloud_radio = RadioButton("云端 LiveKit 服务", self)
        self.service_selection.addWidget(self.local_radio)
        self.service_selection.addWidget(self.cloud_radio)
        layout.addLayout(self.service_selection)
        
        # 本地 LiveKit 启动按钮
        self.start_local_btn = PushButton("启动本地 LiveKit 服务", self)
        self.start_local_btn.clicked.connect(self.start_local_livekit)
        layout.addWidget(self.start_local_btn)
        
        # 云端 LiveKit 配置
        self.cloud_config = QVBoxLayout()
        self.livekit_url = LineEdit(self)
        self.livekit_url.setPlaceholderText("LIVEKIT_URL")
        self.livekit_api_key = LineEdit(self)
        self.livekit_api_key.setPlaceholderText("LIVEKIT_API_KEY")
        self.livekit_api_secret = LineEdit(self)
        self.livekit_api_secret.setPlaceholderText("LIVEKIT_API_SECRET")
        self.cloud_config.addWidget(self.livekit_url)
        self.cloud_config.addWidget(self.livekit_api_key)
        self.cloud_config.addWidget(self.livekit_api_secret)
        layout.addLayout(self.cloud_config)
        
        # 修改连接按钮的连接方式
        self.connect_btn = PushButton("连接 LiveKit 服务", self)
        self.connect_btn.clicked.connect(self.connect_livekit)
        layout.addWidget(self.connect_btn)
        
        # 连接状态
        self.connection_status = StrongBodyLabel("未连接", self)
        layout.addWidget(self.connection_status)
        
        # 服务器地址显示
        self.server_address_layout = QHBoxLayout()
        self.server_address_label = BodyLabel("服务器地址:", self)
        self.server_address_text = LineEdit(self)
        self.server_address_text.setReadOnly(True)
        self.copy_server_address_btn = PushButton("复制", self)
        self.copy_server_address_btn.setEnabled(False)
        self.copy_server_address_btn.clicked.connect(self.copy_server_address)
        self.server_address_layout.addWidget(self.server_address_label)
        self.server_address_layout.addWidget(self.server_address_text)
        self.server_address_layout.addWidget(self.copy_server_address_btn)
        layout.addLayout(self.server_address_layout)
        
        # 创建房间和刷新房间列表
        room_control_layout = QHBoxLayout()
        self.room_name_input = LineEdit(self)
        self.room_name_input.setPlaceholderText("输入房间名称")
        self.create_room_btn = PushButton("创建房间", self)
        self.create_room_btn.clicked.connect(self.create_room)
        self.refresh_room_list_btn = PushButton("刷新列表", self)
        self.refresh_room_list_btn.clicked.connect(self.refresh_room_list)
        room_control_layout.addWidget(self.room_name_input)
        room_control_layout.addWidget(self.create_room_btn)
        room_control_layout.addWidget(self.refresh_room_list_btn)
        layout.addLayout(room_control_layout)
        
        # 房间列表
        self.room_table = TableWidget(self)
        self.room_table.setColumnCount(3)
        self.room_table.setHorizontalHeaderLabels(["房间名", "参与者数量", "操作"])
        self.room_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.room_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.room_table.setColumnWidth(2, 100)  # 设置"操作"列的固定宽度
        layout.addWidget(self.room_table)
        
        # 生成令牌
        token_layout = QVBoxLayout()
        token_select_layout = QHBoxLayout()
        self.token_room_select = ComboBox(self)
        self.generate_token_btn = PushButton("生成访问令牌", self)
        self.generate_token_btn.clicked.connect(self.generate_token)
        token_select_layout.addWidget(self.token_room_select)
        token_select_layout.addWidget(self.generate_token_btn)
        token_layout.addLayout(token_select_layout)
        
        # 新增：显示生成的 token 的文本框和复制按钮
        token_display_layout = QHBoxLayout()
        self.token_display = TextEdit(self)
        self.token_display.setReadOnly(True)
        self.token_display.setPlaceholderText("生成的令牌将显示在这里")
        self.copy_token_btn = PushButton("复制", self)
        self.copy_token_btn.clicked.connect(self.copy_token)
        token_display_layout.addWidget(self.token_display)
        token_display_layout.addWidget(self.copy_token_btn)
        token_layout.addLayout(token_display_layout)
        
        layout.addLayout(token_layout)
        
        # 初始状态设置
        self.local_radio.setChecked(True)
        self.update_ui_state()
        
        # 连接信号
        self.local_radio.toggled.connect(self.update_ui_state)
        self.cloud_radio.toggled.connect(self.update_ui_state)

    def update_ui_state(self):
        is_local = self.local_radio.isChecked()
        self.start_local_btn.setVisible(is_local)
        self.livekit_url.setVisible(not is_local)
        self.livekit_api_key.setVisible(not is_local)
        self.livekit_api_secret.setVisible(not is_local)

    def start_local_livekit(self):
        if not self.livekit_process or self.livekit_process.state() == QProcess.NotRunning:
            self.livekit_process = QProcess(self)
            # 判断当前系统为windows还是mac
            if QApplication.platformName() == "windows":
                self.livekit_process.start("D:\\livekit\\livekit-server.exe", ["--dev"])
            else:
                self.livekit_process.start("livekit-server", ["--dev"])
            InfoBar.success(
                title="本地 LiveKit 服务",
                content="正在启动本地 LiveKit 服务...",
                orient=InfoBarPosition.TOP,
                parent=self
            )
        else:
            InfoBar.warning(
                title="本地 LiveKit 服务",
                content="地 LiveKit 服务已在运行",
                orient=InfoBarPosition.TOP,
                parent=self
            )

    @asyncSlot()
    async def connect_livekit(self):
        if self.local_radio.isChecked():
            url = "http://localhost:7880"
            api_key = "devkey"
            api_secret = "secret"
            
            # 检查本地 LiveKit 服务是否正在运行
            if not self.livekit_process or self.livekit_process.state() != QProcess.Running:
                InfoBar.warning(
                    title="连接错误",
                    content="本地 LiveKit 服务未运行，请先启动服务",
                    orient=InfoBarPosition.TOP,
                    parent=self
                )
                return
        else:
            url = self.livekit_url.text()
            api_key = self.livekit_api_key.text()
            api_secret = self.livekit_api_secret.text()
            
        if not url or not api_key or not api_secret:
            InfoBar.error(
                title="连接错误",
                content="请填写所有 LiveKit 配置信息",
                orient=InfoBarPosition.TOP,
                parent=self
            )
            return
        
        try:
            if self.session:
                await self.session.close()
            self.session = aiohttp.ClientSession()
            self.livekit_client = api.LiveKitAPI(url, api_key, api_secret)
            # 保存 API key 和 secret 以供后续使用
            self.livekit_client.saved_api_key = api_key
            self.livekit_client.saved_api_secret = api_secret
            await self.test_connection()
            self.connection_status.setText(f"已连接到 LiveKit 服务: {url}")
            InfoBar.success(
                title="连接成功",
                content="已成功连接到 LiveKit 服务",
                orient=InfoBarPosition.TOP,
                parent=self
            )
            logger.info(f"成功连接到 LiveKit 服务: {url}")
            await self.update_room_list()
            self.server_address_text.setText(url)
            self.copy_server_address_btn.setEnabled(True)
        except Exception as e:
            logger.exception(f"连接 LiveKit 服务时发生错误: {str(e)}")
            InfoBar.error(
                title="连接错误",
                content=f"无法连接到 LiveKit 服务: {str(e)}",
                orient=InfoBarPosition.TOP,
                parent=self
            )
            self.livekit_client = None
            if self.session:
                await self.session.close()
                self.session = None

    async def test_connection(self):
        # 如果你想列出特定的房间，可以添加名称
        # list_request.names.extend(["room1", "room2"])
        await self.livekit_client.room.list_rooms(api.ListRoomsRequest())

    @asyncSlot()
    async def create_room(self):
        if not self.livekit_client:
            InfoBar.warning(
                title="创建房间失败",
                content="请先连接到 LiveKit 服务",
                orient=InfoBarPosition.TOP,
                parent=self
            )
            return

        room_name = self.room_name_input.text()
        if not room_name:
            InfoBar.warning(
                title="创建房间失败",
                content="请输入房间名称",
                orient=InfoBarPosition.TOP,
                parent=self
            )
            return

        try:
            room = await self.livekit_client.room.create_room(api.CreateRoomRequest(name=room_name))
            InfoBar.success(
                title="创建房间成功",
                content=f"已成功创建房间: {room_name}",
                orient=InfoBarPosition.TOP,
                parent=self
            )
            self.room_name_input.clear()
            await self.update_room_list()
        except Exception as e:
            logger.error(f"创建房间时发生错误: {traceback.format_exc()}")
            InfoBar.error(
                title="创建房间失败",
                content=f"无法创建房间: {str(e)}",
                orient=InfoBarPosition.TOP,
                parent=self
            )

    @asyncSlot()
    async def update_room_list(self):
        if not self.livekit_client:
            return

        try:
            list_request = api.ListRoomsRequest()
            # 如果你想列出特定的房间，可以添加名称
            # list_request.names.extend(["room1", "room2"])
            response = await self.livekit_client.room.list_rooms(list_request)
            rooms = response.rooms
            self.room_table.setRowCount(len(rooms))
            for row, room in enumerate(rooms):
                self.room_table.setItem(row, 0, QTableWidgetItem(room.name))
                self.room_table.setItem(row, 1, QTableWidgetItem(str(room.num_participants)))
                delete_btn = PushButton("删除")
                delete_btn.clicked.connect(lambda _, r=room.name: asyncio.create_task(self.delete_room(r)))
                delete_btn.setFixedWidth(80)  # 设置删除按钮的固定宽度
                self.room_table.setCellWidget(row, 2, delete_btn)

            self.token_room_select.clear()
            self.token_room_select.addItems([room.name for room in rooms])
        except Exception as e:
            InfoBar.error(
                title="更新房间列表失败",
                content=f"无法获取房间列表: {str(e)}",
                orient=InfoBarPosition.TOP,
                parent=self
            )

    async def delete_room(self, room_name):
        try:
            await self.livekit_client.room.delete_room(api.DeleteRoomRequest(room=room_name))
            InfoBar.success(
                title="删除房间成功",
                content=f"已成功删除房间: {room_name}",
                orient=InfoBarPosition.TOP,
                parent=self
            )
            await self.update_room_list()
        except Exception as e:
            InfoBar.error(
                title="删除房间失败",
                content=f"无法删除房间: {str(e)}",
                orient=InfoBarPosition.TOP,
                parent=self
            )

    @asyncSlot()
    async def generate_token(self):
        if not self.livekit_client:
            InfoBar.warning(
                title="生成令牌失败",
                content="请先连接到 LiveKit 服务",
                orient=InfoBarPosition.TOP,
                parent=self
            )
            return

        selected_room = self.token_room_select.currentText()
        if not selected_room:
            InfoBar.warning(
                title="生成令牌失败",
                content="请先选择一个房间",
                orient=InfoBarPosition.TOP,
                parent=self
            )
            return

        try:
            api_key = self.livekit_client.saved_api_key
            api_secret = self.livekit_client.saved_api_secret

            token = api.AccessToken(api_key, api_secret).with_identity("test_user").with_name("Test User").with_grants(
                api.VideoGrants(room_join=True, room=selected_room)
            ).to_jwt()
            
            # 在文本框中显示生成的令牌
            self.token_display.setPlainText(token)
            
            InfoBar.success(
                title="令牌生成成功",
                content=f"房间 {selected_room} 的访问令牌已生成",
                orient=InfoBarPosition.TOP,
                parent=self
            )
            logger.info(f"成功为房间 {selected_room} 生成访问令牌")
        except Exception as e:
            logger.error(f"生成访问令牌时发生错误: \n{traceback.format_exc()}")
            InfoBar.error(
                title="生成令牌失败",
                content=f"无法生成访问令牌: {str(e)}",
                orient=InfoBarPosition.TOP,
                parent=self
            )

    def copy_token(self):
        token = self.token_display.toPlainText()
        if token:
            QApplication.clipboard().setText(token)
            InfoBar.success(
                title="复制成功",
                content="访问令牌已复制到剪贴板",
                orient=InfoBarPosition.TOP,
                parent=self
            )
        else:
            InfoBar.warning(
                title="复制失败",
                content="没有可复制的访问令牌",
                orient=InfoBarPosition.TOP,
                parent=self
            )

    def copy_server_address(self):
        server_address = self.server_address_text.text()
        if server_address:
            QApplication.clipboard().setText(server_address)
            InfoBar.success(
                title="复制成功",
                content="服务器地址已复制到剪贴板",
                orient=InfoBarPosition.TOP,
                parent=self
            )
        else:
            InfoBar.warning(
                title="复制失败",
                content="没有可复制的服务器地址",
                orient=InfoBarPosition.TOP,
                parent=self
            )

    @asyncSlot()
    async def refresh_room_list(self):
        if not self.livekit_client:
            InfoBar.warning(
                title="刷新失败",
                content="请先连接到 LiveKit 服务",
                orient=InfoBarPosition.TOP,
                parent=self
            )
            return
        await self.update_room_list()
        InfoBar.success(
            title="刷新成功",
            content="房间列表已更新",
            orient=InfoBarPosition.TOP,
            parent=self
        )

    @asyncClose
    async def closeEvent(self, event):
        logger.info("正在关闭 RoomManagementWidget")
        if self.session:
            await self.session.close()
        if self.livekit_process:
            self.livekit_process.kill()
        await super().closeEvent(event)
        logger.info("RoomManagementWidget 已关闭")