#!/usr/bin/env python3
"""
prepare_data.py
读取 fulfill_data.json（牵牛花数据），按城市/区域/门店三维度汇总，
输出 dashboard_data.json，供 refresh_db.py 写入数据库。

牵牛花字段说明：
  - upTwoLevelDepartmentName : 城市（如"上海"）
  - upOneLevelDepartmentName : 区域（如"上海二区"）
  - storeName                : 门店名（含"歪马送酒（）"前缀，需去除）
  - storeId                  : 门店 ID
  - validOrder               : 有效订单数
  - fulfillRiderNum          : 在岗骑手数
  - idleRiderNum             : 空闲骑手数
  - avgRiderLoad             : 人均负载（字符串，如"1.50"）
  - workedEmployeeNum        : 在岗员工数
  - ninetiethFulfillDuration : P90 时长（字符串）
  - avgFulfillDuration       : 平均时长（字符串）
  - judgeTimeoutOrder        : 超时订单数（判责超时）
  - etaOvertimeOrdNumV2      : ETA 超时订单数
  - seriousTimeoutOrder      : 严重超时订单数
  - etaBadOvertimeOrdNumV2   : 严重超时订单数 V2
  - deliveredRateIn15Min     : 15min 送达率（字符串，如"53.80"）
  - deliveredRateIn25Min     : 25min 送达率
  - etaOntimeRatioV2         : ETA 准时率
  - etaBadOvertimeRatioV2    : 严重超时率

用法：
  python3 kanban-scripts/prepare_data.py

输入：  kanban-scripts/fulfill_data.json
输出：  kanban-scripts/dashboard_data.json
"""

import json
import os
from collections import defaultdict

WORKSPACE = os.path.dirname(os.path.abspath(__file__))

# ── 加载数据 ──────────────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "fulfill_data.json"), "r", encoding="utf-8") as f:
    raw = json.load(f)

stores    = raw["stores"]
districts = raw.get("districts", [])   # 牵牛花直接返回的区域汇总（可能为空）
print(f"📂 加载数据: 门店={len(stores)}, 区域={len(districts)}")


# ── 辅助函数 ──────────────────────────────────────────────────────────

def safe_float(v, default=0.0):
    try:
        return float(v) if v is not None and v != "--" else default
    except Exception:
        return default


def clean_name(name):
    return (name or "").replace("歪马送酒（", "").replace("）", "").replace("歪马送酒", "").strip()


# ── 1. 门店维度（store_monitor）──────────────────────────────────────
store_rows = []
for s in stores:
    store_name = clean_name(s.get("storeName", ""))
    emp        = s.get("workedEmployeeNum", 0) or 0
    rider      = s.get("fulfillRiderNum", 0) or 0
    schedule_rate = round(rider / emp * 100, 2) if emp > 0 else 0.0

    store_rows.append({
        "store_id":                     str(s.get("storeId", "")),
        "store_name":                   store_name,
        "city":                         s.get("upTwoLevelDepartmentName", ""),
        "valid_order":                  s.get("validOrder", 0) or 0,
        "rider_worked":                 rider,
        "schedule_actual":              emp,
        "schedule_rate":                schedule_rate,
        "timeout_order_cnt":            s.get("etaOvertimeOrdNumV2", 0) or 0,
        "serious_timeout_order_cnt":    s.get("seriousTimeoutOrder", 0) or 0,
        "rate_15min_val":               safe_float(s.get("deliveredRateIn15Min", 0)),
        "rate_25min_val":               safe_float(s.get("deliveredRateIn25Min", 0)),
        "eta_ontime_val":               safe_float(s.get("etaOntimeRatioV2", 0)),
        "serious_timeout_val":          safe_float(s.get("etaBadOvertimeRatioV2", 0)),
        "p90_duration_val":             safe_float(s.get("ninetiethFulfillDuration", 0)),
        "avg_rider_load":               safe_float(s.get("avgRiderLoad", 0)),
        "alert_level":                  "",
        "alert_reasons":                "",
    })
store_rows.sort(key=lambda x: x["valid_order"], reverse=True)


# ── 2. 区域维度（district_monitor）───────────────────────────────────
# 优先用牵牛花直接返回的区域汇总，否则从门店数据聚合
if districts:
    district_rows = []
    for d in districts:
        emp   = d.get("workedEmployeeNum", 0) or 0
        rider = d.get("fulfillRiderNum", 0) or 0
        schedule_rate = round(rider / emp * 100, 2) if emp > 0 else 0.0
        district_rows.append({
            "district_id":                  d.get("departmentName", ""),
            "district_name":                "上海二区",
            "city":                         "上海二区",
            "valid_order":                  d.get("validOrder", 0) or 0,
            "rider_worked":                 rider,
            "store_cnt":                    d.get("storeCnt", 0) or 0,
            "schedule_actual":              emp,
            "schedule_rate":                schedule_rate,
            "timeout_order_cnt":            d.get("judgeTimeoutOrder", 0) or 0,
            "serious_timeout_order_cnt":    d.get("seriousTimeoutOrder", 0) or 0,
            "rate_15min_val":               safe_float(d.get("deliveredRateIn15Min", 0)),
            "rate_25min_val":               safe_float(d.get("deliveredRateIn25Min", 0)),
            "eta_ontime_val":               safe_float(d.get("etaOntimeRatioV2", 0)),
            "serious_timeout_val":          safe_float(d.get("etaBadOvertimeRatioV2", 0)),
            "p90_duration_val":             safe_float(d.get("ninetiethFulfillDuration", 0)),
            "avg_rider_load":               safe_float(d.get("avgRiderLoad", 0)),
            "alert_level":                  "",
            "alert_reasons":                "",
        })
else:
    # 从门店数据聚合区域维度
    dist_map = defaultdict(lambda: {
        "city": "", "valid_order": 0, "rider_worked": 0, "store_cnt": 0,
        "schedule_actual": 0, "timeout_order_cnt": 0, "serious_timeout_order_cnt": 0,
        "rate_15min_sum": 0.0, "rate_25min_sum": 0.0, "eta_ontime_sum": 0.0,
        "serious_timeout_val_sum": 0.0, "p90_sum": 0.0, "avg_load_sum": 0.0,
    })
    for s in stores:
        dist  = s.get("upOneLevelDepartmentName", "未知")
        city  = s.get("upTwoLevelDepartmentName", "未知")
        d = dist_map[dist]
        d["city"]                       = city
        d["valid_order"]                += s.get("validOrder", 0) or 0
        d["rider_worked"]               += s.get("fulfillRiderNum", 0) or 0
        d["store_cnt"]                  += 1
        d["schedule_actual"]            += s.get("workedEmployeeNum", 0) or 0
        d["timeout_order_cnt"]          += s.get("etaOvertimeOrdNumV2", 0) or 0
        d["serious_timeout_order_cnt"]  += s.get("seriousTimeoutOrder", 0) or 0
        d["rate_15min_sum"]             += safe_float(s.get("deliveredRateIn15Min", 0))
        d["rate_25min_sum"]             += safe_float(s.get("deliveredRateIn25Min", 0))
        d["eta_ontime_sum"]             += safe_float(s.get("etaOntimeRatioV2", 0))
        d["serious_timeout_val_sum"]    += safe_float(s.get("etaBadOvertimeRatioV2", 0))
        d["p90_sum"]                    += safe_float(s.get("ninetiethFulfillDuration", 0))
        d["avg_load_sum"]               += safe_float(s.get("avgRiderLoad", 0))

    district_rows = []
    for name, d in dist_map.items():
        n = d["store_cnt"] or 1
        emp   = d["schedule_actual"]
        rider = d["rider_worked"]
        schedule_rate = round(rider / emp * 100, 2) if emp > 0 else 0.0
        district_rows.append({
            "district_id":                  name,
            "district_name":                "上海二区",
            "city":                         d["city"],
            "valid_order":                  d["valid_order"],
            "rider_worked":                 rider,
            "store_cnt":                    d["store_cnt"],
            "schedule_actual":              emp,
            "schedule_rate":                schedule_rate,
            "timeout_order_cnt":            d["timeout_order_cnt"],
            "serious_timeout_order_cnt":    d["serious_timeout_order_cnt"],
            "rate_15min_val":               round(d["rate_15min_sum"] / n, 2),
            "rate_25min_val":               round(d["rate_25min_sum"] / n, 2),
            "eta_ontime_val":               round(d["eta_ontime_sum"] / n, 2),
            "serious_timeout_val":          round(d["serious_timeout_val_sum"] / n, 2),
            "p90_duration_val":             round(d["p90_sum"] / n, 2),
            "avg_rider_load":               round(d["avg_load_sum"] / n, 2),
            "alert_level":                  "",
            "alert_reasons":                "",
        })

district_rows.sort(key=lambda x: x["valid_order"], reverse=True)


# ── 3. 城市维度（city_monitor）────────────────────────────────────────
# 从门店数据聚合城市维度
city_map = defaultdict(lambda: {
    "rider_worked": 0, "store_cnt": 0, "schedule_actual": 0,
    "timeout_order_cnt": 0, "serious_timeout_order_cnt": 0,
    "rate_15min_sum": 0.0, "eta_ontime_sum": 0.0,
    "serious_timeout_val_sum": 0.0, "p90_sum": 0.0, "avg_load_sum": 0.0,
})
for s in stores:
    city = s.get("upTwoLevelDepartmentName", "未知")
    c = city_map[city]
    c["rider_worked"]               += s.get("fulfillRiderNum", 0) or 0
    c["store_cnt"]                  += 1
    c["schedule_actual"]            += s.get("workedEmployeeNum", 0) or 0
    c["timeout_order_cnt"]          += s.get("etaOvertimeOrdNumV2", 0) or 0
    c["serious_timeout_order_cnt"]  += s.get("seriousTimeoutOrder", 0) or 0
    c["rate_15min_sum"]             += safe_float(s.get("deliveredRateIn15Min", 0))
    c["eta_ontime_sum"]             += safe_float(s.get("etaOntimeRatioV2", 0))
    c["serious_timeout_val_sum"]    += safe_float(s.get("etaBadOvertimeRatioV2", 0))
    c["p90_sum"]                    += safe_float(s.get("ninetiethFulfillDuration", 0))
    c["avg_load_sum"]               += safe_float(s.get("avgRiderLoad", 0))

city_rows = []
for city, c in city_map.items():
    n = c["store_cnt"] or 1
    city_rows.append({
        "city":                         city,
        "rider_worked":                 c["rider_worked"],
        "store_cnt":                    c["store_cnt"],
        "schedule_actual":              c["schedule_actual"],
        "timeout_order_cnt":            c["timeout_order_cnt"],
        "serious_timeout_order_cnt":    c["serious_timeout_order_cnt"],
        "rate_15min_val":               round(c["rate_15min_sum"] / n, 2),
        "eta_ontime_val":               round(c["eta_ontime_sum"] / n, 2),
        "eta_ontime":                   str(round(c["eta_ontime_sum"] / n, 2)),
        "serious_timeout_val":          round(c["serious_timeout_val_sum"] / n, 2),
        "p90_duration_val":             round(c["p90_sum"] / n, 2),
        "avg_rider_load":               round(c["avg_load_sum"] / n, 2),
        "weather_icon":                 "",
    })
city_rows.sort(key=lambda x: x["store_cnt"], reverse=True)


# ── 输出 ──────────────────────────────────────────────────────────────
result = {
    "city_rows":     city_rows,
    "district_rows": district_rows,
    "store_rows":    store_rows,
}

out_path = os.path.join(WORKSPACE, "dashboard_data.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\n✅ 已保存到 {out_path}")
print(f"   城市维度:  {len(city_rows)} 条")
print(f"   区域维度:  {len(district_rows)} 条")
print(f"   门店维度:  {len(store_rows)} 条")

print("\n门店数据预览（前3条）:")
for r in store_rows[:3]:
    print(f"  {r['store_name']}: 订单={r['valid_order']}, "
          f"超时={r['timeout_order_cnt']}, 严重超时={r['serious_timeout_order_cnt']}, "
          f"15min率={r['rate_15min_val']}%, 准时率={r['eta_ontime_val']}%")
