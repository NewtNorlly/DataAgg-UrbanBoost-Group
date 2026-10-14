import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

import pandas as pd
import numpy as np
import json
import re
import torch
from transformers import pipeline

# ================== 配置 ==================
CITY_NAME = "武汉14"
INPUT_FILE = f"武汉_Day14_后湖_生活区街景AI分析结果.xlsx"
OUTPUT_FILE = f"{CITY_NAME}_六维感知得分.xlsx"

# 30个维度名称（必须与你 AI 输出的 JSON key 完全一致）
DIM_NAMES = [
    "空间开阔度", "交通可达性", "交通秩序度", "有效步行空间", "无障碍设施",
    "视觉多样性", "美感评价", "外立面污损与破损", "违规搭建覆盖", "首层界面开口率",
    "商业多样性", "街道繁荣度", "摊贩活动", "商业环境", "非正规便民服务点",
    "绿化覆盖率", "植物健康度", "污染可见度", "噪音干扰度", "生活垃圾堆积",
    "墙面违规张贴", "负面情绪度", "夜间照明设施", "街道眼开口指数", "消防通道畅通度",
    "景观特色度", "文化符号", "历史文脉", "社区归属感", "自发绿化与装饰"
]

# 维度映射：30个AI指标 → 6个框架维度 (是否负向)
AI_TO_FRAMEWORK = {
    "空间开阔度": ("街巷空间与交通通达", False),
    "交通可达性": ("街巷空间与交通通达", False),
    "交通秩序度": ("街巷空间与交通通达", False),
    "有效步行空间": ("街巷空间与交通通达", True),
    "无障碍设施": ("街巷空间与交通通达", False),
    "视觉多样性": ("建筑风貌与界面品质", False),
    "美感评价": ("建筑风貌与界面品质", False),
    "外立面污损与破损": ("建筑风貌与界面品质", True),
    "违规搭建覆盖": ("建筑风貌与界面品质", True),
    "首层界面开口率": ("建筑风貌与界面品质", False),
    "商业多样性": ("便民生活与服务韧性", False),
    "街道繁荣度": ("便民生活与服务韧性", False),
    "摊贩活动": ("便民生活与服务韧性", False),
    "商业环境": ("便民生活与服务韧性", False),
    "非正规便民服务点": ("便民生活与服务韧性", False),
    "绿化覆盖率": ("环境秩序与生态韧性", False),
    "植物健康度": ("环境秩序与生态韧性", False),
    "污染可见度": ("环境秩序与生态韧性", True),
    "噪音干扰度": ("环境秩序与生态韧性", True),
    "生活垃圾堆积": ("环境秩序与生态韧性", True),
    "墙面违规张贴": ("环境秩序与生态韧性", True),
    "负面情绪度": ("公共安全与心理感知", True),
    "夜间照明设施": ("公共安全与心理感知", False),
    "街道眼开口指数": ("公共安全与心理感知", False),
    "消防通道畅通度": ("公共安全与心理感知", False),
    "景观特色度": ("场所氛围与情感价值", False),
    "文化符号": ("场所氛围与情感价值", False),
    "历史文脉": ("场所氛围与情感价值", False),
    "社区归属感": ("场所氛围与情感价值", False),
    "自发绿化与装饰": ("场所氛围与情感价值", False),
}

NEGATIVE_INDICATORS = [k for k, (_, neg) in AI_TO_FRAMEWORK.items() if neg]

# ================== 解析 text 列 ==================
def parse_text_column(text_value):
    """从 text 列中提取 30 个维度的文本，返回字典"""
    if not isinstance(text_value, str):
        return {}
    text = text_value.strip()
    # 去掉 markdown 代码块
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # 尝试直接解析 JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {k: str(v) for k, v in data.items() if k in DIM_NAMES}
    except:
        pass

    # 处理双引号转义问题："" -> "
    text_fixed = text.replace('""', '"').strip().strip('"')
    try:
        data = json.loads(text_fixed)
        if isinstance(data, dict):
            return {k: str(v) for k, v in data.items() if k in DIM_NAMES}
    except:
        pass

    # 正则兜底（纯文本格式）
    result = {}
    for dim in DIM_NAMES:
        pattern = rf'{dim}[：:]\s*(.*?)(?=\s*(?:{"|".join(DIM_NAMES)})[：:]|$)'
        match = re.search(pattern, text_fixed, re.DOTALL)
        if match:
            result[dim] = match.group(1).strip()
    return result

# ================== 加载 BERT ==================
print("加载 BERT 情感分析模型...")
device = 0 if torch.cuda.is_available() else -1
sent_pipeline = pipeline(
    "sentiment-analysis",
    model="nlptown/bert-base-multilingual-uncased-sentiment",
    device=device, max_length=512, truncation=True
)

def bert_score(text):
    if not isinstance(text, str) or len(text.strip()) < 10:
        return 0.5
    try:
        result = sent_pipeline(text)[0]
        stars = int(result['label'][0])
        return (stars - 1) / 4.0
    except:
        return 0.5

# ================== 主程序 ==================
def main():
    df = pd.read_excel(INPUT_FILE)
    total_before = len(df)
    print(f"读取到 {total_before} 行数据")

    # 过滤无效行：只保留分析状态为“成功”的行
    valid_mask = df["分析状态"].astype(str).str.strip() == "成功"
    df = df[valid_mask].copy()
    print(f"过滤后有效行数：{len(df)}（移除 {total_before - len(df)} 条失败/重复记录）")

    # 初始化分数列
    for dim in DIM_NAMES:
        df[f"{dim}_score"] = np.nan

    # 逐行解析并评分
    for i, (_, row) in enumerate(df.iterrows()):
        text_val = row.get("text", "")
        parsed = parse_text_column(text_val)
        for dim, content in parsed.items():
            score = bert_score(content)
            if dim in NEGATIVE_INDICATORS:
                score = 1.0 - score
            df.at[df.index[i], f"{dim}_score"] = score
        if (i + 1) % 50 == 0:
            print(f"  已评分 {i+1}/{len(df)} 行")

    print("评分完成，开始按点位聚合...")

    # 按点位（编号、纬度、经度）分组，多视角取平均
    group_cols = ["编号", "纬度", "经度"]
    aggregated = []
    for (pid, lat, lng), group in df.groupby(group_cols):
        row = {"编号": pid, "纬度": lat, "经度": lng}
        for fw_dim in ["街巷空间与交通通达", "建筑风貌与界面品质",
                       "便民生活与服务韧性", "环境秩序与生态韧性",
                       "公共安全与心理感知", "场所氛围与情感价值"]:
            sub_dims = [d for d in DIM_NAMES if AI_TO_FRAMEWORK[d][0] == fw_dim]
            scores = []
            for d in sub_dims:
                col = f"{d}_score"
                vals = group[col].dropna().values
                scores.extend(vals)
            row[fw_dim] = np.mean(scores) if len(scores) > 0 else 0.5
        aggregated.append(row)

    result_df = pd.DataFrame(aggregated)
    result_df.to_excel(OUTPUT_FILE, index=False)
    print(f"✅ 六维感知得分已保存至: {OUTPUT_FILE}")
    print(f"共 {len(result_df)} 个点位，每个点位包含六个维度得分。")

if __name__ == "__main__":
    main()