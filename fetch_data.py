#!/usr/bin/env python3
"""
fetch_data.py
从牵牛花系统抓取上海二区履约数据，保存为 fulfill_data.json。

数据来源：
  - 门店统计：/goldengateway/fulfill-data/store-statistics
  - 区域汇总：/goldengateway/fulfill-data/department-statistics

用法：
  python3 kanban-scripts/fetch_data.py

认证方式：
  优先读取环境变量 QNH_COOKIE（格式：key1=val1; key2=val2）
  或读取 kanban-scripts/qnh_cookies.json（本地开发用）
  或自动从 CatDesk 浏览器提取 Cookie（需要 CatDesk 已登录牵牛花）

输出：
  kanban-scripts/fulfill_data.json
"""

import json
import os
import sys
import subprocess

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

WORKSPACE   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(WORKSPACE, "fulfill_data.json")
COOKIE_PATH = os.path.join(WORKSPACE, "qnh_cookies.json")
CATDESK     = os.path.expanduser("~/.catpaw/bin/catdesk")

BASE_URL = "https://qnh.meituan.com"

# 上海二区 10 个门店 ID
STORE_IDS = [
    "1127169", "1095581", "1095929", "1097378", "1121796",
    "1122796", "1131199", "1100476", "1117133", "1117578"
]


# ── Cookie 获取 ────────────────────────────────────────────────────────

def get_cookies():
    """按优先级获取 Cookie：环境变量 > 本地文件 > CatDesk 浏览器"""

    # 1. 环境变量（GitHub Actions / 服务器部署用）
    env_cookie = os.environ.get("QNH_COOKIE", "").strip()
    if env_cookie:
        print("🔑 使用环境变量 QNH_COOKIE")
        cookies = {}
        for part in env_cookie.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookies[k.strip()] = v.strip()
        return cookies

    # 2. 本地 Cookie 文件
    if os.path.exists(COOKIE_PATH):
        print(f"🔑 使用本地 Cookie 文件: {COOKIE_PATH}")
        with open(COOKIE_PATH, "r") as f:
            return json.load(f)

    # 3. 从 CatDesk 浏览器自动提取
    print("🔑 从 CatDesk 浏览器提取 Cookie...")
    if not os.path.exists(CATDESK):
        print("❌ 未找到 CatDesk，请设置 QNH_COOKIE 环境变量或创建 qnh_cookies.json")
        sys.exit(1)

    # 先导航到牵牛花确保已登录
    subprocess.run(
        [CATDESK, "browser-action",
         json.dumps({"action": "navigate", "url": BASE_URL, "waitUntil": "networkidle"})],
        capture_output=True, text=True, timeout=30
    )

    r = subprocess.run(
        [CATDESK, "browser-action",
         json.dumps({"action": "cookies_get", "url": BASE_URL})],
        capture_output=True, text=True, timeout=15
    )
    data = json.loads(r.stdout.strip())
    all_cookies = data["data"]["cookies"]

    key_names = ["_et", "_qnh_account_id", "_qnh_tenant_id", "_app_id", "_biz_app_id", "misId"]
    cookies = {c["name"]: c["value"] for c in all_cookies if c["name"] in key_names}

    # 保存到本地文件，下次直接用
    with open(COOKIE_PATH, "w") as f:
        json.dump(cookies, f, indent=2)
    print(f"   已保存到 {COOKIE_PATH}")
    return cookies


# ── HTTP 请求 ──────────────────────────────────────────────────────────

def make_session(cookies):
    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({
        "Content-Type": "application/json",
        "Referer": f"{BASE_URL}/",
        "Origin": BASE_URL,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })
    return session


def check_auth(session):
    """验证 Cookie 是否有效"""
    r = session.post(
        f"{BASE_URL}/goldengateway/fulfill-data/store-statistics",
        json={"pageNo": 1, "pageSize": 1, "storeIds": [STORE_IDS[0]]},
        timeout=15
    )
    d = r.json()
    if d.get("code") != 0:
        print(f"❌ Cookie 已失效或无权限: {d.get('msg', '')}")
        print("   请重新提取 Cookie：删除 qnh_cookies.json 后重新运行，或更新 QNH_COOKIE 环境变量")
        sys.exit(1)
    print("   ✅ Cookie 有效")


# ── 抓取门店统计数据 ──────────────────────────────────────────────────

def fetch_stores(session):
    print(f"\n🏪 抓取门店统计数据（{len(STORE_IDS)} 个门店）...")
    all_stores = []
    page = 1
    total = 999

    while len(all_stores) < total:
        r = session.post(
            f"{BASE_URL}/goldengateway/fulfill-data/store-statistics",
            json={"pageNo": page, "pageSize": 40, "storeIds": STORE_IDS},
            timeout=15
        )
        d = r.json()
        if d.get("code") != 0:
            print(f"❌ 抓取门店数据失败: {d.get('msg', '')}")
            sys.exit(1)

        total = d.get("data", {}).get("total", 0)
        batch = d.get("data", {}).get("list", [])
        all_stores.extend(batch)

        if len(batch) < 40 or len(all_stores) >= total:
            break
        page += 1

    print(f"✅ 门店数据: {len(all_stores)} 条")
    return all_stores


# ── 抓取区域汇总数据 ──────────────────────────────────────────────────

def fetch_districts(session):
    print(f"\n🗺️  抓取区域汇总数据...")
    r = session.post(
        f"{BASE_URL}/goldengateway/fulfill-data/department-statistics",
        json={
            "pageNo": 1, "pageSize": 40,
            "storeIds": STORE_IDS,
            "departmentLevel": "near_poi_second_department_id"
        },
        timeout=15
    )
    d = r.json()
    if d.get("code") != 0:
        print(f"⚠️  抓取区域数据失败: {d.get('msg', '')}，将从门店数据聚合")
        return []

    districts = d.get("data", {}).get("list", [])
    print(f"✅ 区域数据: {len(districts)} 条")
    return districts


# ── 主流程 ────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("📡 牵牛花履约数据抓取（上海二区）")
    print("=" * 50)

    cookies = get_cookies()
    session = make_session(cookies)

    print("\n🔐 验证登录状态...")
    check_auth(session)

    stores    = fetch_stores(session)
    districts = fetch_districts(session)

    result = {"stores": stores, "districts": districts}
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存到 {OUTPUT_PATH}")
    print(f"   门店: {len(stores)} 条")
    print(f"   区域: {len(districts)} 条")


if __name__ == "__main__":
    main()
