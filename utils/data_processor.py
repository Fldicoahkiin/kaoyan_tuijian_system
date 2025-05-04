import pandas as pd
import json
import os
import re # 用于后续的正则提取

# 定义文件路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # 获取项目根目录
EXCEL_PATH = os.path.join(BASE_DIR, "择校文档.xlsx")
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "data", "schools.json")
DATA_DIR = os.path.join(BASE_DIR, "data")

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

def get_region(province):
    """根据省份（工作表名）判断A/B区。"""
    # 注意：这个映射关系需要根据实际情况确认和完善
    b_zone_provinces = ["B区"] # 假设只有'B区'工作表属于B区
    if province in b_zone_provinces:
        return "B区"
    else:
        # 默认为A区，但可能需要更精确的省份列表
        # 例如：北京、天津、河北、山西、辽宁、吉林、黑龙江、上海、江苏、
        # 浙江、安徽、福建、江西、山东、河南、湖北、湖南、广东、重庆、
        # 四川、陕西等属于A区
        # 内蒙古、广西、海南、贵州、云南、西藏、甘肃、青海、宁夏、新疆属于B区
        # Sheet1 比较特殊，需要看里面的学校具体属于哪个省份
        return "A区" # 暂时默认非B区的都为A区

def process_excel_data(excel_path, output_json_path):
    """读取Excel文件，处理数据，并输出为JSON。"""
    try:
        excel_file = pd.ExcelFile(excel_path)
    except FileNotFoundError:
        print(f"错误：未找到 Excel 文件: {excel_path}")
        return

    all_schools_dict = {} # 使用字典存储学校，方便合并专业信息，key为学校名称

    sheet_names = excel_file.sheet_names
    print(f"开始处理 Excel 文件，包含工作表: {sheet_names}")

    for sheet_name in sheet_names:
        print(f"\n--- 正在处理工作表: {sheet_name} ---")
        try:
            df = excel_file.parse(sheet_name)
            df = clean_column_names(df)

            # 重命名列名中的 '.1' 等后缀 (例如 '23拟录取情况.1')
            df.columns = [re.sub(r'\.\d+$', '', col) for col in df.columns]

            # --- 数据清洗和转换 ---
            # 1. 删除完全为空的行
            df.dropna(how='all', inplace=True)
            if df.empty:
                print(f"工作表 '{sheet_name}' 为空或只包含空行，跳过。")
                continue

            # 2. 处理每一行数据
            for index, row in df.iterrows():
                school_name_raw = row.get('院校名称') # Sheet1 用 '院校名称'，其他用 '院校'
                if pd.isna(school_name_raw):
                    school_name_raw = row.get('院校') # 尝试获取 '院校' 列

                if pd.isna(school_name_raw):
                    # 如果关键的学校名称为空，可能不是有效数据行，跳过
                    # 或者，这行可能是属于上一行的某个专业的附加信息，需要后续处理
                    continue

                # 清理学校名称，去除可能存在的换行符和等级信息
                school_name_cleaned = str(school_name_raw).split('\n')[0].strip()
                school_level = extract_school_level(str(school_name_raw))
                province = sheet_name # 以工作表名作为省份依据
                region = get_region(province)

                # 如果学校还不在字典中，创建学校基本信息
                if school_name_cleaned not in all_schools_dict:
                    all_schools_dict[school_name_cleaned] = {
                        "id": school_name_cleaned, # 使用清理后的名称作为ID
                        "name": school_name_cleaned,
                        "level": school_level,
                        "region": region,
                        "province": province if province != 'Sheet1' else None, # Sheet1 的省份需要额外判断
                        "intro": row.get('院校简介', ''), # 处理可能不存在的列
                        "computer_rank": row.get('计算机评级', '无'),
                        "self_vs_408": "待判断", # 需要逻辑来判断是自命题还是408
                        "departments": {}, # 使用字典存储院系，方便合并专业, key为院系名称
                        "favorites_count": 0
                    }
                
                # 获取或创建院系信息
                department_name = row.get('招生院系', '未知院系')
                if pd.isna(department_name): department_name = '未知院系'

                school_entry = all_schools_dict[school_name_cleaned]
                if department_name not in school_entry['departments']:
                     school_entry['departments'][department_name] = {
                         "department_name": department_name,
                         "majors": [] # 专业列表
                     }

                # 提取专业信息
                major_code = row.get('专业代码')
                if pd.isna(major_code): continue # 专业代码是核心信息，为空则跳过此行

                # 处理多行文本字段
                def get_multiline_str(value):
                    # 检查输入是否为 Series，如果是，取第一个元素
                    if isinstance(value, pd.Series):
                        value = value.iloc[0] if not value.empty else None
                    return str(value).replace('\r\n', '\n') if not pd.isna(value) else None

                # 明确处理可能重复的列，优先获取第一个
                admission_23 = row.get('23拟录取情况')
                admission_24 = row.get('24拟录取情况') or row.get('24拟录取名单') or row.get('24复试名单')

                major_info = {
                    "major_code": str(major_code).strip(),
                    "major_name": "待提取", # 需要从专业代码或其他列提取
                    "exam_subjects": get_multiline_str(row.get('初试科目')),
                    "reference_books": get_multiline_str(row.get('参考书')),
                    "retrial_subjects": get_multiline_str(row.get('复试科目')),
                    "enrollment_24": pd.to_numeric(row.get('24招生人数'), errors='coerce'), # 转换为数字，失败则为NaN
                    "tuition_duration": get_multiline_str(row.get('学费学制')),
                    "score_lines": {
                        "2024": get_multiline_str(row.get('24复试线')),
                        "2023": get_multiline_str(row.get('23复试线')) # 部分sheet有23复试线
                    },
                    "admission_info_23": get_multiline_str(admission_23), # 传入处理后的值
                    "admission_info_24": get_multiline_str(admission_24)  # 传入处理后的值
                }

                # 简单的专业名称提取逻辑（示例）
                if '计算机科学与技术' in major_info['exam_subjects'] or '081200' in major_info['major_code']:
                    major_info['major_name'] = '计算机科学与技术'
                elif '软件工程' in major_info['exam_subjects'] or '083500' in major_info['major_code'] or '085405' in major_info['major_code']:
                     major_info['major_name'] = '软件工程'
                elif '计算机技术' in major_info['exam_subjects'] or '085404' in major_info['major_code'] or '085400' in major_info['major_code']:
                     major_info['major_name'] = '计算机技术'
                elif '人工智能' in major_info['exam_subjects'] or '085410' in major_info['major_code']:
                     major_info['major_name'] = '人工智能'
                elif '大数据技术与工程' in major_info['exam_subjects'] or '085411' in major_info['major_code']:
                     major_info['major_name'] = '大数据技术与工程'
                elif '网络空间安全' in major_info['exam_subjects'] or '083900' in major_info['major_code']:
                     major_info['major_name'] = '网络空间安全'
                else:
                    major_info['major_name'] = '未知专业' # 可以留空或标记


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
    for school_data in all_schools_dict.values():
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