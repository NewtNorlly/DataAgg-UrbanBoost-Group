import dashscope
import json
import os
import time
import base64
import io
import pandas as pd
import sys
import traceback
import subprocess
import math
import shutil
import piexif
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


# ====================== 依赖安装与验证 ======================
def setup_environment():
    """设置运行环境，安装必要依赖"""
    print("=" * 60)
    print("🔧 环境初始化中...")
    print("=" * 60)

    required_packages = ['exifread', 'pillow-heif', 'dashscope', 'pandas', 'openpyxl', 'piexif']
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} 已安装")
        except ImportError:
            print(f"⚠️ 安装 {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package],
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
                print(f"✅ {package} 安装成功")
            except Exception as e:
                print(f"❌ {package} 安装失败: {str(e)}")
                sys.exit(1)

    # 重新导入关键模块
    global exifread, register_heif_opener, piexif
    try:
        import exifread
        from pillow_heif import register_heif_opener
        import piexif
        print("✅ 环境初始化成功")
    except Exception as e:
        print(f"❌ 环境初始化失败: {str(e)}")
        sys.exit(1)


# ====================== 配置参数 ======================
# 请替换为你的实际DashScope API Key
API_KEY = 'sk-eaedbd54921940988afd7c9e42cbeb7a'  # 必须修改！

# 原始图片文件夹路径
ROOT_FOLDER = r'E:\图片4'  # 必须修改为你的实际路径

# 处理后的文件夹路径
PROCESSED_FOLDER = ROOT_FOLDER + '_processed'

# 输出Excel文件名
OUTPUT_EXCEL = '华安里_分析结果_完整版.xlsx'

# 调试模式（True=显示详细调试信息）
DEBUG_MODE = True


# ====================== 专业EXIF工具类 ======================
class EXIFHandler:
    """专业EXIF处理类，解决GPS提取问题"""

    @staticmethod
    def extract_gps_from_original(file_path):
        """直接从原始文件提取GPS，不经过任何处理"""
        try:
            if DEBUG_MODE:
                print(f"  🔍 直接从原始文件提取GPS: {os.path.basename(file_path)}")

            # 方案1：使用exifread（最可靠）
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, details=False, stop_tag='GPS GPSLongitude')

                lat = tags.get('GPS GPSLatitude')
                lon = tags.get('GPS GPSLongitude')
                lat_ref = tags.get('GPS GPSLatitudeRef')
                lon_ref = tags.get('GPS GPSLongitudeRef')

                if all([lat, lon, lat_ref, lon_ref]):
                    coords = EXIFHandler._convert_to_decimal(lat, lon, lat_ref, lon_ref)
                    if coords:
                        return coords

            # 方案2：使用piexif（专业EXIF库）
            exif_dict = piexif.load(file_path)
            gps_ifd = exif_dict.get("GPS", {})

            if gps_ifd:
                lat_ref = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef)
                lon_ref = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef)
                lat = gps_ifd.get(piexif.GPSIFD.GPSLatitude)
                lon = gps_ifd.get(piexif.GPSIFD.GPSLongitude)

                if lat_ref and lon_ref and lat and lon:
                    lat_ref = lat_ref.decode() if isinstance(lat_ref, bytes) else lat_ref
                    lon_ref = lon_ref.decode() if isinstance(lon_ref, bytes) else lon_ref

                    lat_deg = lat[0][0] / lat[0][1] + lat[1][0] / (lat[1][1] * 60) + lat[2][0] / (lat[2][1] * 3600)
                    lon_deg = lon[0][0] / lon[0][1] + lon[1][0] / (lon[1][1] * 60) + lon[2][0] / (lon[2][1] * 3600)

                    if lat_ref == 'S':
                        lat_deg = -lat_deg
                    if lon_ref == 'W':
                        lon_deg = -lon_deg

                    if -90 <= lat_deg <= 90 and -180 <= lon_deg <= 180:
                        return f"{lat_deg:.6f},{lon_deg:.6f}"

            # 方案3：使用PIL（备用）
            img = Image.open(file_path)
            exif_data = img._getexif()
            if exif_data:
                gps_info = {}
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    if 'GPS' in str(tag_name) or tag_id == 34853:
                        gps_info[tag_name] = value

                if 34853 in gps_info:
                    gps_data = gps_info[34853]
                    if all(k in gps_data for k in [1, 2, 3, 4]):
                        lat_ref = gps_data[1].decode() if isinstance(gps_data[1], bytes) else gps_data[1]
                        lon_ref = gps_data[3].decode() if isinstance(gps_data[3], bytes) else gps_data[3]
                        lat_val = gps_data[2]
                        lon_val = gps_data[4]

                        lat_deg = lat_val[0] + lat_val[1] / 60 + lat_val[2] / 3600
                        lon_deg = lon_val[0] + lon_val[1] / 60 + lon_val[2] / 3600

                        if lat_ref.strip() == 'S':
                            lat_deg = -lat_deg
                        if lon_ref.strip() == 'W':
                            lon_deg = -lon_deg

                        if -90 <= lat_deg <= 90 and -180 <= lon_deg <= 180:
                            return f"{lat_deg:.6f},{lon_deg:.6f}"

        except Exception as e:
            if DEBUG_MODE:
                print(f"  ⚠️ GPS提取异常: {str(e)}")

        return "GPS数据缺失"

    @staticmethod
    def _convert_to_decimal(lat, lon, lat_ref, lon_ref):
        """转换GPS坐标为十进制"""
        try:
            # 处理不同格式的EXIF值
            def parse_value(val):
                if hasattr(val, 'values') and val.values:
                    v = val.values[0]
                    return v.num / v.den if hasattr(v, 'num') else float(v)
                return float(val)

            lat_deg = parse_value(lat.values[0])
            lat_min = parse_value(lat.values[1])
            lat_sec = parse_value(lat.values[2])

            lon_deg = parse_value(lon.values[0])
            lon_min = parse_value(lon.values[1])
            lon_sec = parse_value(lon.values[2])

            lat_decimal = lat_deg + lat_min / 60 + lat_sec / 3600
            lon_decimal = lon_deg + lon_min / 60 + lon_sec / 3600

            lat_ref_val = str(lat_ref.values).strip()
            lon_ref_val = str(lon_ref.values).strip()

            if lat_ref_val == 'S':
                lat_decimal = -lat_decimal
            if lon_ref_val == 'W':
                lon_decimal = -lon_decimal

            if -90 <= lat_decimal <= 90 and -180 <= lon_decimal <= 180:
                return f"{lat_decimal:.6f},{lon_decimal:.6f}"
        except Exception as e:
            if DEBUG_MODE:
                print(f"  ⚠️ 坐标转换失败: {str(e)}")
        return None

    @staticmethod
    def verify_exif_preserved(source_path, target_path):
        """验证EXIF是否被保留"""
        try:
            # 比较两个文件的EXIF大小
            source_exif = piexif.load(source_path)
            target_exif = piexif.load(target_path)

            source_gps = source_exif.get("GPS", {})
            target_gps = target_exif.get("GPS", {})

            has_gps_source = bool(source_gps)
            has_gps_target = bool(target_gps)

            if DEBUG_MODE:
                print(f"  📊 EXIF验证: 源文件GPS={has_gps_source}, 目标文件GPS={has_gps_target}")

            return has_gps_target
        except:
            return False


# ====================== 智能文件处理器 ======================
class FileProcessor:
    """智能文件处理，确保EXIF不丢失"""

    @staticmethod
    def process_file(source_path, target_folder):
        """智能处理单个文件，保留EXIF"""
        filename = os.path.basename(source_path)
        file_ext = filename.lower()
        target_path = os.path.join(target_folder, filename)

        if DEBUG_MODE:
            print(f"\n📁 处理文件: {filename}")
            print(f"   源路径: {source_path}")
            print(f"   目标路径: {target_path}")

        # 先提取GPS（从原始文件）
        gps_coord = EXIFHandler.extract_gps_from_original(source_path)
        if DEBUG_MODE:
            print(f"   🌐 原始GPS: {gps_coord}")

        try:
            if file_ext.endswith('.heic'):
                # HEIC文件处理
                result_path = FileProcessor._process_heic(source_path, target_folder)
                if result_path:
                    # 验证EXIF是否保留
                    if not EXIFHandler.verify_exif_preserved(source_path, result_path):
                        if DEBUG_MODE:
                            print("   ⚠️ EXIF未保留，重新注入GPS数据")
                        FileProcessor._inject_gps_data(source_path, result_path)
                    return result_path, gps_coord

            elif file_ext.endswith(('.jpg', '.jpeg')):
                # JPG文件处理
                result_path = FileProcessor._process_jpg(source_path, target_folder)
                if result_path:
                    # 验证EXIF
                    if not EXIFHandler.verify_exif_preserved(source_path, result_path):
                        if DEBUG_MODE:
                            print("   ⚠️ EXIF未保留，重新注入GPS数据")
                        FileProcessor._inject_gps_data(source_path, result_path)
                    return result_path, gps_coord

            elif file_ext.endswith(('.png', '.bmp', '.gif')):
                # 其他格式：直接复制，无EXIF
                shutil.copy2(source_path, target_path)
                if DEBUG_MODE:
                    print(f"   📋 复制其他格式: {filename} (无EXIF)")
                return target_path, "无EXIF数据"

            else:
                if DEBUG_MODE:
                    print(f"   ⚠️ 跳过不支持的文件类型: {filename}")
                return None, gps_coord

        except Exception as e:
            if DEBUG_MODE:
                print(f"   ❌ 文件处理失败: {str(e)}")
            return None, gps_coord

    @staticmethod
    def _process_heic(source_path, target_folder):
        """处理HEIC文件，保留EXIF"""
        try:
            register_heif_opener()

            filename = os.path.basename(source_path)
            jpg_filename = os.path.splitext(filename)[0] + '.jpg'
            target_path = os.path.join(target_folder, jpg_filename)

            # 打开HEIC文件
            with Image.open(source_path) as img:
                # 获取原始EXIF
                exif_data = None
                try:
                    exif_bytes = img.info.get('exif', b'')
                    if exif_bytes:
                        exif_data = exif_bytes
                except:
                    pass

                # 保存为JPG
                save_kwargs = {"quality": 95, "optimize": True}
                if exif_data:
                    save_kwargs["exif"] = exif_data

                img.save(target_path, "JPEG", **save_kwargs)

            if DEBUG_MODE:
                print(f"   ✅ HEIC转换成功: {jpg_filename}")
            return target_path

        except Exception as e:
            if DEBUG_MODE:
                print(f"   ❌ HEIC转换失败: {str(e)}")

            # 备用方案：使用系统工具
            try:
                jpg_filename = os.path.splitext(os.path.basename(source_path))[0] + '.jpg'
                target_path = os.path.join(target_folder, jpg_filename)

                # 使用PowerShell转换（Windows）
                cmd = f'''
                Add-Type -AssemblyName System.Drawing
                $img = [System.Drawing.Image]::FromFile("{source_path}")
                $img.Save("{target_path}", [System.Drawing.Imaging.ImageFormat]::Jpeg)
                $img.Dispose()
                '''
                subprocess.run(['powershell', '-Command', cmd],
                               capture_output=True, text=True, timeout=30)

                if os.path.exists(target_path):
                    if DEBUG_MODE:
                        print(f"   ✅ 备用HEIC转换成功: {jpg_filename}")
                    return target_path
            except Exception as e2:
                if DEBUG_MODE:
                    print(f"   ❌ 备用HEIC转换失败: {str(e2)}")

            return None

    @staticmethod
    def _process_jpg(source_path, target_folder):
        """处理JPG文件，确保EXIF保留"""
        try:
            filename = os.path.basename(source_path)
            target_path = os.path.join(target_folder, filename)

            # 方法1：使用piexif复制（最可靠）
            try:
                # 复制文件
                shutil.copy2(source_path, target_path)

                # 验证并修复EXIF
                exif_dict = piexif.load(source_path)
                piexif.insert(piexif.dump(exif_dict), target_path)

                if DEBUG_MODE:
                    print(f"   ✅ JPG处理成功 (piexif): {filename}")
                return target_path
            except:
                # 方法2：使用PIL
                with Image.open(source_path) as img:
                    exif_data = img.info.get('exif', b'')
                    img.save(target_path, "JPEG", quality=95, exif=exif_data)

                if DEBUG_MODE:
                    print(f"   ✅ JPG处理成功 (PIL): {filename}")
                return target_path

        except Exception as e:
            if DEBUG_MODE:
                print(f"   ❌ JPG处理失败: {str(e)}")
            return None

    @staticmethod
    def _inject_gps_data(source_path, target_path):
        """重新注入GPS数据到目标文件"""
        try:
            # 从源文件提取GPS
            source_exif = piexif.load(source_path)
            gps_ifd = source_exif.get("GPS", {})

            if gps_ifd:
                # 加载目标文件EXIF
                target_exif = piexif.load(target_path)
                target_exif["GPS"] = gps_ifd

                # 重新插入EXIF
                exif_bytes = piexif.dump(target_exif)
                piexif.insert(exif_bytes, target_path)

                if DEBUG_MODE:
                    print("   ✅ GPS数据重新注入成功")
                return True
        except Exception as e:
            if DEBUG_MODE:
                print(f"   ❌ GPS注入失败: {str(e)}")
        return False


# ====================== 图片预处理（核心修复） ======================
def prepare_images(source_folder, target_folder):
    """预处理图片，确保GPS数据不丢失"""
    print("\n" + "=" * 60)
    print("🚀 阶段1: 智能图片预处理")
    print("=" * 60)

    # 创建目标文件夹
    os.makedirs(target_folder, exist_ok=True)
    print(f"📁 创建目标文件夹: {target_folder}")

    # 获取所有文件
    all_files = []
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            all_files.append(os.path.join(root, file))

    print(f"🔍 扫描到 {len(all_files)} 个文件")

    processed_files = []
    gps_results = []
    error_count = 0

    for i, file_path in enumerate(all_files, 1):
        filename = os.path.basename(file_path)
        print(f"\n[{i}/{len(all_files)}] 处理: {filename}")

        # 智能处理文件
        result_path, gps_coord = FileProcessor.process_file(file_path, target_folder)

        if result_path and os.path.exists(result_path):
            processed_files.append(result_path)
            gps_results.append({
                "原文件名": filename,
                "处理后文件": os.path.basename(result_path),
                "GPS坐标": gps_coord,
                "状态": "成功"
            })
            print(f"  ✅ 处理成功: {os.path.basename(result_path)}")
            print(f"  📍 最终GPS: {gps_coord}")
        else:
            error_count += 1
            gps_results.append({
                "原文件名": filename,
                "处理后文件": "无",
                "GPS坐标": gps_coord,
                "状态": "失败"
            })
            print(f"  ❌ 处理失败: {filename}")

    # 生成详细报告
    print("\n" + "=" * 60)
    print("📊 预处理结果报告")
    print("=" * 60)

    success_count = len(processed_files)
    print(f"✅ 成功处理: {success_count} 个文件")
    print(f"❌ 处理失败: {error_count} 个文件")

    # GPS统计
    gps_success = sum(1 for r in gps_results if r["GPS坐标"] != "GPS数据缺失" and "无EXIF" not in r["GPS坐标"])
    print(f"📍 GPS提取成功: {gps_success} 个")
    print(f"📍 GPS提取失败: {len(gps_results) - gps_success} 个")

    if DEBUG_MODE:
        print("\n🔍 详细GPS结果:")
        for result in gps_results:
            status = "✅" if result["状态"] == "成功" else "❌"
            gps_status = "🎯" if "缺失" not in result["GPS坐标"] else "❌"
            print(f"{status} {result['原文件名']} → {result['处理后文件']}")
            print(f"   {gps_status} GPS: {result['GPS坐标']}")

    print(f"\n📂 预处理完成! 处理文件夹: {target_folder}")
    return target_folder, gps_results


# ====================== 完整系统提示词 (30个维度) ======================
SYSTEM_PROMPT = """你是一位城市科学研究专家。请依据输入的街景图像，输出可供后续感知评价使用的学术化描述文本。

要求：
1. 采用学术且专业的表达方式，引用城市规划和社会学关键术语。
2. 使用正式、严谨的语气，注重逻辑与条理性。
3. 所有输出必须完全使用中文，包括JSON字段名称。
4. 描述要具体、详细，避免笼统的表述。
5. 基于图像内容进行客观分析，不要添加个人主观臆断。

请从以下30个维度进行深入分析并以中文JSON格式输出：

1. 视觉多样性：分析场景中建筑风格、色彩、材质、形态的多样性程度，以及这种多样性对城市景观丰富性的影响。
2. 空间开阔度：评估街道宽度、建筑高度比例、天空视野占比，判断空间的开敞或压抑感。
3. 空间整洁度：观察地面清洁度、垃圾处理情况、墙面涂鸦、电线杂乱程度等，评价环境维护水平。
4. 景观特色度：识别具有地域特色或文化标识的景观元素，如特色建筑、雕塑、植被配置等。
5. 美感评价：从美学角度评价整体构图、色彩搭配、光影效果、比例协调性等审美价值。
6. 绿化覆盖率：估算植被（树木、灌木、草坪、垂直绿化）占画面面积的比例，评估生态效益。
7. 植物健康度：观察植物的生长状态、叶片颜色、病虫害情况，评价绿化养护质量。
8. 水体可见度：识别喷泉、水池、河流等水体元素的存在及其视觉显著性。
9. 生态廊道连通性：分析绿地、水体等生态要素的空间连续性和连接性，评价生态网络完整性。
10. 自然舒适感：综合评估自然元素（阳光、绿植、水体）对心理舒适度的贡献。
11. 污染可见度：识别空气污染（雾霾）、水体污染、垃圾堆积、油污等环境污染迹象。
12. 噪音干扰度：通过视觉线索（如隔音屏障、车流密度）推断噪音污染程度。
13. 热岛效应迹象：观察硬质铺装比例、遮荫不足、缺乏水体等可能加剧热岛效应的因素。
14. 海绵城市元素：识别透水铺装、雨水花园、植草沟、蓄水设施等海绵城市技术应用。
15. 负面情绪度：评估环境因素（拥挤、破败、污染）可能引发的负面心理感受。
16. 交通可达性：分析道路网络密度、人行道连续性、过街设施等对步行和非机动车的友好度。
17. 交通秩序度：观察车辆停放秩序、交通标识清晰度、人车分流情况、违规行为等。
18. 社会与空间公平：评估公共空间分布、设施可及性、不同群体使用机会的公平性。
19. 休憩与交往空间：识别座椅、凉亭、广场等促进人际交往的公共空间及其使用状况。
20. 无障碍设施：观察盲道、坡道、扶手等无障碍设施的完善程度和维护状况。
21. 商业多样性：分析店铺类型、商品服务种类的丰富程度，评价商业活力。
22. 街道繁荣度：评估人流密度、商业活跃度、街道生活气息的浓厚程度。
23. 摊贩活动：观察街头摊贩的存在形式、管理状况、对街道活力的贡献。
24. 商业环境：评价商业界面（橱窗、招牌、外摆）的设计质量和协调性。
25. 经济活力：通过店铺入驻率、新旧程度、消费档次等推断区域经济状况。
26. 文化符号：识别具有文化意义的符号、图案、色彩、建筑元素等。
27. 历史文脉：观察历史建筑、传统材料、文化遗迹等历史元素的保存和利用状况。
28. 公共艺术：识别雕塑、壁画、装置艺术等公共艺术作品的存在和质量。
29. 社区归属感：通过邻里互动空间、社区标识、居民活动等推断社区凝聚力。
30. 多元文化融合度：观察不同文化背景的商业、装饰、人群等共存状况。

输出格式（必须严格遵守，只输出JSON，不要有其他废话）：
{
"视觉多样性": "详细的描述...",
"空间开阔度": "详细的描述...",
...
"多元文化融合度": "详细的描述..."
}
"""


# ====================== 图像分析函数 ======================
def analyze_image(image_path):
    """分析单张图片并返回30个维度的结果"""
    print(f"  🤖 AI分析中: {os.path.basename(image_path)}")

    try:
        # 读取并压缩图片
        img = Image.open(image_path)

        # 调整大小（限制最大尺寸）
        max_size = 1024
        width, height = img.size
        if width > max_size or height > max_size:
            ratio = min(max_size / width, max_size / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # 转为Base64
        output_buffer = io.BytesIO()
        img.save(output_buffer, format='JPEG', quality=85)
        output_buffer.seek(0)

        img_bytes = output_buffer.getvalue()
        base64_image = base64.b64encode(img_bytes).decode('utf-8')
        image_data_uri = f"data:image/jpeg;base64,{base64_image}"

        # 调用DashScope API
        response = dashscope.MultiModalConversation.call(
            model='qwen-vl-plus',
            api_key=API_KEY,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': [
                    {'image': image_data_uri},
                    {'text': '请根据30个维度分析这张街景图片。'}
                ]}
            ]
        )

        # 处理响应
        if response.status_code == 200:
            raw_content = response.output.choices[0].message.content

            # 处理不同格式的响应
            if isinstance(raw_content, dict):
                return raw_content
            elif isinstance(raw_content, list) and len(raw_content) > 0:
                content = raw_content[0]
                if isinstance(content, dict):
                    return content
                elif isinstance(content, str):
                    return json.loads(content)
            elif isinstance(raw_content, str):
                return json.loads(raw_content)

        return {"错误": f"API返回错误，状态码: {response.status_code}"}

    except Exception as e:
        error_msg = f"分析异常: {str(e)}"
        print(f"  ❌ {error_msg}")
        return {"错误": error_msg}


# ====================== 主程序 ======================
def main():
    print("=" * 70)
    print("🌆 城市街景智能分析系统 (GPS修复版)")
    print("=" * 70)
    print(f"⏰ 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 原始文件夹: {ROOT_FOLDER}")
    print(f"📁 处理文件夹: {PROCESSED_FOLDER}")
    print(f"📊 输出文件: {OUTPUT_EXCEL}")
    print(f"🐛 调试模式: {'开启' if DEBUG_MODE else '关闭'}")
    print("=" * 70)

    # 检查文件夹是否存在
    if not os.path.exists(ROOT_FOLDER):
        print(f"❌ 错误: 原始文件夹不存在: {ROOT_FOLDER}")
        print("💡 请修改ROOT_FOLDER变量为正确的路径")
        return

    # 阶段1：预处理图片（关键修复）
    analysis_folder, gps_results = prepare_images(ROOT_FOLDER, PROCESSED_FOLDER)

    if not gps_results:
        print("\n❌ 错误: 没有可分析的图片文件！")
        return

    # 阶段2：分析图片
    print("\n" + "=" * 60)
    print("🤖 阶段2: AI图像分析")
    print("=" * 60)

    all_results = []
    success_count = 0
    fail_count = 0

    # 获取所有处理后的文件
    processed_files = []
    for result in gps_results:
        if result["状态"] == "成功" and result["处理后文件"] != "无":
            file_path = os.path.join(analysis_folder, result["处理后文件"])
            if os.path.exists(file_path):
                processed_files.append((file_path, result["GPS坐标"], result["原文件名"]))

    print(f"🔍 发现 {len(processed_files)} 个可分析图片")

    # 逐个分析
    for i, (image_path, gps_coord, original_name) in enumerate(processed_files, 1):
        filename = os.path.basename(image_path)
        print(f"\n[{i}/{len(processed_files)}] 分析: {filename}")
        print(f"  📍 使用GPS: {gps_coord}")

        # AI分析
        ai_result = analyze_image(image_path)

        if "错误" in ai_result:
            fail_count += 1
        else:
            success_count += 1

        # 构建结果行
        result_row = {
            "编号": i,
            "GPS坐标": gps_coord,
            "原文件名": original_name,
            "处理后文件名": filename,
            "分析状态": "成功" if "错误" not in ai_result else "失败"
        }

        # 合并AI结果
        result_row.update(ai_result)
        all_results.append(result_row)

        # 防止API限流
        if i < len(processed_files):
            time.sleep(1.5)

    # 阶段3：保存结果
    print("\n" + "=" * 60)
    print("💾 阶段3: 保存分析结果")
    print("=" * 60)

    if all_results:
        # 创建DataFrame
        df = pd.DataFrame(all_results)

        # 调整列顺序
        fixed_cols = ["编号", "GPS坐标", "原文件名", "处理后文件名", "分析状态"]
        other_cols = [col for col in df.columns if col not in fixed_cols]
        df = df[fixed_cols + other_cols]

        # 保存Excel
        try:
            df.to_excel(OUTPUT_EXCEL, index=False)
            print(f"✅ 结果保存成功: {OUTPUT_EXCEL}")
            print(f"📊 分析统计: 成功 {success_count} 个，失败 {fail_count} 个")

            # 生成详细报告
            report_file = OUTPUT_EXCEL.replace('.xlsx', '_报告.txt')
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("=" * 50 + "\n")
                f.write("🌆 城市街景分析报告 (GPS修复版)\n")
                f.write("=" * 50 + "\n")
                f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"原始文件夹: {ROOT_FOLDER}\n")
                f.write(f"处理文件夹: {PROCESSED_FOLDER}\n")
                f.write(f"总文件数: {len(gps_results)}\n")
                f.write(f"成功处理: {len(processed_files)}\n")
                f.write(
                    f"GPS提取成功: {sum(1 for r in gps_results if r['GPS坐标'] != 'GPS数据缺失' and '无EXIF' not in r['GPS坐标'])}\n")
                f.write(f"AI分析成功: {success_count}\n")
                f.write(f"AI分析失败: {fail_count}\n")
                f.write(f"输出文件: {OUTPUT_EXCEL}\n")
                f.write("=" * 50 + "\n")
                f.write("\nGPS详细统计:\n")
                for result in gps_results:
                    f.write(f"- {result['原文件名']}: {result['GPS坐标']} ({result['状态']})\n")
            print(f"✅ 详细报告: {report_file}")

        except Exception as e:
            print(f"❌ 保存Excel失败: {str(e)}")
            print("💡 建议: 关闭所有Excel文件后重试")
    else:
        print("❌ 没有分析结果可保存！")

    print("\n" + "=" * 70)
    print(f"🎉 分析完成! 总耗时: {time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}")
    print("=" * 70)


if __name__ == "__main__":
    start_time = time.time()

    # 设置环境
    setup_environment()


    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ 严重错误: {str(e)}")
        print("📋 详细错误信息:")
        traceback.print_exc()
        sys.exit(1)