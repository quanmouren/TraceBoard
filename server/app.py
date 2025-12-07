#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/11/15 1:05
@Author      : SiYuan
@Email       : 863909694@qq.com
@File        : TraceBoard-app.py
@Description : 修复了数据库过于庞大导致卡顿的问题
"""

import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from pydantic import BaseModel
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from sqlalchemy.sql import func

# SQLAlchemy 数据库设置
DATABASE_URL = "sqlite:///./key_events.db"  # SQLite 数据库路径

# 创建数据库引擎
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# 基类
Base = declarative_base()


# 按键总计表
class KeyTotalStats(Base):
    __tablename__ = "key_total_stats"

    id = Column(Integer, primary_key=True)
    key_name = Column(String)
    virtual_key_code = Column(Integer, index=True, unique=True)
    total_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    
# 月度
class MonthlyKeyStats(Base):
    __tablename__ = "monthly_key_stats"

    id = Column(Integer, primary_key=True)
    key_name = Column(String)
    virtual_key_code = Column(Integer, index=True)
    stat_month = Column(String(7), index=True)
    monthly_count = Column(Integer, default=0)
    
    __table_args__ = (
        Index('idx_month_key_code', stat_month, virtual_key_code, unique=True),
    )

# 创建数据库表（如果不存在）
Base.metadata.create_all(bind=engine)

# 创建 SessionLocal 作为数据库会话的创建器
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI 应用
app = FastAPI()

# 允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件路径配置
try:
    static_dir = os.path.join(sys._MEIPASS, "static") if getattr(sys, 'frozen', False) else "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
except:
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# 定义按键统计数据模型
class KeyCount(BaseModel):
    key_name: str
    count: int
    virtual_key_code: int


# 返回 HTML 页面
@app.get("/", response_class=HTMLResponse)
async def read_dashboard():
    static_dir_path = os.path.join(os.path.dirname(__file__), 'static')
    html_file_path = os.path.join(static_dir_path, 'index.html')
    
    with open(html_file_path, "r", encoding="utf-8") as file:
        html_content = file.read()
    return HTMLResponse(content=html_content, status_code=200)


# 获取所有按键统计数据
@app.get("/key_counts", response_model=List[KeyCount])
def get_key_counts():
    db = SessionLocal()
    try:
        results = db.query(KeyTotalStats.key_name, KeyTotalStats.virtual_key_code, KeyTotalStats.total_count) \
            .order_by(KeyTotalStats.total_count.desc()) \
            .all()
        
        return [
            {"key_name": row[0], "count": row[2], 'virtual_key_code': row[1]} 
            for row in results
        ]
    finally:
        db.close()


# 定义按键事件创建模型
class KeyEventCreate(BaseModel):
    key_name: str
    virtual_key_code: int


# 插入/更新按键统计数据 
@app.post("/key_events", response_model=KeyEventCreate)
def update_key_stats(key_event: KeyEventCreate):
    db = SessionLocal()
    vk = key_event.virtual_key_code
    current_time = datetime.now()
    current_month = current_time.strftime('%Y-%m')
    
    try:
        # 更新 KeyTotalStats
        total_stat = db.query(KeyTotalStats).filter(KeyTotalStats.virtual_key_code == vk).first()
        if total_stat:
            total_stat.total_count += 1
            total_stat.last_updated = current_time
        else:
            new_total_stat = KeyTotalStats(
                key_name=key_event.key_name,
                virtual_key_code=vk,
                total_count=1,
                last_updated=current_time
            )
            db.add(new_total_stat)

        # 更新 MonthlyKeyStats
        monthly_stat = db.query(MonthlyKeyStats).filter(
            MonthlyKeyStats.virtual_key_code == vk,
            MonthlyKeyStats.stat_month == current_month
        ).first()

        if monthly_stat:
            monthly_stat.monthly_count += 1
        else:
            new_monthly_stat = MonthlyKeyStats(
                key_name=key_event.key_name,
                virtual_key_code=vk,
                stat_month=current_month,
                monthly_count=1
            )
            db.add(new_monthly_stat)

        db.commit()
        return key_event
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database update error: {str(e)}")
    finally:
        db.close()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=21315)