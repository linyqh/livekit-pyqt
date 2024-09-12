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
from livekit.rtc import Room, RemoteParticipant, RemoteTrackPublication, RemoteAudioTrack, RemoteVideoTrack, TrackKind
from app.ui.widgets.subscribed_tracks_widget import SubscribedTracksWidget
from PyQt5.QtMultimedia import QAudioOutput, QAudioFormat
from PyQt5.QtCore import QBuffer, QByteArray, QMetaObject, Qt, Q_ARG
import numpy as np
import wave
import os
from datetime import datetime

class LiveKitManager(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LiveKit 管理工具")
        self.resize(900, 700)

        # 创添加页面
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

        # 连接阅号
        self.join_room.subscribe_track_signal.connect(self.on_subscribe_track)
        self.join_room.unsubscribe_track_signal.connect(self.on_unsubscribe_track)

        self.subscribed_tracks = SubscribedTracksWidget(self)
        self.subscribed_tracks.setObjectName("subscribedTracksWidget")
        self.addSubInterface(self.subscribed_tracks, icon=FIF.VIDEO, text="已订阅轨道")

        self.audio_output = None
        self.audio_buffer = None
        self.audio_tasks = {}
        self.video_tasks = {}

        self.loop = asyncio.get_event_loop()

        self.subscribed_tracks.play_track_signal.connect(self.on_play_track)
        self.subscribed_tracks.record_track_signal.connect(self.on_record_track)

    def on_join_room(self, url, token):
        asyncio.ensure_future(self.async_join_room(url, token))

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
            await self.update_participants_info()
            
            # 设置房间事件监听器
            self.current_room.on("participant_connected", self.on_participant_connected)
            self.current_room.on("participant_disconnected", self.on_participant_disconnected)
            self.current_room.on("local_track_published", self.on_local_track_published)
            self.current_room.on("local_track_unpublished", self.on_local_track_unpublished)
            self.current_room.on("track_published", self.on_track_published)
            self.current_room.on("track_unpublished", self.on_track_unpublished)
            self.current_room.on("track_subscribed", self.on_track_subscribed)
            self.current_room.on("track_unsubscribed", self.on_track_unsubscribed)
            
            logger.info("成功加入房间并设置了所有事件监听器")
            
            # 更新 JoinRoomWidget 的连接状态
            self.join_room.update_connection_status(True)
            
        except Exception as e:
            error_message = f"加入房间时发生错误: {str(e)}"
            logger.error(f"{error_message}\n{traceback.format_exc()}")
            self.join_room.show_error_message(error_message)
            self.room_connected = False
            self.camera_preview.update_room_status(False)
            self.microphone_widget.update_room_status(False)
            self.audio_publisher.update_room_status(False, None)
            self.join_room.update_connection_status(False)

    def on_participant_connected(self, participant: RemoteParticipant):
        logger.info(f"参与者 {participant.identity} 已连接")
        self.join_room.add_room_event("参与者连接", f"参与者 {participant.identity} 已连接")
        asyncio.create_task(self.update_participants_info())

    def on_participant_disconnected(self, participant: RemoteParticipant):
        logger.info(f"参与者 {participant.identity} 已断开连接")
        self.join_room.add_room_event("参与断开连接", f"参与者 {participant.identity} 已断开连接")
        asyncio.create_task(self.update_participants_info())

    def on_local_track_published(self, publication, track):
        logger.info(f"本地轨道已发布: {publication.sid}")
        self.join_room.add_room_event("本地轨道发布", f"轨道 {publication.sid} 已发布")
        asyncio.create_task(self.update_participants_info())

    def on_local_track_unpublished(self, publication):
        logger.info(f"本地轨道已取消发布: {publication.sid}")
        self.join_room.add_room_event("本地轨道取消发布", f"轨道 {publication.sid} 已取消发布")
        asyncio.create_task(self.update_participants_info())

    def on_track_published(self, publication: RemoteTrackPublication, participant: RemoteParticipant):
        logger.info(f"轨道已发布: {publication.sid} 来自 {participant.identity}")
        self.join_room.add_room_event("轨道发布", f"轨道 {publication.sid} 已由 {participant.identity} 发布")
        asyncio.create_task(self.update_participants_info())

    def on_track_unpublished(self, publication: RemoteTrackPublication, participant: RemoteParticipant):
        logger.info(f"轨道已取消发布: {publication.sid} 来自 {participant.identity}")
        self.join_room.add_room_event("轨道取消发布", f"轨道 {publication.sid} 已由 {participant.identity} 取消发布")
        asyncio.create_task(self.update_participants_info())

    def on_track_subscribed(self, track, publication: RemoteTrackPublication, participant: RemoteParticipant):
        logger.info(f"已订阅轨道: {publication.sid} 来自 {participant.identity}")
        self.join_room.add_room_event("轨道订阅", f"已订阅来自 {participant.identity} 的轨道 {publication.sid}")
        self.subscribed_tracks.add_track(participant.identity, publication.sid, "Audio" if publication.kind == TrackKind.KIND_AUDIO else "Video")
        asyncio.create_task(self.update_participants_info())

    def on_track_unsubscribed(self, track, publication: RemoteTrackPublication, participant: RemoteParticipant):
        logger.info(f"已取订阅轨道: {publication.sid} 来自 {participant.identity}")
        self.join_room.add_room_event("轨道取消订阅", f"已取消订阅来自 {participant.identity} 的轨道 {publication.sid}")
        
        if publication.sid in self.audio_tasks:
            self.audio_tasks[publication.sid].cancel()
            del self.audio_tasks[publication.sid]
        if publication.sid in self.video_tasks:
            self.video_tasks[publication.sid].cancel()
            del self.video_tasks[publication.sid]
        
        self.subscribed_tracks.remove_track(publication.sid)
        asyncio.create_task(self.update_participants_info())

    async def update_participants_info(self):
        if not self.current_room:
            logger.warning("尝试更新参与者信息，但房间未连接")
            return

        tracks_data = []

        # 添加本地参与的轨道
        local_participant = self.current_room.local_participant
        for track in local_participant.track_publications.values():
            tracks_data.append({
                'participant': local_participant.identity + " (你)",
                'id': track.sid,
                'type': 'Audio' if track.kind == TrackKind.KIND_AUDIO else 'Video',
                'subscribed': True  # 本地轨道总是被订阅
            })

        # 添加远程参与者的轨道
        for participant in self.current_room.remote_participants.values():
            for track in participant.track_publications.values():
                tracks_data.append({
                    'participant': participant.identity,
                    'id': track.sid,
                    'type': 'Audio' if track.kind == TrackKind.KIND_AUDIO else 'Video',
                    'subscribed': track.subscribed
                })

        # 使用 QMetaObject.invokeMethod 在主线程中更新 UI
        QMetaObject.invokeMethod(self.join_room, "update_tracks_table",
                                 Qt.QueuedConnection,
                                 Q_ARG(list, tracks_data))

        logger.info(f"更新了 {len(tracks_data)} 条轨道信息")

    def get_room_connection_status(self):
        return self.room_connected

    def get_current_room(self):
        return self.current_room

    def closeEvent(self, event):
        if self.audio_output:
            self.audio_output.stop()
        if self.audio_buffer:
            self.audio_buffer.close()
        if self.current_room:
            asyncio.create_task(self.current_room.disconnect())
        super().closeEvent(event)

    def refresh_room_info(self):
        asyncio.create_task(self._async_refresh_room_info())

    async def _async_refresh_room_info(self):
        if self.current_room:
            try:
                # 更新参与者信息
                await self.update_participants_info()
                
                # 刷新本地参与者信息
                local_participant = self.current_room.local_participant
                logger.info(f"本地参与者: {local_participant.identity}")
                for track in local_participant.track_publications.values():
                    logger.info(f"本地轨道: {track.sid}, 类型: {'音频' if track.kind == TrackKind.KIND_AUDIO else '视频'}")
                
                # 刷新远程参与者信息
                for participant in self.current_room.remote_participants.values():
                    logger.info(f"远程参与者: {participant.identity}")
                    for track in participant.track_publications.values():
                        logger.info(f"远程轨道: {track.sid}, 类型: {'音频' if track.kind == TrackKind.KIND_AUDIO else '视频'}, 已订阅: {track.subscribed}")
                
                logger.info("刷新了房间信息")
            except Exception as e:
                logger.error(f"刷新房间信息时发生错误: {traceback.format_exc()}")
        else:
            logger.warning("尝试刷新房间信息，但未连接到房间")

    def on_subscribe_track(self, participant, track_id):
        asyncio.create_task(self._async_subscribe_track(participant, track_id))

    def on_unsubscribe_track(self, participant, track_id):
        asyncio.create_task(self._async_unsubscribe_track(participant, track_id))

    async def _async_subscribe_track(self, participant, track_id):
        if self.current_room:
            try:
                participant_obj = self.current_room.remote_participants.get(participant)
                if participant_obj:
                    track_publication = participant_obj.track_publications.get(track_id)
                    if track_publication:
                        if not track_publication.subscribed:
                            # 直接设置 subscribed 属性为 True
                            track_publication.subscribed = True
                            
                            track = track_publication.track
                            if track:
                                track_type = "Audio" if track_publication.kind == TrackKind.KIND_AUDIO else "Video"
                                self.subscribed_tracks.add_track(participant, track_id, track_type)
                                
                                # 切换到已订阅轨道页面
                                self.switchTo(self.subscribed_tracks)
                                
                                logger.info(f"成功订阅轨道: {track_id} 从参与者 {participant}")
                            else:
                                logger.error(f"轨道 {track_id} 不可用")
                        else:
                            logger.info(f"轨道 {track_id} 已经被订阅")
                    else:
                        logger.error(f"无法找到轨道: {track_id}")
                else:
                    logger.error(f"无法找到参与者: {participant}")
            except Exception as e:
                logger.error(f"订阅轨道时发生错误: {traceback.format_exc()}")
        else:
            logger.error("未连接到房间")

        await self.update_participants_info()

    async def _async_unsubscribe_track(self, participant, track_id):
        if self.current_room:
            try:
                participant_obj = self.current_room.remote_participants.get(participant)
                if participant_obj:
                    track_publication = participant_obj.track_publications.get(track_id)
                    if track_publication:
                        if track_publication.subscribed:
                            # 直接���置 subscribed 属性为 False
                            track_publication.subscribed = False
                            
                            if track_id in self.audio_tasks:
                                self.audio_tasks[track_id].cancel()
                                del self.audio_tasks[track_id]
                            if track_id in self.video_tasks:
                                self.video_tasks[track_id].cancel()
                                del self.video_tasks[track_id]
                            
                            self.subscribed_tracks.remove_track(track_id)
                            
                            logger.info(f"成功取消订阅轨道: {track_id} 从参与者 {participant}")
                        else:
                            logger.info(f"轨道 {track_id} 已经被取消订阅")
                    else:
                        logger.error(f"无法找到轨道: {track_id}")
                else:
                    logger.error(f"无法找到参与者: {participant}")
            except Exception as e:
                logger.error(f"取消订阅轨道时发生错误: {traceback.format_exc()}")
        else:
            logger.error("未连接到房间")

        # 更新参与者与轨道表格
        await self.update_participants_info()

    async def handle_audio_track(self, audio_track: rtc.RemoteAudioTrack):
        try:
            # 创建保存音频的目录
            audio_dir = os.path.join(os.getcwd(), "recorded_audio")
            os.makedirs(audio_dir, exist_ok=True)

            # 创建 WAV 文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audio_{audio_track.sid}_{timestamp}.wav"
            filepath = os.path.join(audio_dir, filename)

            # WAV 文件参数
            channels = 1
            sample_width = 2  # 16-bit
            frame_rate = 48000  # 假设采样率为 48kHz，根据实际情况调整

            with wave.open(filepath, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(frame_rate)

                logger.info(f"开始录制音频到文件: {filepath}")

                while True:
                    try:
                        audio_frame = await audio_track.receive()
                        audio_data = audio_frame.data
                        if isinstance(audio_data, np.ndarray):
                            audio_data = audio_data.astype(np.int16).tobytes()
                        wav_file.writeframes(audio_data)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"接收音频帧时发生错误: {str(e)}")
                        break

                logger.info(f"音频录制已完成: {filepath}")

        except Exception as e:
            logger.error(f"处理音频轨道时发生错误: {traceback.format_exc()}")

    async def handle_video_track(self, video_track: rtc.RemoteVideoTrack):
        try:
            logger.info(f"开始处理视频轨道: {video_track.sid}")

            while True:
                try:
                    video_frame = await video_track.receive()
                    logger.info(f"接收到视频帧: {video_frame}")
                    # TODO: 处理视频帧，例如显示在UI上或保存
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"接收视频帧时发生错误: {str(e)}")
                    break

            logger.info(f"视频轨道处理已完成: {video_track.sid}")

        except Exception as e:
            logger.error(f"处理视频轨道时发生错误: {traceback.format_exc()}")

    def stop_recording(self, track_id):
        # 这个方法应该被调用来停止特定轨道的录音
        # 你需要实现一种方式来触发 stop_event
        pass

    def on_play_track(self, track_id, track_type):
        asyncio.create_task(self._async_play_track(track_id, track_type))

    def on_record_track(self, track_id, track_type):
        asyncio.create_task(self._async_record_track(track_id, track_type))

    async def _async_play_track(self, track_id, track_type):
        if self.current_room:
            for participant in self.current_room.remote_participants.values():
                track_publication = participant.track_publications.get(track_id)
                if track_publication:
                    track = track_publication.track
                    if track:
                        if track_type == "Audio":
                            audio_stream = rtc.AudioStream(track=track)
                            await self.subscribed_tracks.play_audio_stream(audio_stream)
                        elif track_type == "Video":
                            video_stream = rtc.VideoStream(track, format=rtc.VideoBufferType.RGB24)
                            await self.subscribed_tracks.play_video_stream(video_stream)
                    break

    async def _async_record_track(self, track_id, track_type):
        if self.current_room:
            try:
                for participant in self.current_room.remote_participants.values():
                    track_publication = participant.track_publications.get(track_id)
                    if track_publication:
                        track = track_publication.track
                        if track:
                            if track_type == "Audio":
                                audio_stream = rtc.AudioStream(track=track)
                                await self.subscribed_tracks.record_audio_stream(audio_stream, track_id)
                            elif track_type == "Video":
                                video_stream = rtc.VideoStream(track, format=rtc.VideoBufferType.RGB24)
                                await self.subscribed_tracks.record_video_stream(video_stream, track_id)
                            logger.info(f"开始录制 {track_type} 轨道: {track_id}")
                        else:
                            logger.error(f"轨道 {track_id} 不可用")
                        break
                else:
                    logger.error(f"未找到轨道: {track_id}")
            except Exception as e:
                logger.error(f"录制轨道时发生错误: {str(e)}")
                logger.error(traceback.format_exc())
        else:
            logger.error("未连接到房间")
