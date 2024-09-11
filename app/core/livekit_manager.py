from qfluentwidgets import FluentWindow, NavigationItemPosition
from qfluentwidgets import FluentIcon as FIF
from app.ui.widgets.room_management_widget import RoomManagementWidget
from app.ui.widgets.join_room_widget import JoinRoomWidget
from app.ui.widgets.camera_preview_widget import CameraPreviewWidget
from app.ui.widgets.microphone_widget import MicrophoneWidget
from app.ui.widgets.audio_publisher_widget import AudioPublisherWidget
from app.services.livekit_service import join_livekit_room
from app.utils.logger import logger
from livekit.rtc import ChatManager, TrackKind
import asyncio
import traceback
from livekit import rtc


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

        self.microphone_widget = MicrophoneWidget(self)
        self.microphone_widget.setObjectName("microphoneWidget")

        self.audio_publisher = AudioPublisherWidget(self)
        self.audio_publisher.setObjectName("audioPublisherWidget")

        self.addSubInterface(self.room_management, icon=FIF.HOME, text="房间管理")
        self.addSubInterface(self.join_room, icon=FIF.VIDEO, text="加入房间")
        self.addSubInterface(self.camera_preview, icon=FIF.CAMERA, text="摄像头预览")
        self.addSubInterface(self.microphone_widget, icon=FIF.MICROPHONE, text="麦克风")
        self.addSubInterface(self.audio_publisher, icon=FIF.MUSIC, text="布音频")

        # 设置侧边栏样式
        self.navigationInterface.setExpandWidth(200)
        self.navigationInterface.setMinimumWidth(200)

        # 连接信号到槽
        self.join_room.join_room_signal.connect(self.on_join_room)
        self.join_room.refresh_signal.connect(self.refresh_room_info)  # 连接刷新信号
        self.current_room = None
        self.room_connected = False
        self.chat_manager = None

    def on_join_room(self, url, token):
        asyncio.create_task(self.async_join_room(url, token))

    async def async_join_room(self, url, token):
        try:
            logger.info(f"尝试加入房间: {url}")
            self.current_room = await join_livekit_room(url, token)
            logger.info("成功创建房间对象")
            
            self.join_room.show_success_message("成功加入房间")
            logger.info("显示成功消息")
            
            self.room_connected = True
            self.camera_preview.update_room_status(True)
            self.microphone_widget.update_room_status(True)
            self.audio_publisher.update_room_status(True, self.current_room)
            logger.info("更新房间连接状态和各个组件状态")
            
            # 初始化 ChatManager
            self.chat_manager = ChatManager(self.current_room)
            logger.info("初始化 ChatManager")
            
            # 设置消息接收监听器
            @self.chat_manager.on("message_received")
            def on_message_received(message):
                chat_message = f"收到消息: {message.message}"
                self.join_room.add_chat_message(chat_message)
            
            # 更新参与者信息
            self.update_participants_info()
            
            # 监听房间事件
            @self.current_room.on("participant_connected")
            def on_participant_connected(participant):
                chat_message = f"参与者 {participant.identity} 已连接"
                self.join_room.add_chat_message(chat_message)
                self.update_participants_info()
            
            @self.current_room.on("participant_disconnected")
            def on_participant_disconnected(participant):
                chat_message = f"参与者 {participant.identity} 已断开连接"
                self.join_room.add_chat_message(chat_message)
                self.update_participants_info()
            
            # 打印房间信息到聊天窗口
            room_info = f"房间名: {self.current_room.name}\n"
            room_info += f"本地参与者: {self.current_room.local_participant.identity}\n"
            room_info += f"远程参与者: {[p.identity for p in self.current_room.remote_participants.values()]}"
            self.join_room.add_chat_message(room_info)
            
            logger.info("成功加入房间并设置了所有事件监听器")
            
            # 在成功加入房间后，更新轨道信息
            self.update_tracks_info()

            # 添加轨道变化的监听器
            @self.current_room.on("track_published")
            @self.current_room.on("track_unpublished")
            @self.current_room.on("track_subscribed")
            @self.current_room.on("track_unsubscribed")
            def on_track_change(track, publication, participant):
                self.update_tracks_info()

        except Exception as e:
            error_message = f"加入房间时发生错误: {str(e)}"
            logger.error(f"{error_message}\n{traceback.format_exc()}")
            self.join_room.show_error_message(error_message)
            self.room_connected = False
            self.camera_preview.update_room_status(False)
            self.microphone_widget.update_room_status(False)
            self.audio_publisher.update_room_status(False, None)

    def update_participants_info(self):
        if not self.current_room:
            logger.warning("尝试更新参与者信息，但房间未连接")
            return

        tracks_data = []

        # 添加本地参与者的轨道
        local_participant = self.current_room.local_participant
        for track in local_participant.track_publications.values():
            tracks_data.append({
                'participant': local_participant.identity + " (你)",
                'id': track.sid,
                'type': 'Audio' if track.kind == rtc.TrackKind.KIND_VIDEO else 'Video'
            })

        # 添加远程参与者的轨道
        for participant in self.current_room.remote_participants.values():
            for track in participant.track_publications.values():
                tracks_data.append({
                    'participant': participant.identity,
                    'id': track.sid,
                    'type': 'Audio' if track.kind == rtc.TrackKind.KIND_VIDEO else 'Video'
                })

        self.join_room.update_tracks_table(tracks_data)
        logger.info(f"更新了 {len(tracks_data)} 条轨道信息")

    def get_room_connection_status(self):
        return self.room_connected

    def get_current_room(self):
        return self.current_room

    def closeEvent(self, event):
        if self.current_room:
            asyncio.create_task(self.current_room.disconnect())
        super().closeEvent(event)

    def update_tracks_info(self):
        if not self.current_room:
            logger.warning("尝试更新轨道信息，但房间未连接")
            return

        tracks_data = []

        # 添加本地参与者的轨道
        local_participant = self.current_room.local_participant
        for track in local_participant.track_publications.values():
            tracks_data.append({
                'participant': local_participant.identity + " (你)",
                'id': track.sid,
                'type': 'Audio' if track.kind == rtc.TrackKind.KIND_VIDEO else 'Video'
            })

        # 添加远程参与者的轨道
        for participant in self.current_room.remote_participants.values():
            for track in participant.track_publications.values():
                tracks_data.append({
                    'participant': participant.identity,
                    'id': track.sid,
                    'type': 'Audio' if track.kind == rtc.TrackKind.KIND_AUDIO else 'Video'
                })

        self.join_room.update_tracks_table(tracks_data)
        logger.info(f"更新了 {len(tracks_data)} 条轨道信息")

    def refresh_room_info(self):
        self.update_participants_info()
        logger.info("刷新了房间信息")
