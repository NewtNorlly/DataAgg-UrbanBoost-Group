"""
合并低置信格网：把点数<3的格网合并到最近的有点格网
"""
"""
import pandas as pd
import numpy as np
import geopandas as gpd
from scipy.spatial import cKDTree

# 读300米格网
gdf = gpd.read_file("武汉_300m格网_更新潜力.gpkg")

# 分离高置信和低置信
high = gdf[gdf["点数"] >= 3].copy()
low = gdf[gdf["点数"] < 3].copy()

print(f"高置信格网: {len(high)}")
print(f"低置信格网: {len(low)}")

if len(low) > 0:
    # 用高置信格网建KDTree
    high_coords = np.array([(g.centroid.x, g.centroid.y) for g in high.geometry])
    tree = cKDTree(high_coords)

    # 每个低置信格网找最近的高置信格网
    low_coords = np.array([(g.centroid.x, g.centroid.y) for g in low.geometry])
    dists, idxs = tree.query(low_coords, k=1)
    low["最近高置信ID"] = high.iloc[idxs]["grid_id"].values

    # 把低置信格网的属性汇总到高置信格网
    # 简化处理：直接丢弃低置信，用高置信做后续分析
    # 或者按点数加权合并
    print(f"低置信格网平均距离最近高置信格网: {dists.mean():.0f}m")

# 简版：直接用高置信做后续
high.to_file("武汉_300m格网_高置信.gpkg", driver="GPKG")
high.drop(columns="geometry").to_excel("武汉_300m格网_高置信.xlsx", index=False)
print(f"\n最终用于聚类的格网数: {len(high)}")

"""

"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, calinski_harabasz_score
import geopandas as gpd

# 1. 读高置信格网
gdf = gpd.read_file("武汉_300m格网_高置信.gpkg")
df = pd.read_excel("武汉_300m格网_高置信.xlsx")

# 2. 聚类特征
features = [
    "街巷空间与交通通达", "建筑风貌与界面品质", "便民生活与服务韧性",
    "环境秩序与生态韧性", "公共安全与心理感知", "场所氛围与情感价值",
    "外部供给指数", "更新潜力指数"
]

X = df[features].fillna(df[features].median())
X_scaled = StandardScaler().fit_transform(X)

# 3. K值评估
print("=" * 60)
print("K值评估:")
print("=" * 60)

results = []
for k in range(2, 10):
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)
    sil = silhouette_score(X_scaled, labels)
    ch = calinski_harabasz_score(X_scaled, labels)
    inertia = km.inertia_
    results.append({"K": k, "轮廓系数": sil, "CH指数": ch, "惯性": inertia})
    print(f"K={k}: 轮廓系数={sil:.3f}, CH={ch:.1f}, 惯性={inertia:.1f}")

results_df = pd.DataFrame(results)
results_df.to_excel("K值评估.xlsx", index=False)

# 4. 画肘部图 + 轮廓系数图
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].plot(results_df["K"], results_df["惯性"], "bo-")
axes[0].set_xlabel("K"); axes[0].set_ylabel("惯性")
axes[0].set_title("肘部法则")
axes[1].plot(results_df["K"], results_df["轮廓系数"], "ro-")
axes[1].set_xlabel("K"); axes[1].set_ylabel("轮廓系数")
axes[1].set_title("轮廓系数")
plt.tight_layout()
plt.savefig("K值评估.png", dpi=300)
plt.close()

print("\n已保存 K值评估.xlsx / K值评估.png")
"""


"""
import pandas as pd
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

# 字体
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 读数据
gdf = gpd.read_file("武汉_300m格网_高置信.gpkg")

features = [
    "街巷空间与交通通达", "建筑风貌与界面品质", "便民生活与服务韧性",
    "环境秩序与生态韧性", "公共安全与心理感知", "场所氛围与情感价值",
    "外部供给指数", "更新潜力指数"
]

X = gdf[features].fillna(gdf[features].median())
X_scaled = StandardScaler().fit_transform(X)

# K=4聚类
K = 4
km = KMeans(n_clusters=K, random_state=42, n_init=10)
gdf["聚类"] = km.fit_predict(X_scaled)

# 聚类中心
centers = pd.DataFrame(km.cluster_centers_, columns=features)
centers.index = [f"类型{i}" for i in range(K)]

print("=" * 80)
print("各聚类中心（标准化后，正=高于均值，负=低于均值）")
print("=" * 80)
print(centers.round(2))

print("\n" + "=" * 80)
print("各类型特征总结（用于命名）")
print("=" * 80)

for i in range(K):
    row = centers.iloc[i]
    top3 = row.nlargest(3)
    bot3 = row.nsmallest(3)
    n = (gdf["聚类"] == i).sum()
    print(f"\n【类型{i}】 样本数={n} ({n/len(gdf)*100:.1f}%)")
    print(f"  明显高: {', '.join([f'{k}={v:.2f}' for k,v in top3.items()])}")
    print(f"  明显低: {', '.join([f'{k}={v:.2f}' for k,v in bot3.items()])}")

# 保存
gdf.to_file("武汉_300m格网_聚类.gpkg", driver="GPKG")
gdf.drop(columns="geometry").to_excel("武汉_300m格网_聚类.xlsx", index=False)
centers.to_excel("聚类中心.xlsx")

# 画聚类地图
fig, ax = plt.subplots(figsize=(12, 10))
gdf.plot(column="聚类", categorical=True, legend=True, ax=ax,
         cmap="Set2", edgecolor="white", linewidth=0.3)
ax.set_title(f"武汉城市更新潜力空间聚类 (K={K})", fontsize=14)
ax.axis("off")
plt.savefig("聚类地图.png", dpi=300, bbox_inches="tight")
plt.close()

# 画雷达图
fig, axes = plt.subplots(1, K, figsize=(5*K, 5), subplot_kw=dict(polar=True))
for i in range(K):
    ax = axes[i]
    values = centers.iloc[i].values
    angles = np.linspace(0, 2*np.pi, len(features), endpoint=False).tolist()
    values = np.concatenate([values, [values[0]]])
    angles += angles[:1]
    ax.plot(angles, values, 'o-', linewidth=2)
    ax.fill(angles, values, alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(features, fontsize=8)
    ax.set_title(f"类型{i}", fontsize=12)
plt.tight_layout()
plt.savefig("聚类雷达图.png", dpi=300, bbox_inches="tight")
plt.close()

print("\n已保存：武汉_300m格网_聚类.gpkg / .xlsx / 聚类中心.xlsx / 聚类地图.png / 聚类雷达图.png")

"""


"""
import geopandas as gpd
import numpy as np
from libpysal.weights import Queen
from esda.moran import Moran

gdf = gpd.read_file("武汉_300m格网_聚类.gpkg")

# 建空间权重
w = Queen.from_dataframe(gdf)
w.transform = 'r'

# 对聚类标签做Moran's I
moran = Moran(gdf["聚类"].values, w)
print(f"Moran's I = {moran.I:.3f}, p = {moran.p_sim:.4f}")

if moran.p_sim < 0.05:
    print("✅ 聚类结果有显著空间聚集")
    if moran.I > 0.3:
        print("   聚集性强，聚类合理")
    else:
        print("   聚集性中等，需进一步分析")
else:
    print("❌ 聚类结果空间随机分布，可能不稳定")
    print("   建议：用空间约束聚类（SKATER/ClustGeo）或降K")
    
"""
