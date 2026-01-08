from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, inspect
from sqlalchemy.orm import declarative_base
from tqdm import tqdm

try:
    from server.app import engine, SessionLocal, Base, KeyTotalStats, MonthlyKeyStats, DBMeta
    print("ℹ️ 成功导入 server.app 的数据库配置和新模型。")
except ImportError as e:
    print(f"❌ 导入失败，无法找到 server.app 模块: {e}")
    print("请确保在项目根目录运行此脚本，且 'server' 目录包含 '__init__.py'。")
    sys.exit(1)


OldBase = declarative_base()


class OldKeyEvent(OldBase):
    __tablename__ = "key_events"

    id = Column(Integer, primary_key=True)
    key_name = Column(String)
    virtual_key_code = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)


def _get_schema_version(db) -> int:
    insp = inspect(engine)
    if "db_meta" not in insp.get_table_names():
        if "key_events" in insp.get_table_names():
            return 0
        return 1

    row = db.query(DBMeta).filter(DBMeta.key == "schema_version").first()
    if not row:
        if "key_events" in insp.get_table_names():
            return 0
        return 1
    try:
        return int(row.value)
    except Exception:
        return 1


def _set_schema_version(db, version: int):
    now = datetime.utcnow()
    row = db.query(DBMeta).filter(DBMeta.key == "schema_version").first()
    if row:
        row.value = str(version)
        row.updated_at = now
    else:
        db.add(DBMeta(key="schema_version", value=str(version), updated_at=now))


def migrate_v0_to_v1():
    db = SessionLocal()
    insp = inspect(engine)

    if "key_events" not in insp.get_table_names():
        print("✅ 未发现旧表 'key_events'，跳过 v0->v1 迁移。")
        db.close()
        return

    print("🚀 检测到旧表 key_events，开始迁移到聚合表（v0 -> v1）...")

    try:
        Base.metadata.create_all(bind=engine)

        total_stats_map = {}
        monthly_stats_map = defaultdict(lambda: {"key_name": "-", "count": 0})  

        
        batch_size = 20000
        last_id = 0

        while True:
            events = (
                db.query(OldKeyEvent)
                .filter(OldKeyEvent.id > last_id)
                .order_by(OldKeyEvent.id.asc())
                .limit(batch_size)
                .all()
            )
            if not events:
                break

            for event in tqdm(events, desc=f"Batch {last_id + 1}~", unit="events"):
                vk = event.virtual_key_code
                if vk is None:
                    continue
                key_name = event.key_name or "-"
                ts = event.timestamp or datetime.utcnow()
                month = ts.strftime("%Y-%m")

                if vk in total_stats_map:
                    total_stats_map[vk]["count"] += 1
                    if ts > total_stats_map[vk]["last_updated"]:
                        total_stats_map[vk]["last_updated"] = ts
                        total_stats_map[vk]["key_name"] = key_name
                else:
                    total_stats_map[vk] = {"key_name": key_name, "count": 1, "last_updated": ts}

                k = (month, vk)
                monthly_stats_map[k]["key_name"] = key_name
                monthly_stats_map[k]["count"] += 1

            last_id = events[-1].id

        print(f"🧩 写入 KeyTotalStats ({len(total_stats_map)} 条)...")
        for vk, data in tqdm(total_stats_map.items(), desc="KeyTotalStats", unit="keys"):
            existing = db.query(KeyTotalStats).filter(KeyTotalStats.virtual_key_code == vk).first()
            if existing:
                existing.total_count += data["count"]
                existing.last_updated = max(existing.last_updated or datetime.utcnow(), data["last_updated"])
                if data["key_name"] and existing.key_name != data["key_name"]:
                    existing.key_name = data["key_name"]
            else:
                db.add(KeyTotalStats(
                    key_name=data["key_name"],
                    virtual_key_code=vk,
                    total_count=data["count"],
                    last_updated=data["last_updated"]
                ))

        print(f"🧩 写入 MonthlyKeyStats ({len(monthly_stats_map)} 条)...")
        for (month, vk), data in tqdm(monthly_stats_map.items(), desc="MonthlyKeyStats", unit="rows"):
            existing = db.query(MonthlyKeyStats).filter(
                MonthlyKeyStats.virtual_key_code == vk,
                MonthlyKeyStats.stat_month == month
            ).first()
            if existing:
                existing.monthly_count += data["count"]
                if data["key_name"] and existing.key_name != data["key_name"]:
                    existing.key_name = data["key_name"]
            else:
                db.add(MonthlyKeyStats(
                    key_name=data["key_name"],
                    virtual_key_code=vk,
                    stat_month=month,
                    monthly_count=data["count"]
                ))

        db.commit()

        OldKeyEvent.__table__.drop(engine, checkfirst=True)
        print("✅ 旧表 'key_events' 已删除。")

        _set_schema_version(db, 1)
        db.commit()
        print("🎉 v0 -> v1 迁移完成。")
    except Exception as e:
        db.rollback()
        print(f"❌ 迁移失败: {e}")
        raise
    finally:
        db.close()


def migrate_v1_to_v2():
    """
    新增表：daily_activity_stats / hotkey_total_stats / hotkey_daily_stats / db_meta
    """
    db = SessionLocal()
    try:
        print("🚀 开始执行 v1 -> v2 升级（创建新聚合表）...")
        Base.metadata.create_all(bind=engine)
        _set_schema_version(db, 2)
        db.commit()
        print("✅ v1 -> v2 升级完成。")
    finally:
        db.close()


def main():
    db = SessionLocal()
    try:
        current = _get_schema_version(db)
    finally:
        db.close()

    print(f"当前数据库 schema_version 推断为: v{current}")

    if current == 0:
        migrate_v0_to_v1()
        current = 1

    if current == 1:
        migrate_v1_to_v2()
        current = 2

    if current >= 2:
        print("✅ 数据库已是最新版本（v2），无需升级。")


if __name__ == "__main__":
    main()
