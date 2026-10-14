import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon
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

# ================== 生成渔网（WGS84） ==================
gdf_points = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["经度"], df["纬度"]), crs="EPSG:4326")

lat_step = GRID_SIZE_M / 111320.0
lon_step = GRID_SIZE_M / (111320.0 * np.cos(np.radians((REGION_NORTH + REGION_SOUTH) / 2)))
lons = np.arange(REGION_WEST, REGION_EAST + lon_step, lon_step)
lats = np.arange(REGION_SOUTH, REGION_NORTH + lat_step, lat_step)
grid_cells = []
for lat in lats:
    for lon in lons:
        grid_cells.append(Polygon([
            (lon, lat), (lon + lon_step, lat),
            (lon + lon_step, lat + lat_step), (lon, lat + lat_step)
        ]))
grid_gdf = gpd.GeoDataFrame(geometry=grid_cells, crs="EPSG:4326")

# 空间连接并聚合
joined = gpd.sjoin(grid_gdf, gdf_points, how="inner", predicate="contains")
if len(joined) == 0:
    print("❌ 没有网格包含数据点，请检查坐标范围。")
    exit()

grid_agg = joined.groupby(joined.index)[PLOT_COLUMN].mean().reset_index()
grid_result = grid_gdf.iloc[grid_agg["index"]].copy()
grid_result[PLOT_COLUMN] = grid_agg[PLOT_COLUMN].values
print(f"生成 {len(grid_result)} 个有效网格")

# 转为 Web Mercator (米制坐标)
grid_result_3857 = grid_result.to_crs(epsg=3857)

# ================== 绘图 ==================
fig, ax = plt.subplots(figsize=(14, 12))

# 1. 绘制网格（半透明）
grid_result_3857.plot(
    column=PLOT_COLUMN, ax=ax, cmap="RdYlGn_r", legend=True,
    legend_kwds={'label': PLOT_COLUMN, 'shrink': 0.5, 'aspect': 20},
    edgecolor='none', alpha=0.75
)

# 2. 添加卫星底图
try:
    ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, crs='EPSG:3857', zoom='auto', attribution=False)
    print("✅ 卫星底图加载成功")
except Exception as e:
    print(f"⚠️ 卫星底图加载失败 ({e})，使用白色背景")
    ax.set_facecolor('white')

# 3. 设置坐标轴范围
bounds = grid_result_3857.total_bounds
margin = 200
ax.set_xlim(bounds[0] - margin, bounds[2] + margin)
ax.set_ylim(bounds[1] - margin, bounds[3] + margin)

# ---------- 添加指北针和比例尺 ----------
x_min, x_max = ax.get_xlim()
y_min, y_max = ax.get_ylim()
dx = x_max - x_min
dy = y_max - y_min

# 指北针（右上角）
n_x = x_max - dx * 0.1
n_y = y_max - dy * 0.1
arrow = FancyArrowPatch(
    posA=(n_x, n_y - dy*0.03),
    posB=(n_x, n_y + dy*0.03),
    arrowstyle='->,head_length=3,head_width=2',
    lw=2, color='black'
)
ax.add_patch(arrow)
ax.text(n_x, n_y + dy*0.04, 'N', fontsize=14, ha='center', va='bottom', fontweight='bold')

# 比例尺（左下角，表示200米）
scale_bar_length = 200  # 单位：米
x_bar_start = x_min + dx * 0.1
y_bar_start = y_min + dy * 0.1
ax.plot([x_bar_start, x_bar_start + scale_bar_length],
        [y_bar_start, y_bar_start], 'k-', lw=3)
ax.plot([x_bar_start, x_bar_start],
        [y_bar_start - dy*0.01, y_bar_start + dy*0.01], 'k-', lw=2)
ax.plot([x_bar_start + scale_bar_length, x_bar_start + scale_bar_length],
        [y_bar_start - dy*0.01, y_bar_start + dy*0.01], 'k-', lw=2)
ax.text(x_bar_start + scale_bar_length/2, y_bar_start - dy*0.03,
        f'{scale_bar_length} m', ha='center', fontsize=10)

# 4. 关闭原始坐标轴（指北针和比例尺不受影响）
ax.set_axis_off()
ax.set_title(f"襄阳{PLOT_COLUMN}渔网图 (卫星底图)", fontsize=16, pad=20)

plt.tight_layout()
plt.savefig(OUTPUT_MAP, dpi=250, bbox_inches='tight', facecolor='white')
plt.show()
print(f"✅ 渔网图已保存至 {OUTPUT_MAP}")