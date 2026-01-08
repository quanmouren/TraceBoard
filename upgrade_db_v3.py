from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Tuple, List

SCHEMA_LATEST = 3


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _table_exists(cur: sqlite3.Cursor, name: str) -> bool:
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1;",
        (name,),
    )
    return cur.fetchone() is not None


def _get_schema_version(cur: sqlite3.Cursor) -> int:
    if not _table_exists(cur, "db_meta"):
        return 0 if _table_exists(cur, "key_events") else 1

    cur.execute("SELECT value FROM db_meta WHERE key='schema_version' LIMIT 1;")
    row = cur.fetchone()
    if not row:
        return 0 if _table_exists(cur, "key_events") else 1
    try:
        return int(row[0])
    except Exception:
        return 1


def _set_schema_version(cur: sqlite3.Cursor, ver: int) -> None:
    cur.execute(
        """
        INSERT INTO db_meta(key, value, updated_at)
        VALUES('schema_version', ?, ?)
        ON CONFLICT(key) DO UPDATE SET
          value=excluded.value,
          updated_at=excluded.updated_at;
        """,
        (str(ver), _now_iso()),
    )


def _create_tables(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS db_meta(
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS key_total_stats(
          virtual_key_code INTEGER PRIMARY KEY,
          key_name TEXT,
          total_count INTEGER NOT NULL DEFAULT 0,
          last_updated TEXT
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS monthly_key_stats(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          stat_month TEXT NOT NULL,                 -- YYYY-MM
          virtual_key_code INTEGER NOT NULL,
          key_name TEXT,
          monthly_count INTEGER NOT NULL DEFAULT 0,
          UNIQUE(stat_month, virtual_key_code)
        );
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_monthly_key_stats_month ON monthly_key_stats(stat_month);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_monthly_key_stats_vk ON monthly_key_stats(virtual_key_code);"
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_activity_stats(
          stat_date TEXT PRIMARY KEY,               -- YYYY-MM-DD
          key_presses INTEGER NOT NULL DEFAULT 0,
          hotkey_triggers INTEGER NOT NULL DEFAULT 0
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hourly_activity_stats(
          stat_hour TEXT PRIMARY KEY,               -- YYYY-MM-DD HH
          key_presses INTEGER NOT NULL DEFAULT 0,
          hotkey_triggers INTEGER NOT NULL DEFAULT 0,
          last_updated TEXT
        );
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_hourly_activity_hour ON hourly_activity_stats(stat_hour);"
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hotkey_total_stats(
          hotkey_id TEXT PRIMARY KEY,
          display_name TEXT,
          total_count INTEGER NOT NULL DEFAULT 0,
          last_updated TEXT
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hotkey_daily_stats(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          stat_date TEXT NOT NULL,                  -- YYYY-MM-DD
          hotkey_id TEXT NOT NULL,
          count INTEGER NOT NULL DEFAULT 0,
          UNIQUE(stat_date, hotkey_id)
        );
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_hotkey_daily_date ON hotkey_daily_stats(stat_date);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_hotkey_daily_id ON hotkey_daily_stats(hotkey_id);"
    )


def _progress(total: int):

    try:
        from tqdm import tqdm  
        return tqdm(total=total, desc="Upgrading", unit="rows")
    except Exception:
        class Dummy:
            def __init__(self, total): self.total=total; self.done=0
            def update(self, n):
                self.done += n
                if self.total > 0 and self.done % 50000 == 0:
                    pct = self.done / self.total * 100
                    print(f"Upgrading... {pct:.1f}% ({self.done}/{self.total})")
            def close(self): pass
        return Dummy(total)


def _rebuild_from_key_events(cur: sqlite3.Cursor) -> None:

    cur.execute("DELETE FROM key_total_stats;")
    cur.execute("DELETE FROM monthly_key_stats;")
    cur.execute("DELETE FROM daily_activity_stats;")
    cur.execute("DELETE FROM hourly_activity_stats;")

    if not _table_exists(cur, "key_events"):
        return

    cur.execute("SELECT COUNT(*) FROM key_events;")
    total = cur.fetchone()[0] or 0
    if total == 0:
        return

    import collections
    key_total = collections.Counter()
    monthly = collections.Counter()
    daily = collections.Counter()
    hourly = collections.Counter()
    last_key_name: Dict[int, str] = {}

    CHUNK = 5000
    offset = 0
    pbar = _progress(total)

    while True:
        cur.execute(
            """
            SELECT virtual_key_code, key_name, timestamp
            FROM key_events
            ORDER BY id
            LIMIT ? OFFSET ?;
            """,
            (CHUNK, offset),
        )
        rows = cur.fetchall()
        if not rows:
            break

        for vk, key_name, ts in rows:
            if vk is None or ts is None:
                continue
            vk = int(vk)
            key_total[vk] += 1
            if key_name:
                last_key_name[vk] = str(key_name)

            month = str(ts)[:7]
            day = str(ts)[:10]
            hour = str(ts)[:13] 

            monthly[(month, vk)] += 1
            daily[day] += 1
            hourly[hour] += 1

        offset += CHUNK
        pbar.update(len(rows))

    pbar.close()

    now = _now_iso()

    for vk, cnt in key_total.items():
        cur.execute(
            """
            INSERT INTO key_total_stats(virtual_key_code, key_name, total_count, last_updated)
            VALUES (?, ?, ?, ?);
            """,
            (vk, last_key_name.get(vk), int(cnt), now),
        )

    for (month, vk), cnt in monthly.items():
        cur.execute(
            """
            INSERT INTO monthly_key_stats(stat_month, virtual_key_code, key_name, monthly_count)
            VALUES (?, ?, ?, ?);
            """,
            (month, vk, last_key_name.get(vk), int(cnt)),
        )

    for day, cnt in daily.items():
        cur.execute(
            """
            INSERT INTO daily_activity_stats(stat_date, key_presses, hotkey_triggers)
            VALUES (?, ?, 0);
            """,
            (day, int(cnt)),
        )

    for hour, cnt in hourly.items():
        cur.execute(
            """
            INSERT INTO hourly_activity_stats(stat_hour, key_presses, hotkey_triggers, last_updated)
            VALUES (?, ?, 0, ?);
            """,
            (hour, int(cnt), now),
        )


def _ensure_recent_hours(cur: sqlite3.Cursor, hours: int = 48) -> None:
    end_dt = datetime.now().replace(minute=0, second=0, microsecond=0)
    start_dt = end_dt - timedelta(hours=hours - 1)
    now = _now_iso()
    cur_dt = start_dt
    while cur_dt <= end_dt:
        h = cur_dt.strftime("%Y-%m-%d %H")
        cur.execute(
            """
            INSERT OR IGNORE INTO hourly_activity_stats(stat_hour, key_presses, hotkey_triggers, last_updated)
            VALUES (?, 0, 0, ?);
            """,
            (h, now),
        )
        cur_dt += timedelta(hours=1)


def migrate(db_path: str, drop_old: bool) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    cur = conn.cursor()

    try:
        current = _get_schema_version(cur)
        print(f"当前数据库 schema_version: v{current}")

        _create_tables(cur)

        if current < 3:
            if _table_exists(cur, "key_events"):
                print("🚀 检测到 key_events：从逐条事件重建聚合（包含 hourly_activity_stats）...")
                _rebuild_from_key_events(cur)
                if drop_old:
                    cur.execute("DROP TABLE IF EXISTS key_events;")
                    print("🧹 已删除旧表 key_events（--drop-old）。")
            else:
                print("ℹ️ 未发现 key_events：仅补齐 v3 表结构与最近小时占位。")
                _ensure_recent_hours(cur, hours=48)

            _set_schema_version(cur, 3)
            conn.commit()
            print("🎉 升级完成：schema_version 已设置为 v3。")
        else:
            print("✅ 数据库已是最新版本（v3），无需升级。")
            _ensure_recent_hours(cur, hours=48)
            conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db", help="SQLite 数据库文件路径（例如 key_events.db）")
    ap.add_argument("--drop-old", action="store_true", help="升级成功后删除旧表 key_events（瘦身）")
    args = ap.parse_args()
    migrate(args.db, args.drop_old)


if __name__ == "__main__":
    main()
