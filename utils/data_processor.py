import pandas as pd
import json
import os
import re # 用于后续的正则提取
import math # For isnan check if not using pandas

# 定义文件路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # 获取项目根目录
EXCEL_PATH = os.path.join(BASE_DIR, "择校文档.xlsx") # Primary input Excel file
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "data", "schools.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
# CSV_SOURCE_DIR = BASE_DIR # No longer needed

# --- 省份数据 (用于 extract_province_smart IF it needs to validate provinces) ---
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
    "福州": "福建", "厦门": "福建", "泉州": "福建", # Removed "汕头": "福建", as Shantou is in Guangdong
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
    sorted_provinces = sorted(VALID_PROVINCES, key=len, reverse=True)
    for province in sorted_provinces:
        if province in text:
            return province
    return None

def extract_province_smart(row, school_name_raw, intro_raw):
    """智能提取省份，按优先级：列 -> 名称 -> 简介 -> 市名映射。"""
    school_name = str(school_name_raw) if pd.notna(school_name_raw) else ''
    intro = str(intro_raw) if pd.notna(intro_raw) else ''
    
    # 1. Check explicit '省份' column first
    province_from_col = get_first_value_from_row(row, '省份') # Use helper
    if pd.notna(province_from_col):
        province_str = str(province_from_col).strip()
        if is_valid_province(province_str): return province_str

    # 3. Check school name for location in brackets or prefix
    match = re.search(r'[（(](.+?)[)）]', school_name)
    if match:
        location = match.group(1).strip()
        if is_valid_province(location): return location
        if location in CITY_TO_PROVINCE: return CITY_TO_PROVINCE[location]
    for city, province_of_city in CITY_TO_PROVINCE.items():
        if school_name.startswith(city): return province_of_city

    # 4. Extract from school name string
    province_from_name = extract_province_from_string(school_name)
    if province_from_name: return province_from_name
        
    # 5. Extract from intro string
    province_from_intro = extract_province_from_string(intro)
    if province_from_intro: return province_from_intro

    return None # Return None if no province found

def clean_column_names(df):
    df.columns = df.columns.str.strip()
    return df

def extract_school_level(name_str, row_level_val, intro_str=None):
    """从行数据、名称或简介中提取院校等级"""
    explicit_level_from_col = None
    # 1. 优先检查等级列
    if pd.notna(row_level_val):
        level_str = str(row_level_val).strip()
        # "普通院校" 也是一个可接受的等级列值
        if level_str in ["985", "211", "双一流", "一般", "普通院校"]:
            # 如果等级列是明确的 985/211/双一流，直接返回
            if level_str in ["985", "211", "双一流"]:
                return level_str
            # 如果等级列是 "一般" 或 "普通院校"，我们稍后还会检查名称和简介
            explicit_level_from_col = level_str 
        # else: 如果等级列的值不是预期的，则视为无效，继续检查名称和简介
    
    # 2. 检查名称
    if isinstance(name_str, str):
        if "985" in name_str: return "985"
        if "211" in name_str: return "211"
        # "双一流" 在名称中可能不那么常见或明确，主要依赖简介或列
        # if "双一流" in name_str: return "双一流" 
    
    # 3. 检查简介 (新增逻辑)
    if isinstance(intro_str, str):
        intro_lower = intro_str.lower() # 转为小写以便匹配
        # 更精确地匹配 "985工程" 或 "985大学" 等，避免误判包含 "985" 数字的其他文本
        if re.search(r"985工程|985大学|\"985\"", intro_lower): return "985"
        if re.search(r"211工程|211大学|\"211\"", intro_lower): return "211"
        # 双一流的判断可以更宽松一些，因为它通常以文本形式出现
        if "双一流" in intro_lower or "一流大学" in intro_lower or "一流学科" in intro_lower: return "双一流"

    # 4. 如果等级列有明确的 "一般" 或 "普通院校"，且名称和简介中没找到更高级别的，则使用它
    if explicit_level_from_col in ["一般", "普通院校"]:
        return explicit_level_from_col

    return "普通院校" # 默认返回 "普通院校"

def find_header_row(df_peek, keywords):
    best_header_index = -1
    max_matches = 0
    if df_peek.empty: return -1
    MIN_KEYWORD_MATCHES = 2 
    for i in range(min(len(df_peek), 15)): # Limit scan to first 15 rows
        current_matches = 0
        try:
            row_values = [str(cell).strip().lower() for cell in df_peek.iloc[i].tolist()]
        except Exception: continue
        for keyword in keywords:
            if any(keyword.lower() in cell_value for cell_value in row_values):
                current_matches += 1
        if current_matches > max_matches and current_matches >= MIN_KEYWORD_MATCHES:
            max_matches = current_matches
            best_header_index = i
    return best_header_index

def determine_region_from_filename_hint(hint_name):
    """根据工作表名判断院校所属区域（A区或B区）
    Excel工作表名为"B区"的学校归为B区，其他均为A区
    """
    if isinstance(hint_name, str) and "B区" in hint_name:
        return "B区"
    return "A区"

# def get_province_hint_from_filename(hint_name): # REMOVE THIS FUNCTION
#     """
#     根据从文件名提取的提示名称（如 "安徽", "福建", "Sheet1"）判断是否为有效省份提示。
#     排除 "Sheet1", "B区", "东三省" 等特殊提示。
#     """
#     if hint_name not in ["Sheet1", "B区", "东三省"]:
#         # 直接检查传入的 hint_name 是否是有效省份
#         if is_valid_province(hint_name):
#             return hint_name
#     return None # 如果是特殊提示或无效省份名，则返回 None

def get_multiline_str(value):
    if isinstance(value, pd.Series):
        if not value.empty:
            value = value.iloc[0] # 如果是Series，取第一个元素
        else: # 如果是空 Series，则视为 None
            value = None
    if pd.isna(value): return None
    return str(value).strip()

def get_first_value_from_row(row, primary_col_name, secondary_col_name=None):
    """安全地从Pandas行中获取值，处理潜在的Series并获取第一个元素。"""
    val_primary = row.get(primary_col_name)
    
    primary_is_effectively_na = False
    if isinstance(val_primary, pd.Series):
        # 如果是Series，则当它为空，或其第一个元素为NA时，我们认为它是缺失的
        if val_primary.empty or pd.isna(val_primary.iloc[0]):
            primary_is_effectively_na = True
        # else: val_primary is a Series with a non-NA first element, so we'll use it.
    elif pd.isna(val_primary): # 如果val_primary是标量NA或None
        primary_is_effectively_na = True

    chosen_val = val_primary
    if primary_is_effectively_na and secondary_col_name:
        chosen_val = row.get(secondary_col_name) # 尝试使用备用列

    # 现在处理最终选择的值 (chosen_val)
    if isinstance(chosen_val, pd.Series):
        return chosen_val.iloc[0] if not chosen_val.empty else None
            
    return chosen_val # 如果 chosen_val 不是系列 (即它是标量、None 或 pd.NA), get_multiline_str 会处理 pd.isna()

def parse_enrollment(value):
    if pd.isna(value):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    
    if isinstance(value, str):
        value_str = value.strip()
        if not value_str:
            return 0

        # Handle specific non-numeric strings that imply zero or should be treated as zero
        # For example, "无", "未知", "待定", "查看简章", "-", "/"
        # This list can be expanded based on observed data.
        known_non_enrollment_strings = ["无", "未知", "待定", "查看简章", "-", "/"]
        if value_str.lower() in [s.lower() for s in known_non_enrollment_strings]: # Case-insensitive check
            return 0
        
        # Attempt to extract the first sequence of digits
        # This handles cases like "100【含推免】" -> 100 or "专业共93" -> 93 or "35【3】" -> 35
        match = re.search(r'\d+', value_str)
        if match:
            return int(match.group(0))
        else:
            # If no numbers are found after checking known strings, it implies 0.
            return 0
            
    # For any other types or if logic somehow misses, default to 0.
    return 0

def process_excel_sheet(df_sheet, sheet_name, all_schools_data):
    print(f"  Attempting to process Excel sheet: {sheet_name}")
    current_sheet_region = determine_region_from_filename_hint(sheet_name) # Use sheet_name as hint
    is_b_region_file = current_sheet_region == "B区" # Flag for B-region debugging
    
    if is_b_region_file: print(f"    [B区 DEBUG] Identified as B-region sheet.")

    # DataFrame is already passed in, cleaned, and header-processed by main_process_excel_file
    # df_sheet is assumed to have correct headers and string dtypes.
    df_cols_lower = {col.lower(): col for col in df_sheet.columns}
    print(f"    Sheet \'{sheet_name}\' 使用的列名: {list(df_sheet.columns)}")
    if is_b_region_file: print(f"    [B区 DEBUG] Columns for sheet '{sheet_name}': {list(df_sheet.columns)}")

    # --- Define possible column names (lowercase for matching) --- 
    school_name_cols_l = ['院校名称', '院校', '学校名称', '学校']
    intro_cols_l = ['简介', '院校简介']
    level_cols_l = ['院校等级', '等级']
    province_cols_l = ['省份'] 
    rank_cols_l = ['计算机等级', '计算机评级', '学科评估', '评估等级']
    dept_cols_l = ['招生院系', '院系名称', '院系', '学院']
    major_code_cols_l = ['专业代码', '代码', '专业代码及名称'] 
    major_name_cols_l = ['专业名称', '专业方向', '研究方向']
    exam_subj_cols_l = ['初试科目', '考试科目']
    ref_book_cols_l = ['参考书', '参考书目']
    retrial_subj_cols_l = ['复试科目']
    enroll_24_cols_l = ['24招生人数', '招生人数(24)', '24招生', '24年招生人数']
    enroll_23_cols_l = ['23招生人数', '招生人数(23)', '23招生', '23年招生人数']
    enroll_22_cols_l = ['22招生人数', '招生人数(22)', '22招生', '22年招生人数']
    enroll_generic_cols_l = ['招生人数', '招生']
    tuition_cols_l = ['学费学制', '学制与学费', '学费', '学制']
    score_24_cols_l = ['24复试线', '24分数线', '复试线(24)', '分数线(24)']
    score_23_cols_l = ['23复试线', '23分数线', '复试线(23)', '分数线(23)']
    score_22_cols_l = ['22复试线', '22分数线', '复试线(22)', '分数线(22)']
    adm_info_23_cols_l = ['23拟录取情况', '23录取', '录取情况(23)']
    adm_info_24_cols_l = ['24拟录取情况', '24录取', '24复试名单', '24拟录取', '录取情况(24)']

    def find_actual_col(possible_lower_names):
        for name_l in possible_lower_names:
            if name_l.lower() in df_cols_lower:
                return df_cols_lower[name_l.lower()]
        return None

    actual_school_name_col = find_actual_col(school_name_cols_l)
    actual_major_code_col = find_actual_col(major_code_cols_l)

    if actual_school_name_col is None:
        actual_school_name_col = next((col for col in df_sheet.columns if '校' in col or '大学' in col or '学院' in col), None)
        if actual_school_name_col: print(f"    启发式地选择列 '{actual_school_name_col}' 作为学校名称列 (Sheet: {sheet_name})。")
    if actual_major_code_col is None:
        potential_codes = [col for col in df_sheet.columns if '代码' in col]
        code_col_candidates = [col for col in potential_codes if '学校代码' not in col and '院校代码' not in col]
        if code_col_candidates:
            actual_major_code_col = code_col_candidates[0]
            print(f"    启发式地选择列 '{actual_major_code_col}' 作为专业代码列 (Sheet: {sheet_name})。")
        
    if not actual_school_name_col: 
        print(f"    严重警告: 工作表 \'{sheet_name}\' 中未找到学校名称列。跳过。")
        if is_b_region_file: print(f"    [B区 DEBUG] Skipping sheet '{sheet_name}' due to missing school name column.")
        return
    if not actual_major_code_col: 
        print(f"    警告: 工作表 \'{sheet_name}\' 中未找到专业代码列。跳过。")
        if is_b_region_file: print(f"    [B区 DEBUG] Skipping sheet '{sheet_name}' due to missing major code column.")
        return
    print(f"    Sheet '{sheet_name}': 使用 '{actual_school_name_col}' 作为学校名称列, '{actual_major_code_col}' 作为专业代码列。")

    # --- Preprocessing (Forward fill for merged cells) --- 
    if actual_school_name_col in df_sheet.columns:
        df_sheet[actual_school_name_col] = df_sheet[actual_school_name_col].ffill()
    
    actual_dept_col = find_actual_col(dept_cols_l) 
    if actual_dept_col and actual_dept_col in df_sheet.columns:
        print(f"    对列 \'{actual_dept_col}\' (Sheet: {sheet_name}) 进行向前填充以处理合并单元格导致的院系缺失问题。")
        df_sheet[actual_dept_col] = df_sheet[actual_dept_col].ffill()
    else:
        print(f"    警告: 工作表 \'{sheet_name}\' 中未找到明确的院系列 ('{actual_dept_col}') 进行填充，院系信息可能不完整。")

    df_sheet.dropna(subset=[actual_major_code_col], how='all', inplace=True)
    # Ensure major code column exists before trying to filter on it
    if actual_major_code_col in df_sheet.columns:
        df_sheet = df_sheet[df_sheet[actual_major_code_col].astype(str).str.strip().str.len() > 0].copy()
    df_sheet.reset_index(drop=True, inplace=True)
    df_sheet.dropna(how='all', inplace=True) # Drop rows where ALL values are NaN
    
    if df_sheet.empty: 
        print(f"    工作表 \'{sheet_name}\' 数据在预处理后为空，跳过。") 
        if is_b_region_file: print(f"    [B区 DEBUG] Sheet '{sheet_name}' empty after preprocessing, skipping.")
        return
        
    if is_b_region_file: print(f"    [B区 DEBUG] Sheet '{sheet_name}' has {len(df_sheet)} rows after preprocessing.")

    for index, row in df_sheet.iterrows():
        try:
            school_name_raw = row.get(actual_school_name_col)
            if pd.isna(school_name_raw) or not str(school_name_raw).strip(): continue
            school_name_cleaned = str(school_name_raw).split('\n')[0].strip()

            # print(f"DEBUG: Processing Excel sheet '{sheet_name}' row index {index}, school_name_cleaned: '{school_name_cleaned}'")

            if school_name_cleaned not in all_schools_data:
                # print(f"DEBUG: School '{school_name_cleaned}' not in all_schools_data. Creating new entry from sheet '{sheet_name}'.")
                intro_raw = get_first_value_from_row(row, find_actual_col(intro_cols_l))
                level_val = get_first_value_from_row(row, find_actual_col(level_cols_l))
                province = extract_province_smart(row, school_name_cleaned, intro_raw) 
                intro_for_level_check = get_multiline_str(intro_raw)
                rank_val_raw = get_first_value_from_row(row, find_actual_col(rank_cols_l))
                computer_rank_cleaned = "未提供" 

                if pd.notna(rank_val_raw):
                    rank_str_original = str(rank_val_raw).strip()
                    rank_str_upper = rank_str_original.upper()
                    if not rank_str_upper or rank_str_upper == "-" :
                        computer_rank_cleaned = "无评级"
                    elif any(no_rank_indicator in rank_str_upper for no_rank_indicator in ["无评级", "未评估", "不参评", "未参与评估", "不参与评估"]):
                        computer_rank_cleaned = "无评级"
                    else:
                        ORDERED_VALID_RANKS = ['A+', 'A-', 'A', 'B+', 'B-', 'B', 'C+', 'C-', 'C']
                        found_rank_flag = False
                        for r_check in ORDERED_VALID_RANKS:
                            if re.search(r'(?:^|[^A-Z0-9\w])' + re.escape(r_check) + r'(?:$|[^A-Z0-9\w])', rank_str_upper):
                                computer_rank_cleaned = r_check; found_rank_flag = True; break
                            elif r_check in rank_str_upper: 
                                computer_rank_cleaned = r_check; found_rank_flag = True; break
                        if not found_rank_flag:
                            temp_rank_cleaned_str = rank_str_original
                            noise_patterns = [
                                r"^(第四轮评级：|学科评估：|评估等级：|计算机等级：|计算机评级：|评级：)",
                                r"第[一二三四五六七八九十]轮评估?", r"第四轮", r"学科评估结果?",
                                r"计算机科学与技术", r"软件工程", r"等级", r"[：:]"
                            ]
                            for pattern in noise_patterns:
                                temp_rank_cleaned_str = re.sub(pattern, "", temp_rank_cleaned_str, flags=re.IGNORECASE).strip()
                            if temp_rank_cleaned_str.upper() in ORDERED_VALID_RANKS:
                                computer_rank_cleaned = temp_rank_cleaned_str.upper()
                            elif temp_rank_cleaned_str : computer_rank_cleaned = temp_rank_cleaned_str
                
                all_schools_data[school_name_cleaned] = {
                    "id": school_name_cleaned, "name": school_name_cleaned,
                    "level": extract_school_level(school_name_cleaned, level_val, intro_for_level_check),
                    "province": province,
                    "region": current_sheet_region if current_sheet_region else "未知分区",
                    "intro": get_multiline_str(intro_raw),
                    "computer_rank": computer_rank_cleaned,
                    "departments": [], "exam_subjects_summary": ""
                }
                # if school_name_cleaned not in all_schools_data:
                #     print(f"FATAL DEBUG: School '{school_name_cleaned}' STILL NOT in all_schools_data after assignment (sheet '{sheet_name}', row {index})!")
                # else:
                #      print(f"DEBUG: School '{school_name_cleaned}' successfully added from sheet '{sheet_name}'.")
            
            school_entry = all_schools_data[school_name_cleaned]

            if current_sheet_region and current_sheet_region != school_entry.get('region'):
                print(f"    更新学校 '{school_name_cleaned}' 的区域从 '{school_entry.get('region')}' 到 '{current_sheet_region}' (来自工作表 {sheet_name})")
                school_entry['region'] = current_sheet_region

            dept_name_val = get_first_value_from_row(row, find_actual_col(dept_cols_l))
            department_name = get_multiline_str(dept_name_val) or '未知院系'
            
            # Find or create department entry
            dept_entry = next((d for d in school_entry['departments'] if d["department_name"] == department_name), None)
            if not dept_entry:
                dept_entry = {"department_name": department_name, "majors": []}
                school_entry['departments'].append(dept_entry)


            # --- Refined Major Info Extraction ---
            major_code_raw = row.get(actual_major_code_col, '')
            # raw_code_field_value holds the original string from the '专业代码' or '专业代码及名称' column
            raw_code_field_value = str(major_code_raw).strip() if pd.notna(major_code_raw) else ''

            major_name_val = get_first_value_from_row(row, find_actual_col(major_name_cols_l))
            # major_name_from_dedicated_col is from columns like '专业名称', '专业方向'
            major_name_from_dedicated_col = str(major_name_val).strip() if pd.notna(major_name_val) else ''

            parsed_major_code = ''
            parsed_name_from_code_field = ''

            if raw_code_field_value:
                # Try to match '000000 Name Part'
                match_code_and_name = re.match(r'(\\d{6})\\s*(.+)', raw_code_field_value)
                if match_code_and_name:
                    parsed_major_code = match_code_and_name.group(1)
                    parsed_name_from_code_field = match_code_and_name.group(2).strip()
                # Try to match if it's just a 6-digit code '000000'
                elif re.match(r'^\\d{6}$', raw_code_field_value):
                    parsed_major_code = raw_code_field_value
                # If not a 6-digit code and not code+name, it might be just a name in the code field,
                # or a non-6-digit code.
                elif not re.match(r'^\\d+$', raw_code_field_value): # If it's not purely numeric
                    parsed_name_from_code_field = raw_code_field_value # Treat as potential name
                else: # It's purely numeric but not 6 digits, treat as code
                    parsed_major_code = raw_code_field_value


            # Determine the final major_name
            # Priority: 1. Dedicated name column (if specific) -> 2. Name parsed from code field
            final_major_name = major_name_from_dedicated_col
            if parsed_name_from_code_field and (not final_major_name or final_major_name in ['-', '未知专业', '查看详情', '待定']):
                final_major_name = parsed_name_from_code_field
            
            # Determine the final major_code
            final_major_code = parsed_major_code
            # If no code was parsed but the raw field was purely digits, use that raw field as code
            if not final_major_code and re.match(r'^\\d+$', raw_code_field_value):
                final_major_code = raw_code_field_value

            major_code_str = final_major_code
            major_name = final_major_name
            
            if not major_code_str and not major_name: continue # Skip if no major identifier

            enrollment_history = {"2024": 0, "2023": 0, "2022": 0}
            actual_enroll_24_col = find_actual_col(enroll_24_cols_l)
            actual_enroll_23_col = find_actual_col(enroll_23_cols_l)
            actual_enroll_22_col = find_actual_col(enroll_22_cols_l)
            actual_enroll_generic_col = find_actual_col(enroll_generic_cols_l)

            raw_enroll_24 = get_first_value_from_row(row, actual_enroll_24_col) if actual_enroll_24_col else None
            if pd.notna(raw_enroll_24) and str(raw_enroll_24).strip():
                # print(f"DEBUG_ENROLL_PARSED_24 (Excel): School='{school_name_cleaned}', Major='{major_code_str}', Sheet='{sheet_name}', Raw='{raw_enroll_24}', Parsed='{parse_enrollment(raw_enroll_24)}'")
                enrollment_history["2024"] = parse_enrollment(raw_enroll_24)
            
            if enrollment_history["2024"] == 0 and actual_enroll_generic_col: 
                raw_enroll_generic = get_first_value_from_row(row, actual_enroll_generic_col)
                if pd.notna(raw_enroll_generic) and str(raw_enroll_generic).strip():
                    parsed_generic = parse_enrollment(raw_enroll_generic)
                    if parsed_generic != 0: 
                        enrollment_history["2024"] = parsed_generic
                        if enrollment_history["2023"] == 0: enrollment_history["2023"] = parsed_generic 
                        if enrollment_history["2022"] == 0: enrollment_history["2022"] = parsed_generic

            if enrollment_history["2023"] == 0 and actual_enroll_23_col: 
                raw_enroll_23 = get_first_value_from_row(row, actual_enroll_23_col)
                if pd.notna(raw_enroll_23) and str(raw_enroll_23).strip():
                     enrollment_history["2023"] = parse_enrollment(raw_enroll_23)

            if enrollment_history["2022"] == 0 and actual_enroll_22_col: 
                raw_enroll_22 = get_first_value_from_row(row, actual_enroll_22_col)
                if pd.notna(raw_enroll_22) and str(raw_enroll_22).strip():
                     enrollment_history["2022"] = parse_enrollment(raw_enroll_22)
            
            for year_key in ['2024', '2023', '2022']:
                current_val = enrollment_history.get(year_key)
                if not isinstance(current_val, int):
                    enrollment_history[year_key] = int(current_val) if isinstance(current_val, str) and current_val.isdigit() else 0

            score_lines = {}
            score_val_24 = get_first_value_from_row(row, find_actual_col(score_24_cols_l))
            if score_val_24: score_lines["2024"] = get_multiline_str(score_val_24)
            score_val_23 = get_first_value_from_row(row, find_actual_col(score_23_cols_l))
            if score_val_23: score_lines["2023"] = get_multiline_str(score_val_23)
            score_val_22 = get_first_value_from_row(row, find_actual_col(score_22_cols_l))
            if score_val_22: score_lines["2022"] = get_multiline_str(score_val_22)

            exam_subjects_val = get_first_value_from_row(row, find_actual_col(exam_subj_cols_l))
            
            if not major_name or major_name in ['-', '未知专业', '查看详情', '待定']:
                temp_major_name = "未知专业方向"; code = major_code_str
                subjects = str(get_multiline_str(exam_subjects_val)).lower() if exam_subjects_val else ""
                if '0812' in code or '计算机科学与技术' in subjects: temp_major_name = '计算机科学与技术'
                elif '0835' in code or '085405' in code or '软件工程' in subjects: temp_major_name = '软件工程'
                elif '085404' in code or '计算机技术' in subjects: temp_major_name = '计算机技术'
                elif '085410' in code or '人工智能' in subjects: temp_major_name = '人工智能'
                elif '085411' in code or '大数据' in subjects: temp_major_name = '大数据技术与工程'
                elif '0839' in code or '网络空间安全' in subjects: temp_major_name = '网络空间安全'
                major_name = temp_major_name
                
            major_info = {
                "major_code": major_code_str, "major_name": major_name,
                "exam_subjects": get_multiline_str(exam_subjects_val),
                "reference_books": get_multiline_str(get_first_value_from_row(row, find_actual_col(ref_book_cols_l))),
                "retrial_subjects": get_multiline_str(get_first_value_from_row(row, find_actual_col(retrial_subj_cols_l))),
                "enrollment": enrollment_history,
                "tuition_duration": get_multiline_str(get_first_value_from_row(row, find_actual_col(tuition_cols_l))),
                "score_lines": score_lines,
                "admission_info_23": get_multiline_str(get_first_value_from_row(row, find_actual_col(adm_info_23_cols_l))),
                "admission_info_24": get_multiline_str(get_first_value_from_row(row, find_actual_col(adm_info_24_cols_l)))
            }
            
            dept_entry['majors'].append(major_info)
        except Exception as e_row:
            print(f"    处理工作表 \'{sheet_name}\' 的行 (Excel index {index}) 时发生错误: {e_row}")
            if is_b_region_file: print(f"    [B区 DEBUG] Error processing row {index} in sheet '{sheet_name}': {e_row}")
            import traceback; traceback.print_exc()
            continue
    print(f"    工作表 \'{sheet_name}\' 处理完成。")

def replace_nan_with_none(obj): # Keep this helper (now at top level)
    if isinstance(obj, list): return [replace_nan_with_none(item) for item in obj]
    if isinstance(obj, dict): return {key: replace_nan_with_none(value) for key, value in obj.items()}
    if isinstance(obj, float) and pd.isna(obj): return None
    if obj is pd.NA: return None
    return obj

def main_process_excel_file(excel_file_path, output_json_path):
    all_schools_data = {}
    
    if not os.path.exists(excel_file_path):
        print(f"错误: Excel 文件 {excel_file_path} 未找到。程序将退出。")
        return

    print(f"开始从 Excel 文件: {excel_file_path} 处理数据...")
    header_keywords = ['学校', '代码', '专业', '院系', '科目', '名称', '招生', '录取', '复试', '考试', '省份', '简介', '等级', '评级', '院校', '学费']

    try:
        xls = pd.ExcelFile(excel_file_path)
        sheet_names = xls.sheet_names
        print(f"发现工作表: {sheet_names}")

        for sheet_name in sheet_names:
            print(f"\n正在处理工作表: {sheet_name}...")
            try:
                # Peek at the sheet to find the header row
                df_peek = pd.read_excel(xls, sheet_name, nrows=20, header=None, dtype=str)
                identified_header_idx = find_header_row(df_peek, header_keywords)

                if identified_header_idx != -1:
                    print(f"    在工作表 '{sheet_name}' 的第 {identified_header_idx + 1} 行找到表头。")
                    df_sheet = pd.read_excel(xls, sheet_name, header=identified_header_idx, dtype=str)
                else:
                    print(f"    警告: 在工作表 '{sheet_name}' 未能动态找到表头，将使用第一行作为表头。")
                    df_sheet = pd.read_excel(xls, sheet_name, header=0, dtype=str)
                
                df_sheet = clean_column_names(df_sheet)
                process_excel_sheet(df_sheet, sheet_name, all_schools_data)

            except Exception as e_sheet:
                print(f"    处理工作表 '{sheet_name}' 时发生错误: {e_sheet}")
                import traceback; traceback.print_exc()
                continue
        
    except Exception as e_file:
        print(f"读取或处理 Excel 文件 '{excel_file_path}' 时发生严重错误: {e_file}")
        import traceback; traceback.print_exc()
        return # Stop processing if the Excel file itself has issues

    # --- Final Processing & Output ---
    print(f"\nTotal unique schools processed: {len(all_schools_data)}")

    for school_name, school_data in all_schools_data.items():
        total_enrollment_24 = 0
        exam_subjects_list = set()
        try:
            if 'departments' in school_data and isinstance(school_data['departments'], list):
                for department in school_data['departments']:
                    if 'majors' in department and isinstance(department['majors'], list):
                        for major in department['majors']:
                            enrollment_data = major.get('enrollment', {})
                            enrollment_24 = enrollment_data.get('2024', 0)
                            total_enrollment_24 += int(enrollment_24) if isinstance(enrollment_24, (int, float)) or (isinstance(enrollment_24, str) and enrollment_24.isdigit()) else 0
                            
                            subjects_str = major.get('exam_subjects')
                            if subjects_str and isinstance(subjects_str, str):
                                subjects = [s.strip() for s in subjects_str.split('\\n') if s.strip()] # Handle escaped newlines if any, or direct
                                subjects_flat = []
                                for s_part in subjects: # Further split if multiple subjects are in one line, e.g. "subj1 subj2"
                                    subjects_flat.extend(s_part.split()) # Basic split, might need refinement
                                exam_subjects_list.update(subjects_flat)


            school_data['enrollment_24_school_total'] = total_enrollment_24
            school_data['exam_subjects_summary'] = " | ".join(sorted(list(exam_subjects_list))) if exam_subjects_list else "未提供"
        except Exception as e_post:
            print(f"Error during post-processing for school '{school_name}': {e_post}")
            school_data['enrollment_24_school_total'] = 0 
            school_data['exam_subjects_summary'] = "处理错误"

    final_school_list = list(all_schools_data.values())
    final_school_list.sort(key=lambda x: (x.get('region') or '', x.get('province') or '', x.get('name') or ''))
    cleaned_school_list = replace_nan_with_none(final_school_list) # Ensure this function is defined globally

    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_school_list, f, ensure_ascii=False, indent=2)
        print(f"\n成功将处理后的数据写入到: {output_json_path}")
    except IOError as e: print(f"写入 JSON 文件时出错: {e}")
    except Exception as e: print(f"转换或写入 JSON 时发生未知错误: {e}")


if __name__ == "__main__":
    print(f"开始从 Excel 文件 {EXCEL_PATH} 处理数据...")
    main_process_excel_file(EXCEL_PATH, OUTPUT_JSON_PATH) 