#!/usr/bin/env python
# -*- coding: utf-8 -*-\

"""
@Time        : 2024/11/15 1:09
@Author      : SiYuan
@Email       : 863909694@qq.com
@File        : TraceBoard-keyboard.py
@Description : 将数据表整体结构拆分为两个表
"""
from pynput.keyboard import Key
from pynput import keyboard
import datetime
import os
import sys

DB_COMPONENTS_LOADED = False
try:
    from server.app import SessionLocal, KeyTotalStats, MonthlyKeyStats
    DB_COMPONENTS_LOADED = True
except ImportError as e:
    print(f"FATAL: 无法从 'server.app' 导入数据库组件: {e}")
    print("键盘监听功能将无法保存数据！请确保在项目根目录运行。")

# 用于追踪已按下的键
pressed_keys = set()


# 插入按键信息到数据库 
def update_key_stats_in_db(key_name: str, virtual_key_code: int):
    if not DB_COMPONENTS_LOADED:
        return 
    
    db = SessionLocal()
    vk = virtual_key_code
    current_time = datetime.datetime.now()
    current_month = current_time.strftime('%Y-%m')

    try:
        # 更新总计
        total_stat = db.query(KeyTotalStats).filter(KeyTotalStats.virtual_key_code == vk).first()
        if total_stat:
            total_stat.total_count += 1
            total_stat.last_updated = current_time
        else:
            new_total_stat = KeyTotalStats(
                key_name=key_name,
                virtual_key_code=vk,
                total_count=1,
                last_updated=current_time
            )
            db.add(new_total_stat)

        # 更新月统计
        monthly_stat = db.query(MonthlyKeyStats).filter(
            MonthlyKeyStats.virtual_key_code == vk,
            MonthlyKeyStats.stat_month == current_month
        ).first()

        if monthly_stat:
            monthly_stat.monthly_count += 1
        else:
            new_monthly_stat = MonthlyKeyStats(
                key_name=key_name,
                virtual_key_code=vk,
                stat_month=current_month,
                monthly_count=1
            )
            db.add(new_monthly_stat)
            
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error updating stats in DB: {e}")
    finally:
        db.close()


# 键盘按下事件处理函数
def on_press(key):
    try:
        vk = None
        key_name = '-'

        if isinstance(key, Key):
            if hasattr(key.value, 'vk') and key.value.vk is not None:
                 vk = key.value.vk
                 key_name = key.name
            
        elif hasattr(key, 'vk') and key.vk is not None:
            vk = key.vk
            key_name = getattr(key, 'char', '-')

        if not isinstance(vk, int):
            return

        if vk not in pressed_keys:
            update_key_stats_in_db(key_name, vk) 
            pressed_keys.add(vk)
            
    except Exception as e:
        print(f"Error in on_press: {e}")

def on_release(key):
    try:
        if isinstance(key, Key):
            vk = key.value.vk if hasattr(key.value, 'vk') else None
        else:
            vk = key.vk if hasattr(key, 'vk') else None
        
        if isinstance(vk, int) and vk in pressed_keys:
            pressed_keys.remove(vk)
    except Exception as e:
        print(f"Error in on_release: {e}")

# 启动监听器
def start_listener():
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

if __name__ == '__main__':
    start_listener()