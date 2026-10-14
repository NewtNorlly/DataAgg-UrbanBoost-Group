"""
XGBoost多分类 + SHAP解释（修复版）
"""
import pandas as pd
import numpy as np
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

gdf = pd.read_excel("武汉_300m格网_聚类.xlsx")

features = [
    "街巷空间与交通通达", "建筑风貌与界面品质", "便民生活与服务韧性",
    "环境秩序与生态韧性", "公共安全与心理感知", "场所氛围与情感价值",
    "外部供给指数", "内部品质指数"
]

X = gdf[features].fillna(gdf[features].median())
y = gdf["聚类"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3, random_state=42, stratify=y
)

model = xgb.XGBClassifier(
    n_estimators=300, max_depth=5, learning_rate=0.05,
    random_state=42, eval_metric="mlogloss"
)
model.fit(X_train, y_train)

print("分类报告：")
print(classification_report(y_test, model.predict(X_test)))

cv = cross_val_score(model, X, y, cv=5, scoring="accuracy")
print(f"5折CV准确率: {cv.mean():.3f} ± {cv.std():.3f}")

# SHAP
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X)

# 打印shape，确认是list还是3D数组
print(f"\nshap_values 类型: {type(shap_values)}")
if isinstance(shap_values, list):
    print(f"shap_values 是 list, 长度={len(shap_values)}, 每个shape={shap_values[0].shape}")
    shap_3d = np.stack(shap_values, axis=-1)  # 转成 (n_samples, n_features, n_classes)
else:
    print(f"shap_values shape: {shap_values.shape}")
    shap_3d = shap_values

# ===== 全局重要性（多分类平均） =====
plt.figure()
shap.summary_plot(shap_3d, X, plot_type="bar", show=False)
plt.tight_layout()
plt.savefig("SHAP_全局重要性.png", dpi=300, bbox_inches="tight")
plt.close()

# ===== 每个类的蜂巢图 =====
for i in range(4):
    plt.figure()
    # 关键修复：用 shap_3d[:, :, i] 取第i类的SHAP值
    shap.summary_plot(shap_3d[:, :, i], X, show=False)
    plt.title(f"类型{i} 的SHAP解释")
    plt.tight_layout()
    plt.savefig(f"SHAP_类型{i}.png", dpi=300, bbox_inches="tight")
    plt.close()

# ===== 特征重要性表 =====
importance = pd.DataFrame({
    "特征": features,
    "重要性": model.feature_importances_
}).sort_values("重要性", ascending=False)
print("\n特征重要性：")
print(importance)
importance.to_excel("XGBoost特征重要性.xlsx", index=False)

# ===== 每个类型的SHAP平均绝对贡献 =====
shap_importance_by_class = {}
for i in range(4):
    mean_abs = np.abs(shap_3d[:, :, i]).mean(axis=0)
    shap_importance_by_class[f"类型{i}"] = mean_abs

shap_df = pd.DataFrame(shap_importance_by_class, index=features)
shap_df.to_excel("SHAP_各类型特征贡献.xlsx")
print("\n各类型SHAP特征贡献（前3）：")
for i in range(4):
    top3 = shap_df[f"类型{i}"].nlargest(3)
    print(f"类型{i}: {', '.join([f'{k}={v:.3f}' for k,v in top3.items()])}")

print("\n已保存 SHAP_全局重要性.png / SHAP_类型0~3.png / XGBoost特征重要性.xlsx / SHAP_各类型特征贡献.xlsx")