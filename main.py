#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/11/13 23:16 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : TraceBoard-main.py 
@Description : 
"""

import os

import threading
import webbrowser
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw

from uvicorn import Config, Server

from listener.keyboard import start_listener
from log import logger

from server import app, static_dir

from win10toast import ToastNotifier
import tomllib

# 启动键盘监听的同时运行FastAPI服务器
def start_api():
    # import uvicorn
    # uvicorn.run(app, host="127.0.0.1", port=21315)
    log_config = {
        "version": 1,
        "disable_existing_loggers": True,
        "handlers": {
            "file_handler": {
                "class": "logging.FileHandler",
                "filename": "app.log",
            },
        },
        "root": {
            "handlers": ["file_handler"],
            "level": "ERROR",
        },
    }
    config = Config(app=app, host="127.0.0.1", port=21315, log_config=log_config)
    server = Server(config=config)
    server.run()


# 创建托盘图标图像
def create_image(width: int, height: int, color1, color2):
    image = Image.new("RGB", (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        [(width // 4, height // 4), (width * 3 // 4, height * 3 // 4)], fill=color2
    )
    image = Image.open(os.path.join(static_dir, 'logo3.0.ico'))
    return image


# 托盘图标菜单
def setup_tray_icon():
    icon_image = create_image(64, 64, "black", "white")
    tray_icon = Icon("Keyboard Monitor", icon_image, '打开统计面板', menu=Menu(
        MenuItem("查看统计", open_dashboard),
        MenuItem("退出软件", exit_app)
    ))
    tray_icon.run()


# 打开前端 HTML 页面
def open_dashboard(icon, item):
    webbrowser.open("http://127.0.0.1:21315/")


# 退出程序
def exit_app(icon, item):
    icon.stop()
    os._exit(0)


# 主线程启动
if __name__ == "__main__":
    # 启动键盘监听器和 API 服务器
    threading.Thread(target=start_listener).start()
    threading.Thread(target=start_api).start()
    with open("config.toml", "br") as f:
        data = tomllib.load(f)
    if data.get('startup_items', {}).get('open_web', False):
        webbrowser.open("http://127.0.0.1:21315/")
    if data.get('startup_items', {}).get('show_notification', False):
        ToastNotifier().show_toast(
        title="TraceBoard",
        msg="启动成功",
        icon_path="server\\static\\logo3.0.ico",
        duration=1,
        threaded=True
        )
    # 设置托盘图标
    setup_tray_icon()
