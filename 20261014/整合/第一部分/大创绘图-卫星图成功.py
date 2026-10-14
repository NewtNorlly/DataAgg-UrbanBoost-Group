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
OUTPUT_MAP = "武汉_更新潜力散点图.png"
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

# ================== 读取数据 ==================
df = pd.read_excel(INPUT_FILE)
df = df.dropna(subset=["纬度", "经度", PLOT_COLUMN])
df = df.drop_duplicates(subset=["纬度", "经度"], keep='first')
print(f"有效数据点: {len(df)}")

gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["经度"], df["纬度"]), crs="EPSG:4326")
gdf_3857 = gdf.to_crs(epsg=3857)

# ================== 绘图 ==================
fig, ax = plt.subplots(figsize=(16, 14))

# 1. 浅色底图（比卫星图更清爽）
try:
    print("加载底图...")
    ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron,
                    crs='EPSG:3857', zoom=12, attribution=False, zorder=1)
    print("✅ 底图加载成功")
except Exception as e:
    print(f"⚠️ 底图失败：{e}")
    ax.set_facecolor('white')

# 2. 散点，颜色代表潜力指数，点的大小也随数值略微变化
sc = ax.scatter(
    gdf_3857.geometry.x, gdf_3857.geometry.y,
    c=gdf_3857[PLOT_COLUMN], cmap="RdYlGn_r",
    s=25,                 # 点的大小，可以微调
    alpha=0.85,
    edgecolors='black', linewidth=0.2,
    zorder=3
)
cbar = plt.colorbar(sc, ax=ax, shrink=0.5, aspect=20)
cbar.set_label(PLOT_COLUMN, fontsize=12)

# 3. 范围
bounds = gdf_3857.total_bounds
margin = 1000
ax.set_xlim(bounds[0] - margin, bounds[2] + margin)
ax.set_ylim(bounds[1] - margin, bounds[3] + margin)

# 指北针
x_min, x_max = ax.get_xlim()
y_min, y_max = ax.get_ylim()
dx, dy = x_max - x_min, y_max - y_min

n_x = x_max - dx * 0.06
n_y = y_max - dy * 0.06
arrow = FancyArrowPatch(
    posA=(n_x, n_y - dy*0.025), posB=(n_x, n_y + dy*0.025),
    arrowstyle='->,head_length=3,head_width=2', lw=2, color='black', zorder=5
)
ax.add_patch(arrow)
ax.text(n_x, n_y + dy*0.035, 'N', fontsize=14, ha='center', va='bottom', fontweight='bold', zorder=5)

# 比例尺（2000米）
scale_bar_length = 2000
x_bar_start = x_min + dx * 0.05
y_bar_start = y_min + dy * 0.05
ax.plot([x_bar_start, x_bar_start + scale_bar_length],
        [y_bar_start, y_bar_start], 'k-', lw=3, zorder=5)
ax.plot([x_bar_start, x_bar_start],
        [y_bar_start - dy*0.006, y_bar_start + dy*0.006], 'k-', lw=2, zorder=5)
ax.plot([x_bar_start + scale_bar_length, x_bar_start + scale_bar_length],
        [y_bar_start - dy*0.006, y_bar_start + dy*0.006], 'k-', lw=2, zorder=5)
ax.text(x_bar_start + scale_bar_length/2, y_bar_start - dy*0.02,
        f'{scale_bar_length} m', ha='center', fontsize=10, zorder=5)

ax.set_axis_off()
ax.set_title("武汉更新潜力指数散点图", fontsize=16, pad=20)

plt.tight_layout()
plt.savefig(OUTPUT_MAP, dpi=250, bbox_inches='tight', facecolor='white')
plt.show()
print(f"✅ 已保存至 {OUTPUT_MAP}")