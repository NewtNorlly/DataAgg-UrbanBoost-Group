import dashscope
import json
import os
import time
import base64
import io
import pandas as pd
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# === 1. 配置参数 ===
# ⚠️ 请在这里填入你的阿里云 DashScope API Key
API_KEY = 'sk-eaedbd54921940988afd7c9e42cbeb7a'

# 你的图片总文件夹路径
ROOT_FOLDER = r'E:\图片4'

# 输出文件名
OUTPUT_EXCEL = '华安里_全量空间感知结果2.xlsx'
OUTPUT_JSON = '华安里_全量空间感知结果2.json'


# === 2. 辅助函数：提取 GPS 坐标 ===
def get_coordinates(exif_data):
    """将 EXIF 中的 GPS 原始数据转换为经纬度字符串"""
    if 34853 not in exif_data:
        return "无GPS信息"

    gps = exif_data[34853]
    lat = lon = None

    # 解析纬度
    if 2 in gps and 1 in gps:
        lat_ref = gps[1]
        lat_val = gps[2]
        lat = lat_val[0] + lat_val[1] / 60 + lat_val[2] / 3600
        if lat_ref == 'S': lat = -lat

    # 解析经度
    if 4 in gps and 3 in gps:
        lon_ref = gps[3]
        lon_val = gps[4]
        lon = lon_val[0] + lon_val[1] / 60 + lon_val[2] / 3600
        if lon_ref == 'W': lon = -lon

    if lat and lon:
        return f"{lat:.5f}, {lon:.5f}"
    return "解析失败"


# === 3. 辅助函数：提取图片元数据 ===
def get_exif_data(image_path):
    """从图片中提取拍摄时间和GPS信息"""
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()

        if not exif_data:
            return "未知时间", "未知位置"

        # 1. 提取时间
        time_info = "未知时间"
        if 36867 in exif_data:
            time_info = exif_data[36867]
        elif 306 in exif_data:
            time_info = exif_data[306]

        # 2. 提取 GPS
        gps_info = get_coordinates(exif_data)

        return time_info, gps_info

    except Exception as e:
        print(f"   ⚠️ 读取EXIF出错: {e}")
        return "读取错误", "读取错误"


# === 4. 系统提示词 (30个维度) ===
SYSTEM_PROMPT = """
你是一位城市科学研究专家。请依据输入的街景图像，输出可供后续感知评价使用的学术化描述文本。

要求：
1. 采用学术且专业的表达方式，引用城市规划和社会学关键术语。
2. 使用正式、严谨的语气，注重逻辑与条理性。
3. 所有输出必须完全使用中文，包括JSON字段名称。

请从以下30个维度进行深入分析并以中文JSON格式输出：
1. 视觉多样性：街道空间颜色、材质、纹理的丰富程度
2. 空间开阔度：街景是否通透，视野是否受限
3. 空间整洁度：地面、立面、公共设施等是否整洁、无明显破损或杂乱
4. 景观特色度：是否具有独特的地标性元素、地域文化符号
5. 美感评价：对于街景整体的视觉舒适感、艺术性、和谐度的主观评价
6. 绿化覆盖率：视野内植被密度、树冠覆盖率
7. 植物健康度：植被种类、多样性、色彩饱和度
8. 水体可见度：是否存在河流、湖泊、湿地等水景元素
9. 生态廊道连通性：绿地或水体之间的连接状况
10. 自然舒适感：主观上感受到的放松度、亲自然感、隔音降噪效果等
11. 污染可见度：是否能观察到垃圾、工业设施或其他潜在污染源
12. 噪音干扰度：可视线索范围内是否有交通流量、工地施工、商业嘈杂等
13. 热岛效应迹象：建筑密度、遮阴状况、地面铺装材质对热环境的影响
14. 海绵城市元素：雨水花园、下沉式绿地、立面绿化、屋顶花园等可持续元素可见度
15. 负面情绪度：街景是否带来压抑、沉闷或疲惫的心理感受
16. 交通可达性：人行道、自行车道的连续性与宽度，公共交通站点分布
17. 交通秩序度：是否有秩序的车流、人流，是否有拥堵或混行现象
18. 社会与空间公平：是否表现出某种空间不平等或设施分配不均
19. 休憩与交往空间：街边长椅、绿荫空间、凉亭或遮阳蓬等分布与质量
20. 无障碍设施：缘石坡道、无障碍通道、电梯、盲道等配置情况
21. 商业多样性：商铺类型数量及分布
22. 街道繁荣度：人流量、车流量、店铺门庭若市程度
23. 摊贩活动：是否有街头文化活动，是否显示出灵活经营形态
24. 商业环境：招牌设计、橱窗布置、店铺整洁度等
25. 经济活力：通过地标性商场或品牌密集度可推断的消费水平、商圈影响范围
26. 文化符号：具有地方特色的雕塑、建筑、传统图案等
27. 历史文脉：老建筑保护情况、文物古迹、历史街区完整度
28. 公共艺术：壁画、装置艺术、小品等对城市氛围的提升
29. 社区归属感：可视化的社区布告栏、社区活动场所、邻里交往空间
30. 多元文化融合度：是否能在街景中观察到各类族群、文化活动痕迹等

输出格式（必须严格遵守，只输出JSON，不要有其他废话）：
{
"视觉多样性": "详细的描述...",
"空间开阔度": "详细的描述...",
...
"多元文化融合度": "详细的描述..."
}
"""


# === 5. 定义图像分析函数 (核心修复：增加自动压缩) ===
def analyze_image(image_path):
    """分析单张图片并返回结果（已修复：增加自动压缩功能）"""
    try:
        # --- 第一步：读取并压缩图片 (解决全景图过大导致的 400 错误) ---
        img = Image.open(image_path)

        # 获取原始尺寸
        width, height = img.size

        # 设置最大边长限制 (比如限制长边为 1024 像素)
        # 全景图通常很长，压缩到 1024 足够 AI 识别细节
        max_size = 1024

        # 如果图片比限制大，就进行缩放
        if width > max_size or height > max_size:
            # 计算缩放比例
            ratio = min(max_size / width, max_size / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)

            # 执行缩放 (LANCZOS 是高质量缩放算法)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"   ℹ️ 图片已自动压缩: {width}x{height} -> {new_width}x{new_height}")

        # 将处理后的图片保存到内存流中
        output_buffer = io.BytesIO()
        # 保存为 JPEG 格式，质量 85% (既保证清晰度又减小体积)
        img.save(output_buffer, format='JPEG', quality=85)
        output_buffer.seek(0)  # 指针回到开头

        # 读取内存中的数据并转 Base64
        img_bytes = output_buffer.getvalue()
        base64_image = base64.b64encode(img_bytes).decode('utf-8')

        # --- 第二步：构造数据 URI ---
        image_data_uri = f"data:image/jpeg;base64,{base64_image}"

        # --- 第三步：调用模型 ---
        response = dashscope.MultiModalConversation.call(
            model='qwen-vl-plus',
            api_key=API_KEY,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': [
                    {'image': image_data_uri},
                    {'text': '请分析这张街景图片。'}
                ]}
            ]
        )

        # --- 第四步：处理响应 ---
        if response.status_code == 200:
            raw_content = response.output.choices[0].message.content
            result = None

            if isinstance(raw_content, dict):
                result = raw_content
            elif isinstance(raw_content, list):
                content = raw_content[0]
                if isinstance(content, dict):
                    result = content
                else:
                    result = json.loads(content)
            elif isinstance(raw_content, str):
                result = json.loads(raw_content)

            return result
        else:
            # 打印具体错误信息，方便调试
            print(f"   ❌ API 错误详情: {response.output}")
            return {"错误": f"API调用失败，状态码: {response.status_code}"}

    except Exception as e:
        print(f"   ❌ 本地处理出错: {e}")
        return {"错误": str(e)}


# === 6. 递归遍历与批量处理 ===
def recursive_batch_analyze():
    all_results = []

    print(f"🚀 开始扫描总目录: {ROOT_FOLDER}")

    for dirpath, dirnames, filenames in os.walk(ROOT_FOLDER):
        current_folder_name = os.path.basename(dirpath)
        image_files = [f for f in filenames if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

        if image_files:
            print(f"\n🔍 发现图片文件夹: [{current_folder_name}]，共 {len(image_files)} 张图片，开始分析...")

            for i, filename in enumerate(image_files):
                # 拼接完整路径
                image_path = os.path.join(dirpath, filename)
                print(f"   📷 [{current_folder_name}] 正在分析 [{i + 1}/{len(image_files)}]: {filename}")

                # --- 提取元数据 ---
                capture_time, gps_location = get_exif_data(image_path)

                # 生成建议的新文件名 (替换非法字符)
                safe_time = capture_time.replace(":", "-").replace(" ",
                                                                   "_") if capture_time != "未知时间" else "TimeUnknown"
                safe_gps = gps_location.replace(",", "_").replace(" ",
                                                                  "_") if gps_location != "未知位置" else "LocUnknown"
                # 格式：时间_经纬度_原文件名
                suggested_filename = f"{safe_time}_{safe_gps}_{filename}"

                # 调用 AI 分析
                result_dict = analyze_image(image_path)

                # --- 将元数据写入结果 ---
                result_dict["拍摄时间"] = capture_time
                result_dict["GPS坐标"] = gps_location
                result_dict["建议文件名"] = suggested_filename
                result_dict["原文件名"] = filename
                result_dict["源文件夹"] = current_folder_name
                result_dict["图片路径"] = image_path

                all_results.append(result_dict)
                time.sleep(0.5)  # 稍微停顿一下，防止API限流

    return all_results


# === 7. 保存结果 ===
def save_results(data_list):
    if not data_list:
        print("❌ 没有数据需要保存。")
        return

    # 1. 保存 JSON 备份
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data_list, f, ensure_ascii=False, indent=4)

    # 2. 保存 Excel
    df = pd.DataFrame(data_list)
    # 调整列顺序，把重要的信息放前面
    cols = ["源文件夹", "原文件名", "建议文件名", "拍摄时间", "GPS坐标"] + [c for c in df.columns if
                                                                            c not in ["源文件夹", "原文件名",
                                                                                      "建议文件名", "拍摄时间",
                                                                                      "GPS坐标"]]
    df = df[cols]

    df.to_excel(OUTPUT_EXCEL, index=False)

    print(f"\n✅ 全部分析完成！")
    print(f"📊 Excel 文件已生成: {OUTPUT_EXCEL}")
    print(f"💾 JSON 备份已生成: {OUTPUT_JSON}")


# === 8. 执行入口 ===
if __name__ == "__main__":
    results = recursive_batch_analyze()
    save_results(results)