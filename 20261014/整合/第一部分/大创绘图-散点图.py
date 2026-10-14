import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyArrowPatch
import contextily as ctx
import warnings
warnings.filterwarnings("ignore")

# ================== 配置 ==================
INPUT_FILE = "武汉_全区域_更新潜力总表.xlsx"
OUTPUT_MAP = "武汉_全区域_卫星底图.png"
GRID_SIZE_M = 200
PLOT_COLUMN = "更新潜力指数"

REGION_NORTH =30.70
REGION_SOUTH = 30.45
REGION_EAST = 114.45
REGION_WEST = 114.15

EXPAND = 0.002

# 中文字体
available_fonts = [f.name for f in fm.fontManager.ttflist]
if 'Microsoft YaHei' in available_fonts:
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
elif 'SimHei' in available_fonts:
    plt.rcParams['font.sans-serif'] = ['SimHei']
else:
    plt.rcParams['font.sans-serif'] = ['sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# ================== 读取数据 ==================
df = pd.read_excel(INPUT_FILE)
print(f"原始记录数: {len(df)}")
df = df.dropna(subset=["纬度", "经度", PLOT_COLUMN])
print(f"有效数据点: {len(df)}")
df = df.drop_duplicates(subset=["纬度", "经度"], keep='first')
print(f"去重后: {len(df)}")

# 转换为 GeoDataFrame (WGS84) 然后投影到 Web Mercator
gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["经度"], df["纬度"]), crs="EPSG:4326")
gdf_3857 = gdf.to_crs(epsg=3857)

# ================== 绘图 ==================
fig, ax = plt.subplots(figsize=(14, 12))

# 1. 绘制散点图（颜色映射潜力指数）
sc = ax.scatter(
    gdf_3857.geometry.x, gdf_3857.geometry.y,
    c=gdf_3857[PLOT_COLUMN], cmap="RdYlGn_r",      # 红绿反向，红色表示高潜力
    s=100,                     # 点的大小
    alpha=0.8,                # 透明度
    edgecolors='black', linewidth=0.3,
    zorder=2
)
plt.colorbar(sc, ax=ax, label=PLOT_COLUMN, shrink=0.5, aspect=20)

# 2. 添加卫星底图
try:
    ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, crs='EPSG:3857', zoom='auto', attribution=False)
    print("✅ 卫星底图加载成功")
except Exception as e:
    print(f"⚠️ 卫星底图加载失败 ({e})，使用白色背景")
    ax.set_facecolor('white')

# 3. 设置坐标轴范围（略大于数据范围）
xmin, xmax = gdf_3857.geometry.x.min(), gdf_3857.geometry.x.max()
ymin, ymax = gdf_3857.geometry.y.min(), gdf_3857.geometry.y.max()
margin = 200
ax.set_xlim(xmin - margin, xmax + margin)
ax.set_ylim(ymin - margin, ymax + margin)

# ---------- 添加指北针和比例尺 ----------
x_range = ax.get_xlim()
y_range = ax.get_ylim()
dx = x_range[1] - x_range[0]
dy = y_range[1] - y_range[0]

# 指北针（右上角）
n_x = x_range[1] - dx * 0.1
n_y = y_range[1] - dy * 0.1
arrow = FancyArrowPatch(
    posA=(n_x, n_y - dy*0.03),
    posB=(n_x, n_y + dy*0.03),
    arrowstyle='->,head_length=3,head_width=2',
    lw=2, color='black', zorder=5
)
ax.add_patch(arrow)
ax.text(n_x, n_y + dy*0.04, 'N', fontsize=14, ha='center', va='bottom', fontweight='bold', zorder=5)

# 比例尺（左下角，表示200米）
scale_bar_length = 200  # 米
x_bar_start = x_range[0] + dx * 0.1
y_bar_start = y_range[0] + dy * 0.1
ax.plot([x_bar_start, x_bar_start + scale_bar_length],
        [y_bar_start, y_bar_start], 'k-', lw=3, zorder=5)
ax.plot([x_bar_start, x_bar_start],
        [y_bar_start - dy*0.01, y_bar_start + dy*0.01], 'k-', lw=2, zorder=5)
ax.plot([x_bar_start + scale_bar_length, x_bar_start + scale_bar_length],
        [y_bar_start - dy*0.01, y_bar_start + dy*0.01], 'k-', lw=2, zorder=5)
ax.text(x_bar_start + scale_bar_length/2, y_bar_start - dy*0.03,
        f'{scale_bar_length} m', ha='center', fontsize=10, zorder=5)

# 4. 关闭坐标轴数字（不显示经纬度）
ax.set_axis_off()
ax.set_title(f"武汉{PLOT_COLUMN}散点图 (卫星底图)", fontsize=16, pad=20)

plt.tight_layout()
plt.savefig(OUTPUT_MAP, dpi=250, bbox_inches='tight', facecolor='white')
plt.show()
print(f"✅ 散点图已保存至 {OUTPUT_MAP}")