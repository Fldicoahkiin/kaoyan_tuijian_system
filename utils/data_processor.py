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
        xls = pd.ExcelFile(excel_path)
    except FileNotFoundError:
        print(f"错误: Excel 文件未找到于 '{excel_path}'")
        return
    except Exception as e:
        print(f"读取 Excel 文件时出错: {e}")
        return

    all_schools_data = {}
    last_valid_school_name = None # Track last seen school name per sheet

    print("开始处理 Excel 文件...")
    for sheet_name in xls.sheet_names:
        print(f"  正在处理工作表: {sheet_name}...")
        last_valid_school_name = None # Reset for each new sheet
        try:
            # 尝试读取时跳过可能的空行或非数据行，假设表头在第5行 (0-based index 4)
            df = pd.read_excel(xls, sheet_name=sheet_name, header=0)
            df = clean_column_names(df)

            # 提取省份信息（优先从列获取，否则从工作表名获取）
            current_province = sheet_name # 默认使用工作表名作为省份
            if '省份' in df.columns:
                # 如果有省份列，尝试用第一个有效值覆盖默认值
                first_valid_province = df['省份'].dropna().iloc[0] if not df['省份'].dropna().empty else None
                if first_valid_province:
                    current_province = first_valid_province
                    print(f"    从 '省份' 列获取到省份: {current_province}")
                else:
                    print(f"    '省份' 列为空或无效，使用工作表名称 '{current_province}' 作为省份。")
            else:
                print(f"    未找到 '省份' 列，使用工作表名称 '{current_province}' 作为省份。")

            # 删除专业代码列完全为空的行，这些通常是无效数据或分隔行
            if '专业代码' in df.columns:
                df.dropna(subset=['专业代码'], how='all', inplace=True)
                # 重置索引，防止因删除行导致 loc 索引错误
                df.reset_index(drop=True, inplace=True)
            else:
                print(f"警告: 工作表 '{sheet_name}' 中缺少 '专业代码' 列，可能影响数据处理。")
                continue # 如果没有专业代码，跳过这个工作表

            # 重命名列名中的 '.1' 等后缀 (例如 '23拟录取情况.1')
            df.columns = [re.sub(r'\.\d+$', '', col) for col in df.columns]

            # --- 数据清洗和转换 ---
            # 移除专业代码和学校名称都为空的行，这些通常是完全的空行或分隔符
            if '专业代码' in df.columns and '学校名称' in df.columns:
                 df.dropna(subset=['专业代码', '学校名称'], how='all', inplace=True)
                 df.reset_index(drop=True, inplace=True)
            elif '专业代码' in df.columns: # 只有专业代码列
                 df.dropna(subset=['专业代码'], how='all', inplace=True)
                 df.reset_index(drop=True, inplace=True)
            elif '学校名称' in df.columns: # 只有学校名称列 (不太可能有效，但以防万一)
                 df.dropna(subset=['学校名称'], how='all', inplace=True)
                 df.reset_index(drop=True, inplace=True)
            else:
                print(f"警告: 工作表 '{sheet_name}' 缺少 '专业代码' 和 '学校名称' 列，跳过处理。")
                continue # If key columns missing, skip

            # 重命名列名中的 '.1' 等后缀
            df.columns = [re.sub(r'\.\d+$', '', col) for col in df.columns]

            # 1. 删除完全为空的行 (再次检查，以防万一)
            df.dropna(how='all', inplace=True)
            df.reset_index(drop=True, inplace=True) # Reset index again after potential drops
            if df.empty:
                print(f"    工作表 '{sheet_name}' 为空或只包含空行，跳过。")
                continue

            # 2. 处理每一行数据
            for index, row in df.iterrows():
                # --- 获取学校名称 ---
                current_school_name_raw = row.get('学校名称')
                current_school_name = str(current_school_name_raw).strip() if pd.notna(current_school_name_raw) else None

                # 如果当前行有学校名称，则更新 last_valid_school_name
                if current_school_name:
                    last_valid_school_name = current_school_name
                    # 清理名称，去除可能存在的换行符和等级信息
                    last_valid_school_name = str(last_valid_school_name).split('\\n')[0].strip()

                # 如果当前行没有学校名称，但我们已经记录了上一个有效的学校名称，则使用它
                school_name_to_use = last_valid_school_name

                if not school_name_to_use:
                    # print(f"      跳过行 {index+1}，因为无法确定学校名称。")
                    continue # 如果到这里还没有学校名称，无法处理，跳过

                # --- 获取专业信息 ---
                major_code_raw = row.get('专业代码', '')
                major_code_str = str(major_code_raw).strip() if pd.notna(major_code_raw) else ''
                major_name = row.get('专业名称', '').strip() if pd.notna(row.get('专业名称')) else ''

                # 专业代码是核心，如果为空，也跳过这行（这行可能是学校名称行或无效行）
                if not major_code_str:
                    # print(f"      跳过行 {index+1} (学校: {school_name_to_use})，因为专业代码为空。")
                    continue

                # --- 创建或更新学校条目 ---
                school_level = extract_school_level(str(school_name_to_use)) # Use tracked name
                region = get_region(current_province)

                if school_name_to_use not in all_schools_data:
                    # print(f"    发现新学校: {school_name_to_use}")
                    all_schools_data[school_name_to_use] = {
                        "id": school_name_to_use, # 使用追踪到的名称作为ID
                        "name": school_name_to_use,
                        "level": school_level,
                        "region": region,
                        "province": current_province,
                        "intro": None, # Intro likely on first row, handle later if needed
                        "computer_rank": None, # Rank likely on first row
                        "self_vs_408": "待判断",
                        "departments": {},
                        "favorites_count": 0
                    }
                    # 尝试在创建时填充简介和等级 (只在第一次遇到学校时获取)
                    all_schools_data[school_name_to_use]['intro'] = row.get('简介', '').strip() if pd.notna(row.get('简介')) else None
                    all_schools_data[school_name_to_use]['computer_rank'] = row.get('计算机等级', '').strip() if pd.notna(row.get('计算机等级')) else None

                # --- 获取或创建院系 ---
                department_name = row.get('招生院系', '未知院系')
                if pd.isna(department_name) or str(department_name).strip() == '':
                    department_name = '未知院系'
                else:
                     department_name = str(department_name).strip()


                school_entry = all_schools_data[school_name_to_use]
                if department_name not in school_entry['departments']:
                     school_entry['departments'][department_name] = {
                         "department_name": department_name,
                         "majors": [] # 专业列表
                     }

                # --- 提取专业详细信息 ---
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
                    "major_code": major_code_str,
                    "major_name": major_name,
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

            print(f"    工作表 '{sheet_name}' 处理完成。找到 {len(df)} 有效行数据。") # Log count

        except Exception as e:
            print(f"处理工作表 '{sheet_name}' 时发生错误: {e}")
            import traceback
            traceback.print_exc()

    # --- 后处理和输出 ---
    if not all_schools_data:
         print("\\n错误：未能从 Excel 文件中提取任何学校数据。输出文件将为空。")
         # Write empty list to avoid stale data? Or keep old data? Let's write empty.
         final_school_list = []
    else:
        print(f"\\n总共处理得到 {len(all_schools_data)} 所学校的数据。")
        final_school_list = []
        for school_data in all_schools_data.values():
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