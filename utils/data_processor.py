import pandas as pd
import json
import os
import re # 用于后续的正则提取

# 定义文件路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # 获取项目根目录
EXCEL_PATH = os.path.join(BASE_DIR, "择校文档.xlsx")
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "data", "schools.json")
DATA_DIR = os.path.join(BASE_DIR, "data")

# --- 省份和城市数据 ---
VALID_PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", 
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", 
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州", 
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "台湾",
    "香港", "澳门" 
]

CITY_TO_PROVINCE = {
    "哈尔滨": "黑龙江",
    "长春": "吉林", "延吉": "吉林",
    "沈阳": "辽宁", "大连": "辽宁",
    "呼和浩特": "内蒙古",
    "石家庄": "河北", "保定": "河北", "唐山": "河北", "秦皇岛": "河北", "邯郸": "河北",
    "太原": "山西",
    "济南": "山东", "青岛": "山东",
    "郑州": "河南", "焦作": "河南",
    "合肥": "安徽", "淮南": "安徽", "马鞍山": "安徽",
    "南京": "江苏", "徐州": "江苏", "镇江": "江苏", "无锡": "江苏", "南通": "江苏",
    "杭州": "浙江", "金华": "浙江",
    "福州": "福建", "厦门": "福建", "泉州": "福建", "汕头": "福建",
    "南昌": "江西",
    "武汉": "湖北", "宜昌": "湖北",
    "长沙": "湖南", "湘潭": "湖南",
    "广州": "广东", "深圳": "广东", "汕头": "广东",
    "南宁": "广西", "桂林": "广西", "柳州": "广西",
    "海口": "海南",
    "成都": "四川",
    "贵阳": "贵州",
    "昆明": "云南",
    "拉萨": "西藏",
    "西安": "陕西", "延安": "陕西",
    "兰州": "甘肃",
    "西宁": "青海",
    "银川": "宁夏",
    "乌鲁木齐": "新疆",
}

def is_valid_province(name):
    """检查是否为有效的省份/直辖市/自治区名称。"""
    return isinstance(name, str) and name in VALID_PROVINCES

def extract_province_from_string(text):
    """尝试从文本中提取第一个出现的有效省份名称。"""
    if not isinstance(text, str) or not text:
        return None
    # 优先匹配较长的省份名称，例如 "黑龙江" 优先于 "江"
    sorted_provinces = sorted(VALID_PROVINCES, key=len, reverse=True)
    for province in sorted_provinces:
        if province in text:
            return province
    return None

def extract_province_smart(row, school_name_raw, intro_raw, sheet_name_for_province_extraction):
    """智能提取省份，按优先级：列 -> 名称 -> 简介 -> 工作表名。"""
    school_name = str(school_name_raw) if pd.notna(school_name_raw) else ''
    intro = str(intro_raw) if pd.notna(intro_raw) else ''
    
    # 1. 尝试从 '省份' 列获取并验证
    province_from_col = row.get('省份')
    if pd.notna(province_from_col):
        province_str = str(province_from_col).strip()
        if is_valid_province(province_str):
            # print(f"    提取自列: {province_str}")
            return province_str

    # 2. 尝试从学校名称提取
    # 2.1 查找括号内的城市/省份
    match = re.search(r'[（(](.+?)[)）]', school_name)
    if match:
        location = match.group(1).strip()
        if is_valid_province(location):
            # print(f"    提取自名称(括号内省份): {location}")
            return location
        if location in CITY_TO_PROVINCE:
            province_mapped = CITY_TO_PROVINCE[location]
            # print(f"    提取自名称(括号内城市 {location}): {province_mapped}")
            return province_mapped

    # 2.2 检查学校名称是否以已知城市开头
    for city, province_of_city in CITY_TO_PROVINCE.items():
        if school_name.startswith(city):
            # print(f"    提取自名称(城市前缀 {city}): {province_of_city}")
            return province_of_city

    # 2.3 直接在名称中查找省份关键字
    province_from_name = extract_province_from_string(school_name)
    if province_from_name:
        # print(f"    提取自名称(关键字): {province_from_name}")
        return province_from_name
        
    # 3. 尝试从简介提取
    province_from_intro = extract_province_from_string(intro)
    if province_from_intro:
        # print(f"    提取自简介: {province_from_intro}")
        return province_from_intro

    # 4. 尝试使用工作表名称 (作为较低优先级)
    if sheet_name_for_province_extraction and is_valid_province(str(sheet_name_for_province_extraction).strip()):
        # print(f"    提取自工作表名称: {str(sheet_name_for_province_extraction).strip()}")
        return str(sheet_name_for_province_extraction).strip()

    # 5. 无法提取，返回 None
    # print(f"    未能提取省份 for {school_name} from any source.")
    return None

def clean_column_names(df):
    """清理DataFrame的列名，去除首尾空格。"""
    df.columns = df.columns.str.strip()
    return df

def extract_school_level(name_str):
    """尝试从院校名称字符串中提取等级信息。"""
    if isinstance(name_str, str):
        if "985" in name_str:
            return "985"
        if "211" in name_str:
            return "211"
        # 可以根据需要添加更多规则，例如 "双一流"
    return "一般" # 默认等级

# 新增辅助函数：动态查找表头行
def find_header_row(df_peek, keywords):
    """
    分析DataFrame的前几行，找到最可能包含表头关键字的行。
    :param df_peek: DataFrame，通常是工作表的前N行，header=None读取。
    :param keywords: list of str，用于匹配表头的关键字（不区分大小写）。
    :return: 0-based index of the best header row, or -1 if no suitable row found.
    """
    best_header_index = -1
    max_matches = 0
    
    if df_peek.empty:
        return -1

    # 至少需要匹配到的关键字数量
    MIN_KEYWORD_MATCHES = 2 

    for i in range(len(df_peek)):
        current_matches = 0
        try:
            # 将行内容转换为小写字符串列表进行比较
            row_values = [str(cell).strip().lower() for cell in df_peek.iloc[i].tolist()]
        except Exception:
            # 如果某行无法转换（例如完全是奇怪的类型），跳过这一行
            continue
            
        for keyword in keywords:
            # 检查关键字是否作为子字符串存在于任何单元格值中
            if any(keyword.lower() in cell_value for cell_value in row_values):
                current_matches += 1
        
        if current_matches > max_matches and current_matches >= MIN_KEYWORD_MATCHES:
            max_matches = current_matches
            best_header_index = i
            
    return best_header_index

def process_excel_data(excel_path, output_json_path):
    """读取Excel文件，处理数据，并输出为JSON。"""
    try:
        xls = pd.ExcelFile(excel_path)
    except FileNotFoundError:
        print(f"错误: Excel 文件未找到于 '{excel_path}'")
        return
    except Exception as e:
        print(f"读取 Excel 文件时出错: {e}")
        return

    all_schools_data = {}
    # first_sheet_processed = False # 不再需要这个标志位

    print("开始处理 Excel 文件...")
    # 定义用于表头检测的关键字
    header_keywords = ['学校', '代码', '专业', '院系', '科目', '名称', '招生', '录取', '复试', '考试']


    for sheet_name in xls.sheet_names:
        print(f"  正在处理工作表: {sheet_name}...")
        actual_major_code_col = None # 用于存储实际的专业代码列名
        actual_school_name_col = None # 用于存储实际的学校名称列名
        
        try:
            # 1. 动态表头检测
            df_peek = pd.read_excel(xls, sheet_name=sheet_name, nrows=15, header=None)
            identified_header_idx = find_header_row(df_peek, header_keywords)

            if identified_header_idx != -1:
                print(f"    工作表 '{sheet_name}': 动态识别到表头可能在第 {identified_header_idx + 1} 行。")
                df = pd.read_excel(xls, sheet_name=sheet_name, header=identified_header_idx)
            else:
                print(f"    工作表 '{sheet_name}': 未能动态识别表头，尝试使用默认表头行 5 (0-indexed 4)。")
                # 尝试使用之前的默认值 header=4 (即Excel中的第5行)
                df = pd.read_excel(xls, sheet_name=sheet_name, header=4)
            
            df = clean_column_names(df) # 清理列名中的空格
            # 重命名列名中的 '.1' 等后缀 (例如 '23拟录取情况.1'), 并再次去除可能产生的空格
            df.columns = [re.sub(r'\.\d+$', '', col).strip() for col in df.columns]
            
            print(f"    工作表 '{sheet_name}' 清理后的列名: {list(df.columns)}")

            # 2. 定位 '专业代码' 列
            possible_major_code_names = ['专业代码'] # 可以扩展更多可能的名称
            for name_variant in possible_major_code_names:
                if name_variant in df.columns:
                    actual_major_code_col = name_variant
                    break
            
            if actual_major_code_col is None:
                print(f"    警告: 工作表 '{sheet_name}' 中未找到 '专业代码' 列。跳过此工作表。")
                continue
            else:
                print(f"    使用 '{actual_major_code_col}' 作为专业代码列。")

            # 2.a 定位学校名称列
            possible_school_name_cols = ['学校名称', '院校名称', '院校'] 
            for name_variant in possible_school_name_cols:
                if name_variant in df.columns:
                    actual_school_name_col = name_variant
                    print(f"    使用 '{actual_school_name_col}' 作为学校名称列。")
                    break
            
            if actual_school_name_col is None:
                print(f"    严重警告: 工作表 '{sheet_name}' 中未找到任何可识别的学校名称列 (尝试过: {possible_school_name_cols})。清理后的列为: {list(df.columns)}。跳过此工作表。")
                continue

            # 2.b 向前填充学校名称列以处理合并单元格
            # print(f"    对学校名称列 '{actual_school_name_col}' 进行向前填充 (ffill)...") # 可以取消注释以获取更详细的日志
            df[actual_school_name_col] = df[actual_school_name_col].ffill()
            # print(f"    学校名称列 '{actual_school_name_col}' 向前填充完成。")


            # 删除专业代码列完全为空的行
            df.dropna(subset=[actual_major_code_col], how='all', inplace=True)
            df.reset_index(drop=True, inplace=True) # 重置索引

            # --- 诊断代码：打印第一个工作表的列名 ---
            # if not first_sheet_processed:
            #     print(f"    检测到 '{sheet_name}' 的列名: {list(df.columns)}")
            #     first_sheet_processed = True
            # --- 诊断代码结束 ---

            # 删除专业代码列完全为空的行，这些通常是无效数据或分隔行
            # 这部分逻辑已上移并使用了 actual_major_code_col

            # 重命名列名中的 '.1' 等后缀 (例如 '23拟录取情况.1')
            # 这部分逻辑已上移

            # --- 数据清洗和转换 ---
            # 1. 删除完全为空的行
            df.dropna(how='all', inplace=True)
            if df.empty:
                print(f"    工作表 '{sheet_name}' 为空或只包含空行，跳过。")
                continue

            # 2. 处理每一行数据
            for index, row in df.iterrows():
                school_name_raw = row.get(actual_school_name_col) # 使用 ffill 处理后的学校名称列
                intro_raw = row.get('简介')
                # province_col_raw = row.get('省份') # 获取省份列原始值 (暂时不修改省份提取逻辑)

                # 处理学校名称合并单元格 - ffill 已处理，简化此部分
                # current_school_name_raw = school_name_raw
                # if pd.isna(current_school_name_raw) and index > 0:
                #     prev_raw_name = df.loc[index-1].get(actual_school_name_col) # 使用实际学校名称列
                #     current_school_name_raw = prev_raw_name if pd.notna(prev_raw_name) else None

                if pd.isna(school_name_raw): # 直接检查 ffill后的值
                     print(f"    跳过行 (原始Excel行号未知，DataFrame index {index}): 学校名称在列 '{actual_school_name_col}' 中为空或无效。") 
                     continue
                
                current_school_name_raw = school_name_raw # 确保 current_school_name_raw 被赋值

                school_name_cleaned = str(current_school_name_raw).split('\\n')[0].strip()
                school_level = extract_school_level(str(current_school_name_raw))

                province = extract_province_smart(row, current_school_name_raw, intro_raw, sheet_name) # 传入 sheet_name

                major_code_raw = row.get(actual_major_code_col, '') # 使用实际识别的专业代码列名
                major_code_str = str(major_code_raw).strip() if pd.notna(major_code_raw) else ''
                major_name = row.get('专业名称', '').strip() if pd.notna(row.get('专业名称')) else ''

                # 清理学校名称，去除可能存在的换行符和等级信息
                # school_name_cleaned = str(school_name_cleaned).split('\\n')[0].strip() # 已在上文处理
                # school_level = extract_school_level(str(school_name_cleaned)) # 已在上文处理

                if school_name_cleaned not in all_schools_data:
                    all_schools_data[school_name_cleaned] = {
                        "id": school_name_cleaned, # 使用清理后的名称作为ID
                        "name": school_name_cleaned,
                        "level": school_level,
                        "province": province if province else "未知省份", # 使用提取到的省份, 确保不是 None
                        "intro": str(intro_raw).strip() if pd.notna(intro_raw) else None,
                        "computer_rank": None, # 初始化，将在下面填充
                        "self_vs_408": "待判断", # 需要逻辑来判断是自命题还是408
                        "departments": {}, # 使用字典存储院系，方便合并专业, key为院系名称
                        "favorites_count": 0
                    }
                
                # 填充或更新 computer_rank (兼容 '计算机等级' 和 '计算机评级')
                computer_rank_val = row.get('计算机等级') or row.get('计算机评级')
                if pd.notna(computer_rank_val):
                    all_schools_data[school_name_cleaned]['computer_rank'] = str(computer_rank_val).strip()
                elif all_schools_data[school_name_cleaned]['computer_rank'] is None: # 如果之前没有设置过，则保持为 None
                    all_schools_data[school_name_cleaned]['computer_rank'] = None
                    
                # 获取或创建院系信息
                department_name = row.get('招生院系', '未知院系')
                if pd.isna(department_name): department_name = '未知院系'

                school_entry = all_schools_data[school_name_cleaned]
                if department_name not in school_entry['departments']:
                     school_entry['departments'][department_name] = {
                         "department_name": department_name,
                         "majors": [] # 专业列表
                     }

                # 提取专业信息
                if not major_code_str: # 专业代码是核心信息，如果为空字符串 (之前是 pd.isna(major_code_str) )
                    # print(f"    跳过专业：专业代码为空。学校: {school_name_cleaned}, 院系: {department_name}")
                    continue

                # 处理多行文本字段
                def get_multiline_str(value):
                    # 检查输入是否为 Series，如果是，取第一个元素
                    if isinstance(value, pd.Series):
                        value = value.iloc[0] if not value.empty else None
                    return str(value).replace('\r\n', '\n').strip() if not pd.isna(value) else None

                # 明确处理可能重复的列，优先获取第一个
                admission_23 = row.get('23拟录取情况')
                admission_24 = row.get('24拟录取情况') or row.get('24拟录取名单') or row.get('24复试名单')

                major_info = {
                    "major_code": major_code_str,
                    "major_name": major_name,
                    "exam_subjects": get_multiline_str(row.get('初试科目')),
                    "reference_books": get_multiline_str(row.get('参考书')),
                    "retrial_subjects": get_multiline_str(row.get('复试科目')),
                    "enrollment_24": pd.to_numeric(row.get('24招生人数'), errors='coerce'),
                    "tuition_duration": get_multiline_str(row.get('学费学制')),
                    "score_lines": {
                        "2024": get_multiline_str(row.get('24复试线')),
                        "2023": get_multiline_str(row.get('23复试线'))
                    },
                    "admission_info_23": get_multiline_str(admission_23),
                    "admission_info_24": get_multiline_str(admission_24)
                }

                # 专业的专业名称提取逻辑
                exam_subjects_str = str(major_info['exam_subjects'])
                code_str = major_info['major_code']
                name_str = major_info['major_name']
                
                if '计算机科学与技术' in exam_subjects_str or ('081200' in code_str and '计算机科学与技术' not in code_str):
                    major_info['major_name'] = '计算机科学与技术'
                elif '软件工程' in exam_subjects_str or ('083500' in code_str or '085405' in code_str) and '软件工程' not in code_str:
                    major_info['major_name'] = '软件工程'
                elif '计算机技术' in exam_subjects_str or ('085404' in code_str or '085400' in code_str) and '计算机技术' not in code_str:
                    major_info['major_name'] = '计算机技术'
                elif '人工智能' in exam_subjects_str or ('085410' in code_str) and '人工智能' not in code_str:
                    major_info['major_name'] = '人工智能'
                elif '大数据技术与工程' in exam_subjects_str or ('085411' in code_str) and '大数据技术与工程' not in code_str:
                    major_info['major_name'] = '大数据技术与工程'
                elif '网络空间安全' in exam_subjects_str or ('083900' in code_str) and '网络空间安全' not in code_str:
                    major_info['major_name'] = '网络空间安全'
                elif not name_str or name_str == '-' or name_str == '未知专业': # 仅当原始名称无效时设为未知
                    major_info['major_name'] = '未知专业'
                # else: 保持原始专业名称

                # 将专业信息添加到对应院系的majors列表
                school_entry['departments'][department_name]['majors'].append(major_info)

            print(f"工作表 '{sheet_name}' 处理完成。")

        except Exception as e:
            print(f"处理工作表 '{sheet_name}' 时发生错误: {e}")
            import traceback
            traceback.print_exc() # 打印详细错误堆栈


    # --- 后处理和输出 ---
    # 将字典转换为最终的列表格式
    final_school_list = []
    for school_data in all_schools_data.values():
        # 将院系字典转换为列表
        school_data['departments'] = list(school_data['departments'].values())
        final_school_list.append(school_data)

    # 递归函数：将 NaN 替换为 None
    def replace_nan_with_none(obj):
        if isinstance(obj, list):
            return [replace_nan_with_none(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: replace_nan_with_none(value) for key, value in obj.items()}
        elif isinstance(obj, float) and pd.isna(obj):
            return None
        else:
            return obj

    # 清理最终列表中的 NaN 值
    cleaned_school_list = replace_nan_with_none(final_school_list)


    # 创建 data 目录（如果不存在）
    os.makedirs(DATA_DIR, exist_ok=True)

    # 将结果写入 JSON 文件
    try:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_school_list, f, ensure_ascii=False, indent=2) # 使用清理后的列表
        print(f"\n成功将处理后的数据写入到: {output_json_path}")
    except IOError as e:
        print(f"写入 JSON 文件时出错: {e}")
    except Exception as e:
        print(f"转换或写入 JSON 时发生未知错误: {e}")


if __name__ == "__main__":
    process_excel_data(EXCEL_PATH, OUTPUT_JSON_PATH) 