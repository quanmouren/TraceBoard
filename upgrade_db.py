from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from tqdm import tqdm 
import os
import sys


try:
    from server.app import engine, SessionLocal, Base, KeyTotalStats, MonthlyKeyStats
    print("ℹ️ 成功导入 server.app 的数据库配置和新模型。")
except ImportError as e:
    print(f"❌ 导入失败，无法找到 server.app 模块: {e}")
    print("请确保在项目根目录运行此脚本，且 'server' 目录包含 '__init__.py'。")
    sys.exit(1)


class OldKeyEvent(Base):
    __tablename__ = "key_events"

    id = Column(Integer, primary_key=True)
    key_name = Column(String)
    virtual_key_code = Column(Integer)
    timestamp = Column(DateTime)
    
def migrate_database():
    print("--- ⌨️ 数据库升级开始 ---")
    db = SessionLocal()
    
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ 数据库表结构已更新/确认。")
        print("⚠️ 正在清理目标表中的现有数据，确保迁移成功...")
        db.query(KeyTotalStats).delete()
        db.query(MonthlyKeyStats).delete()
        db.commit()
        print("✅ 已清理目标表 KeyTotalStats 和 MonthlyKeyStats。")

        if not engine.dialect.has_table(engine.connect(), "key_events"):
            print("ℹ️ 旧表 'key_events' 不存在，无需迁移。")
            return
            
        total_records = db.query(func.count(OldKeyEvent.id)).scalar()
        if total_records is None or total_records == 0:
            print("ℹ️ 旧表 'key_events' 中没有数据，无需迁移。")
            return

        print(f"总计找到 {total_records} 条旧按键记录，开始聚合...")

        batch_size = 50000 
        
        total_stats_map = {} 
        monthly_stats_map = {} 

        offset = 0
        with tqdm(total=total_records, desc="聚合历史数据") as pbar:
            while True:
                batch = db.query(OldKeyEvent) \
                    .order_by(OldKeyEvent.id) \
                    .offset(offset) \
                    .limit(batch_size) \
                    .all()
                
                if not batch:
                    break
                
                for event in batch:
                    vk = event.virtual_key_code
                    key_name = event.key_name or '-'
                    if not event.timestamp:
                        continue
                        
                    stat_month = event.timestamp.strftime('%Y-%m')

                    total_stats_map[vk] = (key_name, total_stats_map.get(vk, ('', 0))[1] + 1)
                    
                    monthly_key = (stat_month, vk)
                    monthly_stats_map[monthly_key] = (key_name, monthly_stats_map.get(monthly_key, ('', 0))[1] + 1)

                offset += len(batch)
                pbar.update(len(batch))
        
        db.close()
        db = SessionLocal() 

        print("\n正在写入 KeyTotalStats...")
        total_stats_to_insert = [
            KeyTotalStats(
                key_name=data[0],
                virtual_key_code=vk,
                total_count=data[1],
                last_updated=datetime.now()
            ) for vk, data in total_stats_map.items()
        ]
        db.bulk_save_objects(total_stats_to_insert)
        print(f"✅ KeyTotalStats 写入完成 ({len(total_stats_to_insert)} 条记录)。")

        print("正在写入 MonthlyKeyStats...")
        monthly_stats_to_insert = [
            MonthlyKeyStats(
                key_name=data[0],
                virtual_key_code=vk,
                stat_month=month,
                monthly_count=data[1]
            ) for (month, vk), data in monthly_stats_map.items()
        ]
        db.bulk_save_objects(monthly_stats_to_insert)
        print(f"✅ MonthlyKeyStats 写入完成 ({len(monthly_stats_to_insert)} 条记录)。")

        db.commit()
        
        OldKeyEvent.__table__.drop(engine, checkfirst=True)
        print("✅ 旧表 'key_events' 已清理/删除。")


        print("\n--- 🎉 数据库升级成功！系统已切换到高性能聚合模式。 ---")

    except Exception as e:
        db.rollback()
        print(f"\n❌ 数据库迁移失败: {e}")
        print("请检查错误信息，通常是数据库连接或权限问题。")
    finally:
        db.close()


if __name__ == "__main__":
    migrate_database()