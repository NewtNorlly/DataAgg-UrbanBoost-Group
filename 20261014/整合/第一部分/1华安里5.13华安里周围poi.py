import requests
import pandas as pd
import time

def fetch_poi_data():
    # ====================== 配置参数 ======================
    AMAP_KEY = '088f005ad8207517ead7fa86b3192692'
    CENTER = '114.23752,30.61652'
    RADIUS = 1200

    TYPES = [
        '010000',  # 综合商场
        '020000',  # 住宅区
        '050000',  # 餐饮服务
        '060000',  # 购物服务
        '070000',  # 生活服务
        '080000',  # 体育休闲服务
        '090000',  # 医疗保健
        '110000',  # 教育学校
        '120000',  # 科教文化
        '100000',  # 交通设施
        '150000',  # 公用设施
        '160000',  # 风景名胜
        '170000',  # 公共厕所
        '130000',  # 政府机构
        '180000',  # 公司企业
        '200000',  # 建筑物
        '220000',  # 地名地址
        '230000'   # 道路交叉口
    ]

    # 建立大类代码 -> 类别名称的映射（用于统计输出）
    TYPE_NAMES = {
        '010000': '综合商场',
        '020000': '住宅区',
        '050000': '餐饮服务',
        '060000': '购物服务',
        '070000': '生活服务',
        '080000': '体育休闲服务',
        '090000': '医疗保健',
        '110000': '教育学校',
        '120000': '科教文化',
        '100000': '交通设施',
        '150000': '公用设施',
        '160000': '风景名胜',
        '170000': '公共厕所',
        '130000': '政府机构',
        '180000': '公司企业',
        '200000': '建筑物',
        '220000': '地名地址',
        '230000': '道路交叉口'
    }

    # ====================== 数据抓取逻辑 ======================
    all_pois = []
    base_url = "https://restapi.amap.com/v3/place/around"

    for poi_type in TYPES:
        page = 1
        while True:
            params = {
                'key': AMAP_KEY,
                'location': CENTER,
                'radius': RADIUS,
                'types': poi_type,
                'offset': 25,
                'page': page,
                'extensions': 'base'
            }

            try:
                response = requests.get(base_url, params=params)
                data = response.json()

                if data['status'] == '1' and int(data['count']) > 0:
                    pois = data['pois']
                    for poi in pois:
                        all_pois.append({
                            '名称': poi['name'],
                            '类型': poi['type'],
                            '类型代码': poi['typecode'],
                            '经度': poi['location'].split(',')[0],
                            '纬度': poi['location'].split(',')[1],
                            '地址': poi['address'],
                            '所在商圈': poi.get('business_area', '无'),
                            '距中心距离': poi['distance']
                        })
                    print(f"✅ 抓取成功: 类型 {poi_type} 第 {page} 页")

                    if len(pois) < 25:
                        break
                else:
                    print(f"❌ 无数据或错误: 类型 {poi_type} 错误码 {data.get('info', 'Unknown')}")
                    break

                page += 1
                time.sleep(0.5)

            except Exception as e:
                print(f"❌ 请求异常: {e}")
                break

    # ====================== 保存结果 ======================
    if all_pois:
        df = pd.DataFrame(all_pois)
        df.drop_duplicates(subset=['经度', '纬度'], inplace=True)

        output_file = '华安里_POI数据_供GIS分析.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n🎉 抓取完成！共获取 {len(df)} 个设施点。")
        print(f"📁 文件已保存为: {output_file}")

        # ============ 新增：按大类统计POI数量 ============
        # 高德分类代码为6位数字，前两位代表大类（例如 050100 属于 050000 餐饮）
        df['大类代码'] = df['类型代码'].str[:2] + '0000'

        # 统计每个大类的数量，并映射为中文类别名
        stats = df['大类代码'].value_counts().reset_index()
        stats.columns = ['大类代码', '数量']
        stats['类别名称'] = stats['大类代码'].map(TYPE_NAMES).fillna('其他类别')

        # 按数量降序排列
        stats = stats.sort_values('数量', ascending=False)

        # 打印统计表格
        print("\n📊 ========== 类别统计 ==========")
        print(f"{'类别名称':<12} {'大类代码':<10} {'数量':>5}")
        print("-" * 30)
        for _, row in stats.iterrows():
            print(f"{row['类别名称']:<12} {row['大类代码']:<10} {row['数量']:>5}")

        # 保存统计结果到CSV
        stats_file = '华安里_POI类别统计.csv'
        stats.to_csv(stats_file, index=False, encoding='utf-8-sig')
        print(f"\n📁 类别统计已保存为: {stats_file}")
        print("💡 下一步：打开ArcGIS/QGIS，导入POI数据CSV，即可进行核密度和缓冲区分析。")
        # ==============================================

    else:
        print("❌ 未获取到任何数据，请检查Key或网络连接。")


if __name__ == '__main__':
    fetch_poi_data()