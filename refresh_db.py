#!/usr/bin/env python3
"""
refresh_db.py
将 dashboard_data.json 中的数据刷新到 NoCode 数据库的三张表。

用法：
  python kanban-scripts/refresh_db.py

认证方式：
  优先读取环境变量 SUPABASE_URL / SUPABASE_ANON_KEY
  否则使用内置默认值（本地开发用）

数据库信息：
  - 数据库地址: https://dbcli-mvs3fapcgsv0w0re.database.sankuai.com
  - 三张表:     city_monitor / district_monitor / store_monitor
"""

import json
import os
import sys
import time

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

WORKSPACE = os.path.dirname(os.path.abspath(__file__))

# 数据库连接（优先读环境变量，方便 GitHub Actions 注入）
SUPABASE_URL      = os.environ.get("SUPABASE_URL",      "https://dbcli-mvs3fapcgsv0w0re.database.sankuai.com")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIiwiaWF0IjoxNzQ2OTc5MjAwLCJleHAiOjE5MDQ3NDU2MDB9.Fn-xtnd9Pqt1EDagKybGKAdq_Rra1vgnZ9kOpLBZTZU")

TABLES = ["city_monitor", "district_monitor", "store_monitor"]


# ── Supabase REST API 工具函数 ─────────────────────────────────────────

def sb_headers():
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }


def sb_select(table, select="id", limit=1000):
    """查询表数据"""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={**sb_headers(), "Prefer": "count=exact"},
        params={"select": select, "limit": limit},
        timeout=15
    )
    r.raise_for_status()
    return r.json()


def sb_delete_all(table):
    """清空表（通过 id != 0 匹配所有行）"""
    r = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={**sb_headers(), "Prefer": "return=minimal"},
        params={"id": "gte.0"},
        timeout=15
    )
    r.raise_for_status()


def sb_insert(table, rows):
    """批量插入数据"""
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={**sb_headers(), "Prefer": "return=minimal"},
        json=rows,
        timeout=30
    )
    if not r.ok:
        raise Exception(f"插入失败 {r.status_code}: {r.text[:200]}")


def sb_count(table):
    """获取表行数"""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={**sb_headers(), "Prefer": "count=exact"},
        params={"select": "id", "limit": 1},
        timeout=15
    )
    r.raise_for_status()
    content_range = r.headers.get("Content-Range", "0/0")
    try:
        return int(content_range.split("/")[-1])
    except Exception:
        return len(r.json())


# ── 主流程 ────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("🗄️  刷新 NoCode 数据库（Supabase REST API）")
    print(f"   URL: {SUPABASE_URL}")
    print("=" * 50)

    # 读取数据
    dashboard_json = os.path.join(WORKSPACE, "dashboard_data.json")
    print(f"\n📂 读取数据: {dashboard_json}")
    with open(dashboard_json, "r", encoding="utf-8") as f:
        d = json.load(f)

    city_rows     = d["city_rows"]
    district_rows = d["district_rows"]
    store_rows    = d["store_rows"]
    print(f"   城市={len(city_rows)}, 区域={len(district_rows)}, 门店={len(store_rows)}")

    # Step 1: 清空所有表
    print("\n=== Step 1: 清空所有表 ===")
    for table in TABLES:
        try:
            sb_delete_all(table)
            print(f"  {table}: 清空 ✅")
        except Exception as e:
            print(f"  {table}: 清空失败 ({e})")

    time.sleep(0.5)

    # Step 2: 插入城市数据
    print("\n=== Step 2: 插入城市数据（city_monitor）===")
    try:
        sb_insert("city_monitor", city_rows)
        print(f"  city_monitor: 插入 {len(city_rows)}/{len(city_rows)} 条 ✅")
    except Exception as e:
        print(f"  city_monitor: 插入失败 ({e})")

    # Step 3: 插入区域数据
    print("\n=== Step 3: 插入区域数据（district_monitor）===")
    try:
        sb_insert("district_monitor", district_rows)
        print(f"  district_monitor: 插入 {len(district_rows)}/{len(district_rows)} 条 ✅")
    except Exception as e:
        print(f"  district_monitor: 插入失败 ({e})")

    # Step 4: 插入门店数据
    print("\n=== Step 4: 插入门店数据（store_monitor）===")
    try:
        sb_insert("store_monitor", store_rows)
        print(f"  store_monitor: 插入 {len(store_rows)}/{len(store_rows)} 条 ✅")
    except Exception as e:
        print(f"  store_monitor: 插入失败 ({e})")

    # 验证行数
    print("\n=== 验证行数 ===")
    expected = {
        "city_monitor":     len(city_rows),
        "district_monitor": len(district_rows),
        "store_monitor":    len(store_rows),
    }
    all_ok = True
    for table, exp in expected.items():
        try:
            actual = sb_count(table)
            status = "✅" if actual == exp else f"⚠️  期望 {exp}，实际 {actual}"
            if actual != exp:
                all_ok = False
        except Exception as e:
            actual = "?"
            status = f"❌ 读取失败: {e}"
            all_ok = False
        print(f"  {table}: {actual} 条 {status}")

    if all_ok:
        print("\n✅ 数据库刷新完成！")
    else:
        print("\n⚠️  部分表数据异常，请检查上方日志")

    return all_ok


if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)
