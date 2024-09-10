import sys
import os
import asyncio
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from qfluentwidgets import setTheme, Theme
from app.ui.main_window import LiveKitManager
from app.utils.logger import logger

# 设置默认字体
QApplication.setFont(QFont('Arial', 9))  # 使用 Arial 字体，大小为 9
os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false'


async def main():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    setTheme(Theme.DARK)
    window = LiveKitManager()
    window.show()

    logger.info("LiveKit 管理工具已启动")

    # 创建一个永不完成的future，以保持事件循环运行
    await asyncio.Future()
