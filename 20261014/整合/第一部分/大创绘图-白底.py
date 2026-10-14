import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.ticker as mticker
from matplotlib.patches import FancyArrowPatch
import osmnx as ox
import warnings
warnings.filterwarnings("ignore")

# ================== 配置 ==================
INPUT_FILE = "武汉9_更新潜力指数.xlsx"
OUTPUT_MAP = "武汉09_更新潜力网格图_卫星底图.png"
GRID_SIZE_M = 200
PLOT_COLUMN = "更新潜力指数"

REGION_NORTH =30.535
REGION_SOUTH = 30.520
REGION_EAST = 114.365
REGION_WEST = 114.345

EXPAND = 0.002  # 底图向外扩展约200米

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

# ================== 生成渔网 ==================
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

# ================== 下载道路底图（扩展范围） ==================
print("正在下载 OSM 道路底图...")
try:
    G = ox.graph_from_bbox(bbox=(REGION_WEST - EXPAND, REGION_SOUTH - EXPAND,
                                 REGION_EAST + EXPAND, REGION_NORTH + EXPAND),
                           network_type='drive', simplify=True)
    _, edges = ox.graph_to_gdfs(G, nodes=True, edges=True)
    edges_4326 = edges.to_crs(epsg=4326)
    print(f"✅ 成功获取 {len(edges_4326)} 条道路")
    has_basemap = True
except Exception as e:
    print(f"⚠️ 道路下载失败 ({e})，将使用无底图版本")
    edges_4326 = gpd.GeoDataFrame()
    has_basemap = False

# ================== 绘图 ==================
fig, ax = plt.subplots(figsize=(14, 12), facecolor='white')

# 0. 道路底图
if has_basemap:
    edges_4326.plot(ax=ax, edgecolor='#4d4d4d', linewidth=0.4, alpha=0.5, zorder=0)

# 1. 网格（无边框，半透明填充）
grid_result.plot(
    column=PLOT_COLUMN, ax=ax, cmap="RdYlGn_r", legend=True,
    legend_kwds={'label': PLOT_COLUMN, 'shrink': 0.5, 'aspect': 20},
    edgecolor='none', alpha=0.85, zorder=2
)

# 坐标轴设为扩展范围（没有黑框）
ax.set_xlim(REGION_WEST - EXPAND, REGION_EAST + EXPAND)
ax.set_ylim(REGION_SOUTH - EXPAND, REGION_NORTH + EXPAND)

xmin_new, xmax_new = ax.get_xlim()
ymin_new, ymax_new = ax.get_ylim()
dx, dy = xmax_new - xmin_new, ymax_new - ymin_new

# 指北针
n_x = xmax_new - dx * 0.08
n_y = ymax_new - dy * 0.08
arrow = FancyArrowPatch(posA=(n_x, n_y - dy*0.02), posB=(n_x, n_y + dy*0.03),
                        arrowstyle='->,head_length=3,head_width=2', lw=1.5, color='black')
ax.add_patch(arrow)
ax.text(n_x, n_y + dy*0.05, 'N', fontsize=16, ha='center', va='bottom', fontweight='bold')

# 比例尺
scale_length_m = 200
scale_length_deg = scale_length_m / 111000.0
x_bar_start = xmin_new + dx * 0.05
y_bar_start = ymin_new + dy * 0.06
ax.plot([x_bar_start, x_bar_start + scale_length_deg], [y_bar_start, y_bar_start], 'k-', lw=3)
ax.plot([x_bar_start, x_bar_start], [y_bar_start - dy*0.005, y_bar_start + dy*0.005], 'k-', lw=2)
ax.plot([x_bar_start + scale_length_deg, x_bar_start + scale_length_deg],
        [y_bar_start - dy*0.005, y_bar_start + dy*0.005], 'k-', lw=2)
ax.text(x_bar_start + scale_length_deg/2, y_bar_start - dy*0.02, f'{scale_length_m} m', ha='center', fontsize=10)

ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.7, color='gray')
ax.xaxis.set_major_formatter(mticker.FormatStrFormatter('%.3f°E'))
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.3f°N'))
ax.set_xlabel("经度 (Longitude)", fontsize=12)
ax.set_ylabel("纬度 (Latitude)", fontsize=12)
ax.set_title(f"襄阳{PLOT_COLUMN}渔网图", fontsize=16, pad=20)

plt.tight_layout()
plt.savefig(OUTPUT_MAP, dpi=250, bbox_inches='tight', facecolor='white')
plt.show()
print(f"✅ 渔网图已保存至 {OUTPUT_MAP}")