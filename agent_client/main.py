import sys

from PySide6.QtWidgets import QApplication

from src.client.main_window import MainWindow

if __name__ == '__main__':
    app = QApplication()  # 图形应用的强制性控制核心，初始化底层资源，启动事件循环，驱动程序的响应，运行，退出
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())
    # 终止程序运行
    # 启动并管理应用程序的事件循环
