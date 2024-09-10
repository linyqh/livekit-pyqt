import sys
import asyncio
from qasync import QEventLoop
from PyQt5.QtWidgets import QApplication
from app.main import main

if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        loop.run_until_complete(main())
