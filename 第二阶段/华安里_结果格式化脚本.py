"""
从已有BERT评分结果重新计算+格式化输出
补上维度7（针灸式更新潜力）并格式化小数
"""
import json, pandas as pd

INPUT_JSON = r"C:\Honey\华安里_感知得分.json"
OUTPUT_CSV = r"C:\Honey\华安里_感知得分.csv"
OUTPUT_EXCEL = r"C:\Honey\华安里_感知得分.xlsx"

DIMENSION_WEIGHTS = {
    "街巷空间与交通通达": 0.16,
    "建筑风貌与界面品质": 0.13,
    "便民生活与服务韧性": 0.15,
    "环境秩序与生态韧性": 0.14,
    "公共安全与心理感知": 0.13,
    "场所氛围与情感价值": 0.14,
    "针灸式更新潜力": 0.15,
}
FW_DIMS = list(DIMENSION_WEIGHTS.keys())

with open(INPUT_JSON, 'r', encoding='utf-8') as f:
    data = json.load(f)

rows = []
for rec in data:
    fs = rec.get('framework_scores', {})
    
    # 补维度7：前6维反值（感知越差→更新潜力越大）
    front6 = [fs[d] for d in FW_DIMS[:6] if fs.get(d) is not None]
    if front6 and fs.get('针灸式更新潜力') is None:
        fs['针灸式更新潜力'] = round(1.0 - sum(front6) / len(front6), 4)
    
    # 综合感知得分（前6维加权）
    weighted_sum = 0.0
    weight_sum = 0.0
    for d in FW_DIMS[:6]:
        s = fs.get(d)
        if s is not None:
            weighted_sum += s * DIMENSION_WEIGHTS[d]
            weight_sum += DIMENSION_WEIGHTS[d]
    composite = round(weighted_sum / weight_sum, 4) if weight_sum > 0 else None
    
    # 解析GPS
    gps = rec.get('gps', '')
    lat, lng = '', ''
    if ',' in gps:
        parts = gps.split(',')
        lat, lng = parts[0], parts[1]
    
    row = {
        '编号': rec['id'],
        '文件名': rec['filename'],
        'GPS纬度': lat,
        'GPS经度': lng,
        '综合感知得分': composite,
        '街巷空间与交通通达': round(fs.get('街巷空间与交通通达'), 4) if fs.get('街巷空间与交通通达') is not None else None,
        '建筑风貌与界面品质': round(fs.get('建筑风貌与界面品质'), 4) if fs.get('建筑风貌与界面品质') is not None else None,
        '便民生活与服务韧性': round(fs.get('便民生活与服务韧性'), 4) if fs.get('便民生活与服务韧性') is not None else None,
        '环境秩序与生态韧性': round(fs.get('环境秩序与生态韧性'), 4) if fs.get('环境秩序与生态韧性') is not None else None,
        '公共安全与心理感知': round(fs.get('公共安全与心理感知'), 4) if fs.get('公共安全与心理感知') is not None else None,
        '场所氛围与情感价值': round(fs.get('场所氛围与情感价值'), 4) if fs.get('场所氛围与情感价值') is not None else None,
        '针灸式更新潜力': round(fs.get('针灸式更新潜力'), 4) if fs.get('针灸式更新潜力') is not None else None,
    }
    rows.append(row)

df = pd.DataFrame(rows)

# 统计
valid = df['综合感知得分'].dropna()
print(f"有效记录: {len(valid)}")
print(f"综合感知得分: 均值={valid.mean():.4f}, 最高={valid.max():.4f}, 最低={valid.min():.4f}")
print()
for d in FW_DIMS:
    col = df[d].dropna()
    if len(col) > 0:
        print(f"  {d}: 均值={col.mean():.4f}, 最高={col.max():.4f}, 最低={col.min():.4f}")

# 格式化输出
df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
print(f"\nCSV已保存: {OUTPUT_CSV}")
df.to_excel(OUTPUT_EXCEL, index=False)
print(f"Excel已保存: {OUTPUT_EXCEL}")

# 也更新JSON
for r, row in zip(data, rows):
    r['综合感知得分'] = row['综合感知得分']
    r['framework_scores']['针灸式更新潜力'] = row['针灸式更新潜力']

with open(INPUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"JSON已更新: {INPUT_JSON}")
print("\n完成！")
