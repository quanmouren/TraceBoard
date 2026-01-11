#!/usr/bin/env python
# -*- coding: utf-8 -*-\

"""
@Time        : 2024/11/15 1:09
@Author      : SiYuan
@Email       : 863909694@qq.com
@File        : TraceBoard-keyboard.py
@Description : 重建数据表结构
"""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional, Set, Tuple

from pynput.keyboard import Key
from pynput import keyboard

DB_COMPONENTS_LOADED = False
try:
    from server.app import (
        SessionLocal,
        KeyTotalStats,
        MonthlyKeyStats,
        DailyActivityStats,
        HourlyActivityStats,
        HotkeyTotalStats,
        HotkeyDailyStats,
    )
    DB_COMPONENTS_LOADED = True
except Exception as e:
    print(f"FATAL: 无法从 'server.app' 导入数据库组件: {e}")
    print("键盘监听功能将无法保存数据！请确保在项目根目录运行。")


pressed_vks: Set[int] = set()
_active_hotkeys: Set[str] = set()

MOD_VK: Dict[str, Set[int]] = {
    "CTRL": {162, 163},   # VK_LCONTROL / VK_RCONTROL
    "SHIFT": {160, 161},  # VK_LSHIFT / VK_RSHIFT
    "ALT": {164, 165},    # VK_LMENU / VK_RMENU
    "WIN": {91, 92},      # VK_LWIN / VK_RWIN
}

HOTKEY_DEFS: List[Dict[str, object]] = [
    {"hotkey_id": "CTRL+C", "display_name": "Ctrl + C（复制）", "mods": ["CTRL"], "key_vk": 67},
    {"hotkey_id": "CTRL+V", "display_name": "Ctrl + V（粘贴）", "mods": ["CTRL"], "key_vk": 86},
    {"hotkey_id": "CTRL+X", "display_name": "Ctrl + X（剪切）", "mods": ["CTRL"], "key_vk": 88},
    {"hotkey_id": "CTRL+Z", "display_name": "Ctrl + Z（撤销）", "mods": ["CTRL"], "key_vk": 90},
    {"hotkey_id": "CTRL+Y", "display_name": "Ctrl + Y（重做）", "mods": ["CTRL"], "key_vk": 89},
    {"hotkey_id": "CTRL+S", "display_name": "Ctrl + S（保存）", "mods": ["CTRL"], "key_vk": 83},
    {"hotkey_id": "CTRL+F", "display_name": "Ctrl + F（查找）", "mods": ["CTRL"], "key_vk": 70},
    {"hotkey_id": "CTRL+A", "display_name": "Ctrl + A（全选）", "mods": ["CTRL"], "key_vk": 65},
    {"hotkey_id": "CTRL+W", "display_name": "Ctrl + W（关闭标签/窗口）", "mods": ["CTRL"], "key_vk": 87},
    {"hotkey_id": "CTRL+T", "display_name": "Ctrl + T（新建标签）", "mods": ["CTRL"], "key_vk": 84},

    {"hotkey_id": "ALT+TAB", "display_name": "Alt + Tab（切换窗口）", "mods": ["ALT"], "key_vk": 9},
    {"hotkey_id": "ALT+F4", "display_name": "Alt + F4（关闭窗口）", "mods": ["ALT"], "key_vk": 115},

    {"hotkey_id": "WIN+D", "display_name": "Win + D（显示桌面）", "mods": ["WIN"], "key_vk": 68},
    {"hotkey_id": "WIN+E", "display_name": "Win + E（资源管理器）", "mods": ["WIN"], "key_vk": 69},
    {"hotkey_id": "WIN+L", "display_name": "Win + L（锁屏）", "mods": ["WIN"], "key_vk": 76},

    {"hotkey_id": "CTRL+SHIFT+ESC", "display_name": "Ctrl + Shift + Esc（任务管理器）", "mods": ["CTRL", "SHIFT"], "key_vk": 27},
    {"hotkey_id": "CTRL+ALT+DEL", "display_name": "Ctrl + Alt + Del（安全选项）", "mods": ["CTRL", "ALT"], "key_vk": 46},
]


def _mods_pressed(mods: List[str], current_pressed: Set[int]) -> bool:
    for m in mods:
        vks = MOD_VK.get(m)
        if not vks:
            return False
        if not (current_pressed & vks):
            return False
    return True


def _maybe_trigger_hotkeys(trigger_vk: int, current_pressed: Set[int]) -> List[Tuple[str, str]]:
    """
    只在“触发键”按下时判断，避免修饰键按下时误计数
    返回：(hotkey_id, display_name)
    """
    fired: List[Tuple[str, str]] = []
    for d in HOTKEY_DEFS:
        if int(d["key_vk"]) != trigger_vk:
            continue
        mods = d.get("mods", [])
        if not isinstance(mods, list):
            continue
        if _mods_pressed(mods, current_pressed):
            fired.append((str(d["hotkey_id"]), str(d["display_name"])))
    return fired

def update_key_stats_in_db(key_name: str, virtual_key_code: int):

    if not DB_COMPONENTS_LOADED:
        return

    db = SessionLocal()
    vk = int(virtual_key_code)
    now = datetime.datetime.now()
    current_month = now.strftime("%Y-%m")
    today = now.strftime("%Y-%m-%d")
    current_hour = now.strftime("%Y-%m-%d %H")

    try:
        # 总计
        total_stat = db.query(KeyTotalStats).filter(KeyTotalStats.virtual_key_code == vk).first()
        if total_stat:
            total_stat.total_count += 1
            total_stat.last_updated = now
            if key_name:
                total_stat.key_name = key_name
        else:
            db.add(KeyTotalStats(
                key_name=key_name,
                virtual_key_code=vk,
                total_count=1,
                last_updated=now
            ))

        # 月度
        monthly_stat = db.query(MonthlyKeyStats).filter(
            MonthlyKeyStats.virtual_key_code == vk,
            MonthlyKeyStats.stat_month == current_month
        ).first()
        if monthly_stat:
            monthly_stat.monthly_count += 1
            if key_name and not monthly_stat.key_name:
                monthly_stat.key_name = key_name
        else:
            db.add(MonthlyKeyStats(
                key_name=key_name,
                virtual_key_code=vk,
                stat_month=current_month,
                monthly_count=1
            ))

        # 日活跃度
        daily = db.query(DailyActivityStats).filter(DailyActivityStats.stat_date == today).first()
        if daily:
            daily.key_presses += 1
            daily.last_updated = now
        else:
            db.add(DailyActivityStats(
                stat_date=today,
                key_presses=1,
                hotkey_triggers=0,
                last_updated=now
            ))

        # 最近24小时
        hourly = db.query(HourlyActivityStats).filter(HourlyActivityStats.stat_hour == current_hour).first()
        if hourly:
            hourly.key_presses += 1
            hourly.last_updated = now
        else:
            db.add(HourlyActivityStats(
                stat_hour=current_hour,
                key_presses=1,
                hotkey_triggers=0,
                last_updated=now
            ))

        try:
            update_key_stats_in_db._gc_counter = getattr(update_key_stats_in_db, "_gc_counter", 0) + 1
            if update_key_stats_in_db._gc_counter % 2000 == 0:
                cutoff = (now - datetime.timedelta(days=10)).strftime("%Y-%m-%d %H")
                db.query(HourlyActivityStats).filter(HourlyActivityStats.stat_hour < cutoff).delete(synchronize_session=False)
        except Exception:
            pass

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error updating key stats: {e}")
    finally:
        db.close()



def update_hotkey_stats_in_db(hotkey_id: str, display_name: str):
    if not DB_COMPONENTS_LOADED:
        return

    db = SessionLocal()
    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_hour = now.strftime("%Y-%m-%d %H")

    try:
        # hotkey 总计
        total = db.query(HotkeyTotalStats).filter(HotkeyTotalStats.hotkey_id == hotkey_id).first()
        if total:
            total.total_count = (total.total_count or 0) + 1
            total.last_updated = now
            if display_name:
                total.display_name = display_name
        else:
            db.add(HotkeyTotalStats(
                hotkey_id=hotkey_id,
                display_name=display_name,
                total_count=1,
                last_updated=now
            ))

        # hotkey 每日
        daily_hot = db.query(HotkeyDailyStats).filter(
            HotkeyDailyStats.hotkey_id == hotkey_id,
            HotkeyDailyStats.stat_date == today
        ).first()
        if daily_hot:
            daily_hot.daily_count = (daily_hot.daily_count or 0) + 1
            daily_hot.last_triggered = now
            if display_name:
                daily_hot.display_name = display_name
        else:
            db.add(HotkeyDailyStats(
                stat_date=today,
                hotkey_id=hotkey_id,
                daily_count=1,
                display_name=display_name,
                last_triggered=now
            ))

        # 日活跃度
        daily = db.query(DailyActivityStats).filter(DailyActivityStats.stat_date == today).first()
        if daily:
            daily.hotkey_triggers += 1
            daily.last_updated = now
        else:
            db.add(DailyActivityStats(
                stat_date=today,
                key_presses=0,
                hotkey_triggers=1,
                last_updated=now
            ))

        # 小时活跃度
        hourly_hot = db.query(HourlyActivityStats).filter(HourlyActivityStats.stat_hour == current_hour).first()
        if hourly_hot:
            hourly_hot.hotkey_triggers += 1
            hourly_hot.last_updated = now
        else:
            db.add(HourlyActivityStats(
                stat_hour=current_hour,
                key_presses=0,
                hotkey_triggers=1,
                last_updated=now
            ))

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error updating hotkey stats: {e}")
    finally:
        db.close()


def _extract_vk_and_name(key) -> Tuple[Optional[int], str]:

    vk: Optional[int] = None
    name: str = "-"

    try:
        if isinstance(key, Key):
            if hasattr(key.value, "vk") and key.value.vk is not None:
                vk = int(key.value.vk)
            name = getattr(key, "name", str(key))
        else:
            if hasattr(key, "vk") and key.vk is not None:
                vk = int(key.vk)
            name = getattr(key, "char", "-") or "-"
    except Exception:
        return None, "-"

    return vk, name


def on_press(key):
    try:
        vk, key_name = _extract_vk_and_name(key)
        if not isinstance(vk, int):
            return

        if vk in pressed_vks:
            return

        pressed_vks.add(vk)

        update_key_stats_in_db(key_name, vk)

        fired = _maybe_trigger_hotkeys(vk, pressed_vks)
        for hotkey_id, display in fired:
            update_hotkey_stats_in_db(hotkey_id, display)
            _active_hotkeys.add(hotkey_id)

    except Exception as e:
        print(f"Error in on_press: {e}")


def on_release(key):
    try:
        vk, _ = _extract_vk_and_name(key)
        if isinstance(vk, int) and vk in pressed_vks:
            pressed_vks.remove(vk)

        if isinstance(vk, int):
            if vk in MOD_VK["CTRL"] or vk in MOD_VK["ALT"] or vk in MOD_VK["SHIFT"] or vk in MOD_VK["WIN"]:
                _active_hotkeys.clear()

    except Exception as e:
        print(f"Error in on_release: {e}")


def start_listener():
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":
    start_listener()