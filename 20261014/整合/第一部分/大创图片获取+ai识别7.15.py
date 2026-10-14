import os
import time
import json
import base64
import io
import requests
import pandas as pd
import numpy as np
from PIL import Image
import dashscope
import osmnx as ox
import geopandas as gpd
from shapely.geometry import Point, LineString
import pyproj
import warnings
warnings.filterwarnings("ignore")

# ==================== 配置区 ====================
# 百度地图 API Key（全景静态图）
BAIDU_AK = "w3Tl8FnTp3qfKKF9y9crIfLhmNcZSGQY"
# DashScope API Key
DASHSCOPE_API_KEY = "sk-ws-H.EMXIDYH.RRck.MEUCIQDHp0XqUKzYR8qG0aPpbTRjPHKy9bePLZ_4foECaF_mhQIgf3zrYzRfnU5u5t74Cgyiuee4PUdHJgASPdF-BySFpDs"


# ★ 每天运行前只修改这个数字 (1~14)
DAY_NUMBER = 1

# ★ 每个区域的配置: (名称, 北, 南, 东, 西, 采样间距)
DAY_CONFIGS = {
    1:  ("武汉_Day01_江汉路", 30.595, 30.580, 114.295, 114.275, 80),    # 80米，点数多，需多天
    2:  ("武汉_Day02_武广",    30.595, 30.580, 114.275, 114.255, 150),   # 150米，点数约80-100
    3:  ("武汉_Day03_西北湖",  30.605, 30.590, 114.265, 114.245, 150),
    4:  ("武汉_Day04_古田",    30.595, 30.580, 114.225, 114.205, 150),
    5:  ("武汉_Day05_钟家村",  30.555, 30.540, 114.275, 114.255, 150),
    6:  ("武汉_Day06_王家湾",  30.565, 30.550, 114.215, 114.195, 150),
    7:  ("武汉_Day07_司门口",  30.555, 30.540, 114.315, 114.295, 150),
    8:  ("武汉_Day08_中南路",  30.545, 30.530, 114.345, 114.325, 150),
    9:  ("武汉_Day09_街道口",  30.535, 30.520, 114.365, 114.345, 150),
    10: ("武汉_Day10_徐东",    30.585, 30.570, 114.355, 114.335, 150),
    11: ("武汉_Day11_青山",    30.625, 30.610, 114.405, 114.385, 150),
    12: ("武汉_Day12_光谷广场",30.510, 30.495, 114.405, 114.385, 150),
    13: ("武汉_Day13_虎泉",    30.515, 30.500, 114.375, 114.355, 150),
    14: ("武汉_Day14_后湖",    30.655, 30.640, 114.315, 114.295, 150),
}

CITY_NAME, NORTH, SOUTH, EAST, WEST, SPACING_M = DAY_CONFIGS[DAY_NUMBER]

HEADINGS = [0]                # 单方向（正北）
DAILY_QUOTA = 100           # 每日最大下载数

IMAGE_DIR = f"{CITY_NAME}_streetviews"
OUTPUT_EXCEL = f"{CITY_NAME}_街景AI分析结果.xlsx"

WIDTH = 1024
HEIGHT = 512
FOV = 180
COORD_TYPE = "wgs84ll"
DOWNLOAD_DELAY = 0.3
ANALYSIS_DELAY = 1.5

# ==================== 提示词（同前，略） ====================
# 30维系统提示词（与你之前的完全一致）
SYSTEM_PROMPT = """你是一位城市科学研究专家，专门从事老旧街区更新潜力评估。请依据输入的街景图像，输出可供后续感知评价使用的学术化描述文本。

要求：
1. 采用学术且专业的表达方式，引用城市规划和社会学关键术语。
2. 使用正式、严谨的语气，注重逻辑与条理性。
3. 所有输出必须完全使用中文，包括JSON字段名称。
4. 描述要具体、详细，避免笼统的表述。
5. 基于图像内容进行客观分析，但需要给出带有明确评价倾向的判断，例如使用“较好”“较差”“缺乏”“丰富”“整洁”“杂乱”等词语，避免完全中性的客观罗列。
6. 不要添加与图像内容无关的个人主观臆断。

请从以下30个维度进行深入分析并以中文JSON格式输出：

1. 空间开阔度：评估街道宽度、建筑高度比例、天空视野占比，判断空间的开敞感或压抑感，给出明确评价。
2. 交通可达性：分析人行道连续性、过街设施完善度、步行网络的完整度。
3. 交通秩序度：观察车辆停放秩序、交通标识清晰度、人车混行情况。
4. 有效步行空间：评估人行道被车辆、摊位、杂物侵占的程度。
5. 无障碍设施：观察盲道、坡道、扶手等无障碍设施的完善程度和维护状况。
6. 视觉多样性：分析建筑风格、色彩、材质、形态的多样性程度。
7. 美感评价：从美学角度评价整体构图、色彩搭配、光影效果、比例协调性。
8. 外立面污损与破损：观察建筑外墙是否存在剥落、水渍、裂缝等明显老化痕迹。
9. 违规搭建覆盖：识别蓝顶、简易棚、私自加建等非正规增建现象。
10. 首层界面开口率：观察首层门窗、透明橱窗占临街立面的比例。
11. 商业多样性：分析店铺类型、商品服务种类的丰富程度。
12. 街道繁荣度：评估人流密度、商业活跃度、街道生活气息。
13. 摊贩活动：观察街头摊贩的存在形式、管理状况。
14. 商业环境：评价商业界面（橱窗、招牌、外摆）的设计质量和协调性。
15. 非正规便民服务点：识别缝补、修鞋、配钥匙等非正规摊点。
16. 绿化覆盖率：估算植被占画面面积的比例。
17. 植物健康度：观察植物的生长状态、叶片颜色。
18. 污染可见度：识别垃圾堆积、油污、粉尘等环境污染迹象。
19. 噪音干扰度：通过视觉线索推断噪音污染程度。
20. 生活垃圾堆积：观察是否存在生活垃圾袋、废弃物堆积点。
21. 墙面违规张贴：观察墙面涂鸦、小广告覆盖程度。
22. 负面情绪度：评估环境因素可能引发的负面心理感受。
23. 夜间照明设施：观察路灯、建筑灯带的设置密度和分布。
24. 街道眼开口指数：评估首层建筑门窗朝向街道的开口数量和密度。
25. 消防通道畅通度：观察道路宽度、障碍物堵塞情况。
26. 景观特色度：识别具有地域特色或文化标识的景观元素。
27. 文化符号：识别具有文化意义的符号、图案、色彩、建筑元素等。
28. 历史文脉：观察历史建筑、传统材料的保存和利用状况。
29. 社区归属感：通过邻里互动空间、社区标识等推断社区凝聚力。
30. 自发绿化与装饰：观察居民摆放盆栽、悬挂鸟笼、节庆饰品等自发性美化行为。

输出格式（必须严格遵守，只输出JSON，不要有任何其他文字）：
{
"空间开阔度": "带有明确评价倾向的详细描述...",
"交通可达性": "带有明确评价倾向的详细描述...",
...
"自发绿化与装饰": "带有明确评价倾向的详细描述..."
}
"""

# ==================== OSM路网采样 ====================
def generate_sample_points_from_osm(north, south, east, west, spacing_m):
    print("正在下载 OSM 路网...")
    try:
        G = ox.graph_from_bbox(bbox=(west, south, east, north), network_type='walk')
        print(f"路网下载完成：节点 {len(G.nodes)}，边 {len(G.edges)}")
    except Exception as e:
        print(f"❌ OSM 下载失败：{e}")
        return []

    _, edges = ox.graph_to_gdfs(G, nodes=True, edges=True)

    center_lat = (north + south) / 2
    center_lng = (west + east) / 2
    utm_zone = int((center_lng + 180) // 6) + 1
    is_northern = center_lat >= 0
    utm_crs = pyproj.CRS(f"+proj=utm +zone={utm_zone} +{'north' if is_northern else 'south'} +ellps=WGS84 +datum=WGS84 +units=m +no_defs")
    wgs84 = pyproj.CRS('EPSG:4326')
    transformer_to_utm = pyproj.Transformer.from_crs(wgs84, utm_crs, always_xy=True)
    transformer_to_wgs = pyproj.Transformer.from_crs(utm_crs, wgs84, always_xy=True)

    seen = set()
    unique_points = []
    for _, edge in edges.iterrows():
        geom = edge['geometry']
        if geom is None or geom.is_empty:
            continue
        coords_wgs = list(geom.coords)
        coords_utm = [transformer_to_utm.transform(lon, lat) for lon, lat in coords_wgs]
        utm_geom = LineString(coords_utm)
        length_m = utm_geom.length
        num_pts = max(1, int(length_m / spacing_m))
        for i in range(num_pts):
            pt_utm = utm_geom.interpolate(i * spacing_m)
            lon, lat = transformer_to_wgs.transform(pt_utm.x, pt_utm.y)
            key = (round(lat, 5), round(lon, 5))
            if key not in seen:
                seen.add(key)
                unique_points.append((lat, lon))

    sample_points = [(f"P_{i+1}", round(lat, 6), round(lon, 6)) for i, (lat, lon) in enumerate(unique_points)]
    print(f"去重后采样点：{len(sample_points)} 个")
    return sample_points

# ==================== 百度街景下载 ====================
def download_panorama(lat, lng, save_path, heading=0):
    url = "https://api.map.baidu.com/panorama/v2"
    params = {
        "ak": BAIDU_AK,
        "width": WIDTH,
        "height": HEIGHT,
        "location": f"{lng},{lat}",
        "fov": FOV,
        "heading": heading,
        "coordtype": COORD_TYPE
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(save_path, 'wb') as f:
                f.write(resp.content)
            return True
        else:
            print(f"    下载失败({heading}°)，状态码: {resp.status_code}, 长度: {len(resp.content)}")
            return False
    except Exception as e:
        print(f"    请求异常({heading}°): {e}")
        return False

# ==================== AI 分析 ====================
def analyze_image(image_path):
    try:
        img = Image.open(image_path)
        max_size = 1024
        w, h = img.size
        if w > max_size or h > max_size:
            ratio = min(max_size / w, max_size / h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85)
        base64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
        image_uri = f"data:image/jpeg;base64,{base64_str}"

        response = dashscope.MultiModalConversation.call(
            model='qwen-vl-plus',
            api_key=DASHSCOPE_API_KEY,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': [
                    {'image': image_uri},
                    {'text': '请根据30个维度分析这张街景图片。'}
                ]}
            ]
        )

        if response.status_code == 200:
            raw = response.output.choices[0].message.content
            if isinstance(raw, dict):
                return raw
            elif isinstance(raw, list) and len(raw) > 0:
                item = raw[0]
                if isinstance(item, dict):
                    return item
                elif isinstance(item, str):
                    return json.loads(item)
            elif isinstance(raw, str):
                return json.loads(raw)
            else:
                return {"错误": f"未知响应格式"}
        else:
            return {"错误": f"API状态码 {response.status_code}"}
    except Exception as e:
        return {"错误": str(e)}

# ==================== 主程序（断点续传 + 自动停止） ====================
def main():
    sample_points = generate_sample_points_from_osm(NORTH, SOUTH, EAST, WEST, SPACING_M)
    total_points = len(sample_points)
    if total_points == 0:
        print("❌ 没有生成采样点，程序退出。")
        return

    print(f"今日区域: {CITY_NAME}")
    print(f"采样点数: {total_points}，每日配额: {DAILY_QUOTA}")

    os.makedirs(IMAGE_DIR, exist_ok=True)
    results = []
    download_count = 0
    skipped_count = 0

    for idx, (name, lat, lng) in enumerate(sample_points, 1):
        if download_count >= DAILY_QUOTA:
            print(f"\n🛑 已达到每日配额 {DAILY_QUOTA} 次，今日采集结束。")
            print(f"   剩余 {total_points - idx + 1} 个点将在后续日期继续。")
            break

        img_filename = f"{name}.jpg"
        img_path = os.path.join(IMAGE_DIR, img_filename)

        # 断点续传：已存在图片则跳过
        if os.path.exists(img_path):
            print(f"[{idx}/{total_points}] {name} - 已存在，跳过")
            skipped_count += 1
            continue

        print(f"[{idx}/{total_points}] {name} ({lat}, {lng})")

        if download_panorama(lat, lng, img_path, heading=HEADINGS[0]):
            download_count += 1
            print(f"  ✅ 下载成功 (今日第 {download_count} 次)")
            time.sleep(DOWNLOAD_DELAY)
            ai_result = analyze_image(img_path)
            time.sleep(ANALYSIS_DELAY)
        else:
            ai_result = {"错误": "街景图下载失败"}

        row = {
            "编号": idx,
            "点位名称": name,
            "纬度": lat,
            "经度": lng,
            "图片文件": img_filename,
            "分析状态": "成功" if "错误" not in ai_result else "失败"
        }
        row.update(ai_result)
        results.append(row)

    print(f"\n📊 今日统计：新下载 {download_count} 张，跳过 {skipped_count} 个已存在的点")

    # 保存/合并 Excel
    if results:
        if os.path.exists(OUTPUT_EXCEL):
            old_df = pd.read_excel(OUTPUT_EXCEL)
            new_df = pd.DataFrame(results)
            combined_df = pd.concat([old_df, new_df]).drop_duplicates(subset=["编号"], keep='last')
            combined_df.to_excel(OUTPUT_EXCEL, index=False, engine='openpyxl')
            print(f"✅ 已合并旧数据，共 {len(combined_df)} 条记录")
        else:
            df = pd.DataFrame(results)
            df.to_excel(OUTPUT_EXCEL, index=False, engine='openpyxl')
            print(f"✅ 新文件已保存，共 {len(df)} 条记录")
    else:
        print("❌ 没有新数据可保存。")

if __name__ == "__main__":
    main()
