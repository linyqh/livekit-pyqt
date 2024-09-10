from qfluentwidgets import FluentWindow, NavigationItemPosition
from qfluentwidgets import FluentIcon as FIF
from app.ui.widgets.room_management_widget import RoomManagementWidget
from app.ui.widgets.join_room_widget import JoinRoomWidget
from app.ui.widgets.camera_preview_widget import CameraPreviewWidget
from app.services.livekit_service import join_livekit_room
from app.utils.logger import logger
import asyncio
import traceback

class LiveKitManager(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LiveKit 管理工具")
        self.resize(900, 700)
        
        # 创建并添加页面
        self.room_management = RoomManagementWidget(self)
        self.room_management.setObjectName("roomManagementWidget")
        
        self.join_room = JoinRoomWidget(self)
        self.join_room.setObjectName("joinRoomWidget")
        
        self.camera_preview = CameraPreviewWidget(self)
        self.camera_preview.setObjectName("cameraPreviewWidget")
        
        self.addSubInterface(self.room_management, icon=FIF.HOME, text="房间管理")
        self.addSubInterface(self.join_room, icon=FIF.VIDEO, text="加入房间")
        self.addSubInterface(self.camera_preview, icon=FIF.CAMERA, text="摄像头预览")
        
        # 设置侧边栏样式
        self.navigationInterface.setExpandWidth(200)
        self.navigationInterface.setMinimumWidth(200)

        # 连接信号到槽
        self.join_room.join_room_signal.connect(self.on_join_room)
        self.current_room = None

    def on_join_room(self, url, token):
        asyncio.create_task(self.async_join_room(url, token))

    async def async_join_room(self, url, token):
        try:
            self.current_room = await join_livekit_room(url, token)
            self.join_room.show_success_message("成功加入房间")
            
            # 更新成员列表
            self.update_member_list()
            
            # 监听房间事件
            @self.current_room.on("participant_connected")
            def on_participant_connected(participant):
                print(f"参与者 {participant.identity} 已连接")
                self.update_member_list()
            
            @self.current_room.on("participant_disconnected")
            def on_participant_disconnected(participant):
                print(f"参与者 {participant.identity} 已断开连接")
                self.update_member_list()
            
            # 打印房间信息，以便调试
            print(f"房间名: {self.current_room.name}")
            print(f"本地参与者: {self.current_room.local_participant.identity}")
            print(f"远程参与者: {[p.identity for p in self.current_room.remote_participants.values()]}")
            
        except Exception as e:
            error_message = f"加入房间时发生错误: {str(e)}"
            logger.error(f"{error_message}\n{traceback.format_exc()}")
            self.join_room.show_error_message(error_message)

    def update_member_list(self):
        members = []
        if self.current_room:
            # 添加远程参与者
            for participant in self.current_room.remote_participants.values():
                members.append(participant.identity)
            # 添加本地参与者
            members.append(self.current_room.local_participant.identity + " (你)")
        self.join_room.update_member_list(members)