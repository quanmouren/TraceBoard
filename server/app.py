#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/11/15 1:05
@Author      : SiYuan
@Email       : 863909694@qq.com
@File        : TraceBoard-app.py
@Description : 新增快捷键,月度,日,小时统计表,解决卡顿问题
"""

import os
from datetime import datetime, date, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Index, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 数据库
DATABASE_URL = "sqlite:///./key_events.db"  # SQLite 数据库路径
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base = declarative_base()


class DBMeta(Base):
    __tablename__ = "db_meta"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


# 统计表
class KeyTotalStats(Base):
    __tablename__ = "key_total_stats"

    id = Column(Integer, primary_key=True)
    key_name = Column(String)
    virtual_key_code = Column(Integer, index=True, unique=True)
    total_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)


class MonthlyKeyStats(Base):
    __tablename__ = "monthly_key_stats"

    id = Column(Integer, primary_key=True)
    key_name = Column(String)
    virtual_key_code = Column(Integer, index=True)
    stat_month = Column(String(7), index=True)  # YYYY-MM
    monthly_count = Column(Integer, default=0)

    __table_args__ = (
        Index("idx_month_key_code", stat_month, virtual_key_code, unique=True),
    )


# 活跃度 & 快捷键统计
class DailyActivityStats(Base):
    __tablename__ = "daily_activity_stats"

    stat_date = Column(String(10), primary_key=True)  # YYYY-MM-DD

    key_presses = Column(Integer, default=0)
    hotkey_triggers = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class HourlyActivityStats(Base):
    __tablename__ = "hourly_activity_stats"

    stat_hour = Column(String(13), primary_key=True)  # YYYY-MM-DD HH

    key_presses = Column(Integer, default=0)
    hotkey_triggers = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
class HotkeyTotalStats(Base):
    __tablename__ = "hotkey_total_stats"

    id = Column(Integer, primary_key=True)
    hotkey_id = Column(String, index=True, unique=True)  # e.g. "CTRL+C"
    display_name = Column(String, default="")
    total_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)


class HotkeyDailyStats(Base):
    __tablename__ = "hotkey_daily_stats"

    id = Column(Integer, primary_key=True)
    stat_date = Column(String(10), index=True)  # YYYY-MM-DD
    hotkey_id = Column(String, index=True)
    display_name = Column(String, default="")
    daily_count = Column(Integer, default=0)
    last_triggered = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_hotkey_date_id", stat_date, hotkey_id, unique=True),
    )


# 创建数据库表（如果不存在）
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# 定义按键统计数据模型
class KeyCount(BaseModel):
    key_name: str
    count: int
    virtual_key_code: int


class KeyEventCreate(BaseModel):
    key_name: str
    virtual_key_code: int


class ActivityDay(BaseModel):
    date: str  # YYYY-MM-DD
    key_presses: int
    hotkey_triggers: int


class ActivityHour(BaseModel):
    hour: str  # YYYY-MM-DD HH
    key_presses: int
    hotkey_triggers: int


class ActivityMonth(BaseModel):
    month: str  # YYYY-MM
    key_presses: int
    hotkey_triggers: int


class HotkeyTotal(BaseModel):
    hotkey_id: str
    display_name: str
    total_count: int


class HotkeyDay(BaseModel):
    date: str
    count: int


# 工具函数
def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


# 路由
@app.get("/", response_class=HTMLResponse)
async def read_dashboard():
    html_file_path = os.path.join(static_dir, "index.html")
    if not os.path.exists(html_file_path):
        raise HTTPException(status_code=404, detail="index.html not found")
    with open(html_file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.get("/key_counts", response_model=List[KeyCount])
def get_key_counts():
    db = SessionLocal()
    try:
        results = (
            db.query(KeyTotalStats.key_name, KeyTotalStats.virtual_key_code, KeyTotalStats.total_count)
            .order_by(KeyTotalStats.total_count.desc())
            .all()
        )
        return [{"key_name": r[0], "count": r[2], "virtual_key_code": r[1]} for r in results]
    finally:
        db.close()


@app.post("/key_events", response_model=KeyEventCreate)
def record_key_event(key_event: KeyEventCreate):
    db = SessionLocal()
    try:
        vk = key_event.virtual_key_code
        key_name = key_event.key_name
        current_time = datetime.now()

        current_month = current_time.strftime("%Y-%m")
        today = current_time.strftime("%Y-%m-%d")
        current_hour = current_time.strftime("%Y-%m-%d %H")

        total_stat = db.query(KeyTotalStats).filter(KeyTotalStats.virtual_key_code == vk).first()
        if total_stat:
            total_stat.total_count = (total_stat.total_count or 0) + 1
            total_stat.key_name = key_name or total_stat.key_name
            total_stat.last_updated = current_time
        else:
            db.add(
                KeyTotalStats(
                    key_name=key_name,
                    virtual_key_code=vk,
                    total_count=1,
                    last_updated=current_time,
                )
            )

        monthly_stat = (
            db.query(MonthlyKeyStats)
            .filter(MonthlyKeyStats.virtual_key_code == vk, MonthlyKeyStats.stat_month == current_month)
            .first()
        )
        if monthly_stat:
            monthly_stat.monthly_count = (monthly_stat.monthly_count or 0) + 1
            monthly_stat.key_name = key_name or monthly_stat.key_name
        else:
            db.add(
                MonthlyKeyStats(
                    key_name=key_name,
                    virtual_key_code=vk,
                    stat_month=current_month,
                    monthly_count=1,
                )
            )

        daily = db.query(DailyActivityStats).filter(DailyActivityStats.stat_date == today).first()
        if daily:
            daily.key_presses = (daily.key_presses or 0) + 1
            daily.last_updated = current_time
        else:
            db.add(
                DailyActivityStats(
                    stat_date=today,
                    key_presses=1,
                    hotkey_triggers=0,
                    last_updated=current_time,
                )
            )

        hourly = db.query(HourlyActivityStats).filter(HourlyActivityStats.stat_hour == current_hour).first()
        if hourly:
            hourly.key_presses = (hourly.key_presses or 0) + 1
            hourly.last_updated = current_time
        else:
            db.add(
                HourlyActivityStats(
                    stat_hour=current_hour,
                    key_presses=1,
                    hotkey_triggers=0,
                    last_updated=current_time,
                )
            )

        db.commit()
        return key_event

    except Exception as e:
        db.rollback()
        print(f"[WARN] record_key_event 失败: {e}")
        raise HTTPException(status_code=500, detail="record_key_event failed")

    finally:
        db.close()


@app.get("/activity_daily", response_model=List[ActivityDay])
def get_activity_daily(days: int = 120, end_date: Optional[str] = None):
    if days <= 0 or days > 3650:
        raise HTTPException(status_code=400, detail="days must be within 1..3650")

    end = date.today() if not end_date else datetime.strptime(end_date, "%Y-%m-%d").date()
    start = end - timedelta(days=days - 1)

    db = SessionLocal()
    try:
        rows = (
            db.query(DailyActivityStats.stat_date, DailyActivityStats.key_presses, DailyActivityStats.hotkey_triggers)
            .filter(DailyActivityStats.stat_date >= start.strftime("%Y-%m-%d"))
            .filter(DailyActivityStats.stat_date <= end.strftime("%Y-%m-%d"))
            .all()
        )
        mp = {r[0]: (r[1] or 0, r[2] or 0) for r in rows}
        out: List[ActivityDay] = []
        for d in _daterange(start, end):
            ds = d.strftime("%Y-%m-%d")
            kp, hk = mp.get(ds, (0, 0))
            out.append(ActivityDay(date=ds, key_presses=int(kp), hotkey_triggers=int(hk)))
        return out
    finally:
        db.close()


@app.get("/activity_hourly", response_model=List[ActivityHour])
def get_activity_hourly(hours: int = 24, end_hour: Optional[str] = None):
    if hours <= 0 or hours > 24 * 60:
        raise HTTPException(status_code=400, detail="hours must be within 1..1440")

    # 末尾小时：默认当前小时（整点）
    if end_hour:
        try:
            end_dt = datetime.strptime(end_hour, "%Y-%m-%d %H")
        except ValueError:
            raise HTTPException(status_code=400, detail="end_hour must be YYYY-MM-DD HH")
    else:
        now = datetime.now()
        end_dt = now.replace(minute=0, second=0, microsecond=0)

    start_dt = end_dt - timedelta(hours=hours - 1)
    start_key = start_dt.strftime("%Y-%m-%d %H")
    end_key = end_dt.strftime("%Y-%m-%d %H")

    db = SessionLocal()
    try:
        rows = (
            db.query(HourlyActivityStats.stat_hour, HourlyActivityStats.key_presses, HourlyActivityStats.hotkey_triggers)
            .filter(HourlyActivityStats.stat_hour >= start_key, HourlyActivityStats.stat_hour <= end_key)
            .order_by(HourlyActivityStats.stat_hour.asc())
            .all()
        )
        mp = {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in rows}

        out: List[ActivityHour] = []
        cur = start_dt
        for _ in range(hours):
            hk = cur.strftime("%Y-%m-%d %H")
            kp, ht = mp.get(hk, (0, 0))
            out.append(ActivityHour(hour=hk, key_presses=kp, hotkey_triggers=ht))
            cur += timedelta(hours=1)
        return out
    finally:
        db.close()


@app.get("/activity_monthly", response_model=List[ActivityMonth])
def get_activity_monthly(months: int = 24, end_month: Optional[str] = None):
    if months <= 0 or months > 240:
        raise HTTPException(status_code=400, detail="months must be within 1..240")

    if end_month:
        end_dt = datetime.strptime(end_month + "-01", "%Y-%m-%d").date()
    else:
        today = date.today()
        end_dt = today.replace(day=1)

    y, m = end_dt.year, end_dt.month
    total = y * 12 + (m - 1)
    start_total = total - (months - 1)
    start_y, start_m = divmod(start_total, 12)
    start_m += 1
    start_dt = date(start_y, start_m, 1)

    end_total = total + 1
    end_y, end_m = divmod(end_total, 12)
    end_m += 1
    next_month_first = date(end_y, end_m, 1)
    end_last = next_month_first - timedelta(days=1)

    db = SessionLocal()
    try:
        rows = (
            db.query(DailyActivityStats.stat_date, DailyActivityStats.key_presses, DailyActivityStats.hotkey_triggers)
            .filter(DailyActivityStats.stat_date >= start_dt.strftime("%Y-%m-%d"))
            .filter(DailyActivityStats.stat_date <= end_last.strftime("%Y-%m-%d"))
            .all()
        )

        agg = {}
        for ds, kp, hk in rows:
            month = ds[:7]
            a = agg.get(month, (0, 0))
            agg[month] = (a[0] + int(kp or 0), a[1] + int(hk or 0))

        out: List[ActivityMonth] = []
        cur_y, cur_m = start_dt.year, start_dt.month
        for _ in range(months):
            month_str = f"{cur_y:04d}-{cur_m:02d}"
            kp, hk = agg.get(month_str, (0, 0))
            out.append(ActivityMonth(month=month_str, key_presses=kp, hotkey_triggers=hk))

            cur_m += 1
            if cur_m == 13:
                cur_m = 1
                cur_y += 1

        return out
    finally:
        db.close()


@app.get("/hotkey_totals", response_model=List[HotkeyTotal])
def get_hotkey_totals(limit: int = 20):
    if limit <= 0 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be within 1..200")
    db = SessionLocal()
    try:
        rows = (
            db.query(HotkeyTotalStats.hotkey_id, HotkeyTotalStats.display_name, HotkeyTotalStats.total_count)
            .order_by(HotkeyTotalStats.total_count.desc())
            .limit(limit)
            .all()
        )
        return [HotkeyTotal(hotkey_id=r[0], display_name=r[1] or r[0], total_count=int(r[2] or 0)) for r in rows]
    finally:
        db.close()


@app.get("/hotkey_series", response_model=List[HotkeyDay])
def get_hotkey_series(hotkey_id: str, days: int = 120, end_date: Optional[str] = None):
    if not hotkey_id:
        raise HTTPException(status_code=400, detail="hotkey_id is required")
    if days <= 0 or days > 3650:
        raise HTTPException(status_code=400, detail="days must be within 1..3650")

    is_all = (hotkey_id == "__ALL__") or (hotkey_id.strip().upper() in ("ALL", "ALL_HOTKEYS"))

    end = date.today() if not end_date else datetime.strptime(end_date, "%Y-%m-%d").date()
    start = end - timedelta(days=days - 1)

    db = SessionLocal()
    try:
        if not is_all:
            rows = (
                db.query(HotkeyDailyStats.stat_date, HotkeyDailyStats.daily_count)
                .filter(
                    HotkeyDailyStats.hotkey_id == hotkey_id,
                    HotkeyDailyStats.stat_date >= start.strftime("%Y-%m-%d"),
                    HotkeyDailyStats.stat_date <= end.strftime("%Y-%m-%d"),
                )
                .order_by(HotkeyDailyStats.stat_date.asc())
                .all()
            )
        else:
            rows = (
                db.query(
                    HotkeyDailyStats.stat_date,
                    func.sum(HotkeyDailyStats.daily_count).label("daily_count"),
                )
                .filter(
                    HotkeyDailyStats.stat_date >= start.strftime("%Y-%m-%d"),
                    HotkeyDailyStats.stat_date <= end.strftime("%Y-%m-%d"),
                )
                .group_by(HotkeyDailyStats.stat_date)
                .order_by(HotkeyDailyStats.stat_date.asc())
                .all()
            )

        mp = {r[0]: int(r[1] or 0) for r in rows}
        out: List[HotkeyDay] = []
        for d in _daterange(start, end):
            ds = d.strftime("%Y-%m-%d")
            out.append(HotkeyDay(date=ds, count=mp.get(ds, 0)))
        return out
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=21315)
