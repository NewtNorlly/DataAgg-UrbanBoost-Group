import pandas as pd
import numpy as np
import requests
import time

# ================== 配置 ==================
GAODE_AK = "872dacb8dee394a06b8a9aa0e1c43052"          # 你的高德 Web 服务 Key
CITY_NAME = "武汉14"
INPUT_FILE = f"{CITY_NAME}_六维感知得分.xlsx"
OUTPUT_FILE = f"{CITY_NAME}_更新潜力指数.xlsx"

# 六维感知权重
WEIGHTS = {
    "街巷空间与交通通达": 0.16,
    "建筑风貌与界面品质": 0.13,
    "便民生活与服务韧性": 0.15,
    "环境秩序与生态韧性": 0.14,
    "公共安全与心理感知": 0.13,
    "场所氛围与情感价值": 0.14
}

# 外部供给权重
POI_WEIGHTS = {
    "公交站": 0.25,
    "菜市场": 0.20,
    "社区卫生": 0.20,
    "基础教育": 0.15,
    "公园绿地": 0.10,
    "生活服务": 0.10
}

RADIUS = 1000

# 高德 POI 类型代码
POI_TYPES = {
    "公交站": "150700|150800",
    "菜市场": "060100",
    "社区卫生": "090100|090200",
    "基础教育": "141200",
    "公园绿地": "110100|110200",
    "生活服务": "050000|070000"
}

SEARCH_URL = "https://restapi.amap.com/v3/place/around"

# ================== POI 搜索函数（带成功标志） ==================
def search_poi_count_with_status(lat, lng, poi_type):
    """返回 (数量, 是否成功获取)"""
    params = {
        "key": GAODE_AK,
        "location": f"{lng},{lat}",
        "radius": RADIUS,
        "types": poi_type,
        "offset": 1,
        "page": 1,
        "extensions": "base"
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=10)
        data = resp.json()
        if data["status"] == "1" and data["info"] == "OK":
            return int(data["count"]), True
        else:
            print(f"  ⚠️ POI 搜索失败 [{poi_type}]: {data.get('info', '未知错误')}")
            return 0, False
    except Exception as e:
        print(f"  ❌ 请求异常 [{poi_type}]: {e}")
        return 0, False

def compute_poi_raw_score(lat, lng):
    """计算原始便利度得分，同时返回所有类型是否全部成功"""
    score = 0.0
    all_success = True
    for poi_name, poi_code in POI_TYPES.items():
        count, success = search_poi_count_with_status(lat, lng, poi_code)
        if not success:
            all_success = False   # 只要有一类失败，整个点就标记为不完整
        count = min(count, 10)   # 截断最大值
        score += count * POI_WEIGHTS[poi_name]
        time.sleep(0.1)          # 控制频率
    return score, all_success

# ================== 主程序 ==================
def main():
    # 1. 读取六维感知得分
    df = pd.read_excel(INPUT_FILE)
    required_cols = ["纬度", "经度"] + list(WEIGHTS.keys())
    assert all(col in df.columns for col in required_cols), "输入表格缺少必要列"

    # 2. 计算内部品质综合指数
    df["内部品质指数"] = 0.0
    for dim, w in WEIGHTS.items():
        df["内部品质指数"] += df[dim] * w

    # 3. 计算每个点位的 POI 原始便利度得分（同时记录数据获取状态）
    print(f"开始计算 POI 便利度，共 {len(df)} 个点位...")
    poi_scores = []
    poi_status = []   # True: 全部成功, False: 有缺失
    for i, row in df.iterrows():
        lat, lng = row["纬度"], row["经度"]
        print(f"  处理 {i+1}/{len(df)}: ({lat}, {lng})")
        raw, status = compute_poi_raw_score(lat, lng)
        poi_scores.append(raw)
        poi_status.append(status)

    df["POI原始便利度得分"] = poi_scores
    df["POI数据状态"] = poi_status   # 新增列，标记数据质量

    # 4. Min-Max 归一化得外部供给指数
    min_poi = df["POI原始便利度得分"].min()
    max_poi = df["POI原始便利度得分"].max()
    if max_poi > min_poi:
        df["外部供给指数"] = (df["POI原始便利度得分"] - min_poi) / (max_poi - min_poi)
    else:
        df["外部供给指数"] = 0.5

    # 5. 计算更新潜力指数
    w_inner, w_outer = 0.5, 0.5
    df["更新潜力指数"] = (w_inner * (1 - df["内部品质指数"]) +
                          w_outer * (1 - df["外部供给指数"]))

    # 6. 保存结果
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"处理完毕，结果已保存至 {OUTPUT_FILE}")
    print(f"更新潜力指数统计：均值={df['更新潜力指数'].mean():.3f}, "
          f"最大值={df['更新潜力指数'].max():.3f}, 最小值={df['更新潜力指数'].min():.3f}")
    print(f"POI 数据完整点位: {df['POI数据状态'].sum()}/{len(df)}")

if __name__ == "__main__":
    main()