import pandas as pd
import os
import re
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.colors as mcolors
import contextily as ctx
import sys
import warnings
warnings.filterwarnings("ignore")

# ================== 配置 ==================
INPUT_EXCEL = "武汉_全区域_更新潜力总表.xlsx"
OUTPUT_DIR = "片区单独出图"
GRID_SIZE_M = 200
PLOT_COLUMN = "更新潜力指数"

# 中文字体
available_fonts = [f.name for f in fm.fontManager.ttflist]
if 'Microsoft YaHei' in available_fonts:
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
elif 'SimHei' in available_fonts:
    plt.rcParams['font.sans-serif'] = ['SimHei']
else:
    plt.rcParams['font.sans-serif'] = ['sans-serif']
plt.rcParams['axes.unicode_minus'] = False

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 离散配色（5级）
boundaries = [0, 0.35, 0.45, 0.55, 0.65, 1.0]
colors = ['#2c7bb6', '#abd9e9', '#ffffbf', '#fdae61', '#d7191c']
cmap_disc = mcolors.ListedColormap(colors)
norm_disc = mcolors.BoundaryNorm(boundaries, cmap_disc.N)

# ================== 读取数据 ==================
df = pd.read_excel(INPUT_EXCEL)
df = df.dropna(subset=["纬度", "经度", PLOT_COLUMN])
df = df.drop_duplicates(subset=["纬度", "经度"], keep='first')

district_list = sorted(df["片区"].unique(), key=lambda x: int(re.search(r'(\d+)', x).group(1)))
print(f"共 {len(district_list)} 个片区")

# ================== 预计算统一窗口大小 ==================
max_span = 0
for district in district_list:
    sub = df[df["片区"] == district]
    if len(sub) == 0:
        continue
    gdf_sub = gpd.GeoDataFrame(sub, geometry=gpd.points_from_xy(sub["经度"], sub["纬度"]), crs="EPSG:4326")
    gdf_sub_3857 = gdf_sub.to_crs(epsg=3857)
    bb = gdf_sub_3857.total_bounds
    span = max(bb[2] - bb[0], bb[3] - bb[1])
    max_span = max(max_span, span)
window_size = max_span * 1.15
print(f"统一窗口大小：{window_size:.0f} 米")

# ================== 逐个片区出图 ==================
for district in district_list:
    sub = df[df["片区"] == district]
    if len(sub) == 0:
        continue

    print(f"\n正在绘制：{district}")

    gdf_sub = gpd.GeoDataFrame(sub, geometry=gpd.points_from_xy(sub["经度"], sub["纬度"]), crs="EPSG:4326")
    b = gdf_sub.total_bounds
    mid_lat = (b[3] + b[1]) / 2
    lat_step = GRID_SIZE_M / 111320.0
    lon_step = GRID_SIZE_M / (111320.0 * np.cos(np.radians(mid_lat)))

    lons = np.arange(b[0], b[2] + lon_step, lon_step)
    lats = np.arange(b[1], b[3] + lat_step, lat_step)
    grid_cells = []
    for lat in lats:
        for lon in lons:
            grid_cells.append(Polygon([(lon, lat), (lon+lon_step, lat),
                                        (lon+lon_step, lat+lat_step), (lon, lat+lat_step)]))
    grid_gdf = gpd.GeoDataFrame(geometry=grid_cells, crs="EPSG:4326")

    # 空间连接：只保留包含采样点的网格（无采样点的区域自动消失）
    joined = gpd.sjoin(grid_gdf, gdf_sub, how="inner", predicate="contains")
    if len(joined) == 0:
        print(f"  ⚠️ {district} 没有网格包含数据点，跳过")
        continue
    grid_agg = joined.groupby(joined.index)[PLOT_COLUMN].mean().reset_index()
    grid_result = grid_gdf.iloc[grid_agg["index"]].copy()
    grid_result[PLOT_COLUMN] = grid_agg[PLOT_COLUMN].values
    grid_result_3857 = grid_result.to_crs(epsg=3857)

    # 数据中心
    bb = grid_result_3857.total_bounds
    cx = (bb[0] + bb[2]) / 2
    cy = (bb[1] + bb[3]) / 2

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_xlim(cx - window_size/2, cx + window_size/2)
    ax.set_ylim(cy - window_size/2, cy + window_size/2)

    # 卫星底图
    try:
        ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery,
                        crs='EPSG:3857', zoom=15, attribution=False, zorder=1)
    except Exception as e:
        print(f"  ❌ 底图加载失败：{e}")
        plt.close(fig)
        sys.exit(1)

    # ★ 绘制网格：去掉黑边
    grid_result_3857.plot(
        column=PLOT_COLUMN, ax=ax, cmap=cmap_disc, norm=norm_disc,
        edgecolor='none', linewidth=0, alpha=0.75, zorder=2
    )

    ax.text(0.03, 0.03, district, transform=ax.transAxes,
            fontsize=14, ha='left', va='bottom', color='black',
            bbox=dict(boxstyle='square,pad=0.3', facecolor='white',
                      edgecolor='none', alpha=0.85), zorder=5)

    ax.set_axis_off()

    output_path = os.path.join(OUTPUT_DIR, f"{district}.png")
    plt.savefig(output_path, dpi=200, bbox_inches='tight', pad_inches=0.05, facecolor='white')
    plt.close(fig)
    print(f"  ✅ 已保存：{output_path}")

print(f"\n✅ 全部完成，共 {len(district_list)} 张图，保存在 {OUTPUT_DIR} 文件夹中。")