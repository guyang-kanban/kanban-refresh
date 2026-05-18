#!/usr/bin/env python3
"""
run_all.py
一键完成：抓取蜻蜓数据 → 处理 → 写入数据库

用法：
  python kanban-scripts/run_all.py

等价于依次执行：
  1. python kanban-scripts/fetch_data.py
  2. python kanban-scripts/prepare_data.py
  3. python kanban-scripts/refresh_db.py
"""

import subprocess
import sys
import os
import time

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
PYTHON    = sys.executable


def run_step(name, script):
    print(f"\n{'='*50}")
    print(f"▶  {name}")
    print(f"{'='*50}")
    r = subprocess.run([PYTHON, os.path.join(WORKSPACE, script)], env=os.environ.copy())
    if r.returncode != 0:
        print(f"\n❌ {name} 失败，终止执行")
        sys.exit(r.returncode)
    print(f"✅ {name} 完成")


if __name__ == "__main__":
    start = time.time()

    run_step("Step 1: 抓取蜻蜓数据", "fetch_data.py")
    run_step("Step 2: 处理数据",     "prepare_data.py")
    run_step("Step 3: 写入数据库",   "refresh_db.py")

    elapsed = round(time.time() - start)
    print(f"\n🎉 全部完成！耗时 {elapsed} 秒")
    print(f"   数据库: https://dbcli-mvs3fapcgsv0w0re.database.sankuai.com")
