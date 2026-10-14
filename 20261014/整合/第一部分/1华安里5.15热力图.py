import folium
from folium.plugins import HeatMap
import pandas as pd

# 读取你的POI数据
df = pd.read_csv(r"E:\Huaanli.csv", encoding='utf-8')

print("CSV列名：", df.columns.tolist())

# 根据你的实际列名修改
lon_col = '经度'
lat_col = '纬度'
class_col = None      # 如果不需要分类过滤，保持 None
class_val = '050000'

# 筛选数据
if class_col and class_col in df.columns:
    df_filtered = df[df[class_col] == class_val]
else:
    df_filtered = df

# 构建热力数据
heat_data = [
    [float(row[lat_col]), float(row[lon_col]), 1]
    for _, row in df_filtered.iterrows()
    if pd.notnull(row[lat_col]) and pd.notnull(row[lon_col])
]

# 华安里正确中心点
center_lat, center_lon = 30.61652, 114.23752

# 创建地图（默认高德道路图）
m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=16,
    tiles='https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
    attr='高德地图'
)

# 添加高德卫星图层
folium.TileLayer(
    tiles='https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
    attr='高德卫星图',
    name='卫星图'
).add_to(m)

# 添加OpenStreetMap备用
folium.TileLayer(
    tiles='OpenStreetMap',
    name='OpenStreetMap'
).add_to(m)

# 添加热力图
HeatMap(
    heat_data,
    radius=25,
    blur=15,
    max_zoom=1,
    gradient={0.4: 'blue', 0.6: 'lime', 0.8: 'orange', 1.0: 'red'},
    name='餐饮热力'
).add_to(m)

# 中心标记
folium.Marker(
    [center_lat, center_lon],
    popup="华安里社区中心",
    icon=folium.Icon(color='red', icon='star')
).add_to(m)

# 图层控制（直接使用 folium.LayerControl）
folium.LayerControl().add_to(m)

m.save("华安里餐饮热力图.html")
print("✅ 热力图已生成！")