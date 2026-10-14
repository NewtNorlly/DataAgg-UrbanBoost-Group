import os
import re
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Rectangle, Polygon as MplPolygon
from PIL import Image
import warnings
warnings.filterwarnings("ignore")

# ================== 配置 ==================
INPUT_DIR = "片区单独出图"
OUTPUT_FILE = "武汉_全片区拼图.png"
N_COLS = 7
WINDOW_SIZE_M = 2313          # ★ 必须和单图脚本里的 window_size 一致！

# 中文字体
available_fonts = [f.name for f in fm.fontManager.ttflist]
if 'Microsoft YaHei' in available_fonts:
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
elif 'SimHei' in available_fonts:
    plt.rcParams['font.sans-serif'] = ['SimHei']
else:
    plt.rcParams['font.sans-serif'] = ['sans-serif']
plt.rcParams['axes.unicode_minus'] = False

colors = ['#2c7bb6', '#abd9e9', '#ffffbf', '#fdae61', '#d7191c']

# ================== 扫描图片 ==================
def sort_key(fname):
    m = re.search(r'(\d+)', fname)
    return int(m.group(1)) if m else 9999

img_files = sorted([f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.png')], key=sort_key)
print(f"找到 {len(img_files)} 张片区图")
if len(img_files) == 0:
    raise FileNotFoundError(f"{INPUT_DIR} 中没有 PNG")

n_imgs = len(img_files)
n_rows = int(np.ceil(n_imgs / N_COLS))

# ================== 绘制拼图 ==================
import matplotlib.gridspec as gridspec
fig = plt.figure(figsize=(N_COLS * 3.2 + 2.8, n_rows * 3.2), facecolor='white')
gs = gridspec.GridSpec(
    n_rows, N_COLS + 1,
    width_ratios=[1] * N_COLS + [0.95],
    wspace=0.02, hspace=0.02,
    left=0.01, right=0.99, top=0.99, bottom=0.01
)

for idx, fname in enumerate(img_files):
    r, c = idx // N_COLS, idx % N_COLS
    ax = fig.add_subplot(gs[r, c])
    img = Image.open(os.path.join(INPUT_DIR, fname))
    ax.imshow(img)
    ax.set_axis_off()

for idx in range(n_imgs, n_rows * N_COLS):
    r, c = idx // N_COLS, idx % N_COLS
    ax = fig.add_subplot(gs[r, c])
    ax.set_axis_off()

# ================== 右侧栏 ==================
ax_right_top = fig.add_subplot(gs[0, N_COLS])
ax_right_top.set_xlim(0, 1); ax_right_top.set_ylim(0, 1); ax_right_top.set_axis_off()

# ---------- 指北针 ----------
cx, cy, size = 0.5, 0.78, 0.22
tip    = (cx, cy + size * 0.5)
left   = (cx - size * 0.22, cy - size * 0.5)
right  = (cx + size * 0.22, cy - size * 0.5)
center = (cx, cy - size * 0.08)
ax_right_top.add_patch(MplPolygon([tip, left, center], closed=True,
                                   facecolor='#1a1a1a', edgecolor='black',
                                   linewidth=1.0, zorder=3))
ax_right_top.add_patch(MplPolygon([tip, right, center], closed=True,
                                   facecolor='#f5f5f5', edgecolor='black',
                                   linewidth=1.0, zorder=3))
ax_right_top.plot([cx, cx], [center[1], tip[1]], color='black', linewidth=0.8, zorder=4)
ax_right_top.text(cx, tip[1] + 0.03, 'N', ha='center', va='bottom',
                   fontsize=18, fontweight='bold', zorder=5)

# ---------- 计算地图比例（关键修正） ----------
# 先强制画一次布局，让 matplotlib 计算出子图的实际像素宽度
fig.canvas.draw()

# 取任意一张地图子图
sample_ax = fig.axes[0]
bbox = sample_ax.get_window_extent()
map_width_px = bbox.width             # 一张地图子图的像素宽度
map_width_inch = map_width_px / fig.dpi

# 一张地图覆盖 WINDOW_SIZE_M 米，所以：
meters_per_inch = WINDOW_SIZE_M / map_width_inch

# 右侧栏的像素宽度
right_bbox = ax_right_top.get_window_extent()
right_width_inch = right_bbox.width / fig.dpi

# ---------- 比例尺（按地图真实比例绘制） ----------
# 选一个合适的整数长度（比如 500 米），换算成右侧栏的相对宽度
scale_length_m = 500
scale_length_inch = scale_length_m / meters_per_inch
scale_fraction = scale_length_inch / right_width_inch

# 画比例尺：只分 2 段（黑白各一）
n_blocks = 2
block_frac = scale_fraction / n_blocks
x0 = (1.0 - scale_fraction) / 2      # 居中
y0 = 0.30
block_h = 0.035

for i in range(n_blocks):
    color = 'black' if i % 2 == 0 else 'white'
    ax_right_top.add_patch(Rectangle((x0 + i * block_frac, y0),
                                      block_frac, block_h,
                                      facecolor=color, edgecolor='black',
                                      linewidth=0.8, zorder=3))

# 只标首尾两个数字：0 和 500
ax_right_top.text(x0, y0 - 0.018, '0',
                   ha='center', va='top', fontsize=9, zorder=3)
ax_right_top.text(x0 + scale_fraction, y0 - 0.018, f'{scale_length_m}',
                   ha='center', va='top', fontsize=9, zorder=3)

# 单位标注
ax_right_top.text(0.5, y0 - 0.07,
                   f'单位：米 (m)',
                   ha='center', va='top', fontsize=8.5, style='italic', zorder=3)

# ---------- 图例（放下半栏） ----------
if n_rows >= 2:
    ax_right_bot = fig.add_subplot(gs[1:, N_COLS])
else:
    ax_right_bot = ax_right_top
ax_right_bot.set_xlim(0, 1); ax_right_bot.set_ylim(0, 1); ax_right_bot.set_axis_off()

labels = ['低  (0–0.35)', '中低 (0.35–0.45)', '中  (0.45–0.55)',
          '中高 (0.55–0.65)', '高  (>0.65)']

ax_right_bot.text(0.5, 0.92, '更新潜力等级',
                   ha='center', va='center', fontsize=12,
                   fontweight='bold', zorder=3)

box_w, box_h = 0.20, 0.045
for i, (c, lb) in enumerate(zip(colors, labels)):
    yy = 0.80 - i * 0.07
    ax_right_bot.add_patch(Rectangle((0.10, yy), box_w, box_h,
                                      facecolor=c, edgecolor='black',
                                      linewidth=0.6, zorder=3))
    ax_right_bot.text(0.10 + box_w + 0.05, yy + box_h / 2, lb,
                       ha='left', va='center', fontsize=10, zorder=3)

plt.savefig(OUTPUT_FILE, dpi=220, bbox_inches='tight',
            pad_inches=0.15, facecolor='white')
plt.close(fig)
print(f"\n✅ 拼图完成：{OUTPUT_FILE}")