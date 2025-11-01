from logging import DEBUG, INFO, Formatter, StreamHandler, getLogger
from logging.handlers import TimedRotatingFileHandler

# 日志格式化器
# 获取或创建日志器，通过名字把日志通道组织成层级树，实现分级过滤，分级输出，模块级隔离


def set_logger(log_level=DEBUG, log_path=None):
    '''设置日志器'''

    root_logger = getLogger()
    root_logger.setLevel(log_level)
    formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    console_handler = StreamHandler()
    console_handler.setLevel(INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_path:
        file_handler = TimedRotatingFileHandler(log_path, 'm', 10, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
