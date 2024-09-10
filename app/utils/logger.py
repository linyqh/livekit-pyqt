import logging

# 配置日志记录器
logger = logging.getLogger('livekit_manager')
logger.setLevel(logging.DEBUG)

# 创建控制台处理程序
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# 创建文件处理程序
file_handler = logging.FileHandler('livekit_manager.log')
file_handler.setLevel(logging.DEBUG)

# 创建格式化器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 将格式化器添加到处理程序
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# 将处理程序添加到记录器
logger.addHandler(console_handler)
logger.addHandler(file_handler)
