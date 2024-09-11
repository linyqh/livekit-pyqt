from app.core.livekit_manager import LiveKitManager

class MainWindow(LiveKitManager):
    def __init__(self):
        super().__init__()
        # 如果需要，可以在这里添加额外的初始化代码

if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    from qfluentwidgets import FluentTheme, setTheme

    app = QApplication(sys.argv)
    setTheme(FluentTheme.DARK)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())