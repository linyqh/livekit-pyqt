from app.core.livekit_manager import LiveKitManager
import asyncio
from qasync import QEventLoop

class MainWindow(LiveKitManager):
    def __init__(self):
        super().__init__()
        # 如果需要，可以在这里添加额外的初始化代码

    def stop_track(self, track_id, track_type):
        # 实现停止播放逻辑
        self.subscribed_tracks_widget.stop_playback(track_id, track_type)

if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    from qfluentwidgets import FluentTheme, setTheme

    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    setTheme(FluentTheme.DARK)
    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()