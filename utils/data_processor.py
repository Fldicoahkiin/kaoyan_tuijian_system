import pandas as pd
import json
import os
import re # 用于后续的正则提取

# 定义文件路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # 获取项目根目录
# EXCEL_PATH = os.path.join(BASE_DIR, "择校文档.xlsx") # No longer primary input
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "data", "schools.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_SOURCE_DIR = BASE_DIR # Assuming CSVs are in the root project directory for now

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

def process_single_csv(csv_path, filename_hint, all_schools_data):
    print(f"  Attempting to process CSV file: {os.path.basename(csv_path)} (Hint for region/other: {filename_hint})") # Added more explicit start message
    current_sheet_region = determine_region_from_filename_hint(filename_hint)
    # filename_province_hint = None (already set as it was removed from extract_province_smart call)
    
    print(f"    文件 \'{os.path.basename(csv_path)}\' 被识别为区域: {current_sheet_region}")

    try:
        # Try to detect header dynamically, similar to Excel processing
        df_peek = pd.read_csv(csv_path, nrows=20, header=None, on_bad_lines='skip', encoding='utf-8')
        header_keywords = ['学校', '代码', '专业', '院系', '科目', '名称', '招生', '录取', '复试', '考试', '省份', '简介', '等级', '评级', '院校']
        identified_header_idx = find_header_row(df_peek, header_keywords)

        if identified_header_idx != -1:
            print(f"    文件 \'{os.path.basename(csv_path)}\': 动态识别到表头在第 {identified_header_idx + 1} 行。")
            df = pd.read_csv(csv_path, header=identified_header_idx, on_bad_lines='skip', encoding='utf-8')
        else:
            print(f"    文件 \'{os.path.basename(csv_path)}\': 未能动态识别表头，尝试使用默认表头行 1 (0-indexed 0)。")
            df = pd.read_csv(csv_path, header=0, on_bad_lines='skip', encoding='utf-8')
        
        df = clean_column_names(df)
        df.columns = [re.sub(r'\\.\\d+$', '', col).strip() for col in df.columns] # Remove .1 suffixes
        print(f"    文件 \'{os.path.basename(csv_path)}\' 清理后的列名: {list(df.columns)}")

    except Exception as e:
        print(f"读取或预处理 CSV 文件 \'{os.path.basename(csv_path)}\' 时出错: {e}")
        return

    # --- Define possible column names --- 
    school_name_cols = ['院校名称', '院校', '学校名称', '学校']
    intro_cols = ['简介', '院校简介']
    level_cols = ['院校等级', '等级']
    rank_cols = ['计算机等级', '计算机评级', '学科评估', '评估等级']
    dept_cols = ['招生院系', '院系名称', '院系', '学院']
    major_code_cols = ['专业代码', '代码', '专业代码及名称'] # Priority order matters if combined
    major_name_cols = ['专业名称', '专业方向']
    exam_subj_cols = ['初试科目', '考试科目']
    ref_book_cols = ['参考书', '参考书目']
    retrial_subj_cols = ['复试科目']
    enroll_24_cols = ['24招生人数', '招生人数', '24招生', '招生']
    tuition_cols = ['学费学制', '学制与学费']
    score_24_cols = ['24复试线', '24分数线']
    score_23_cols = ['23复试线', '23分数线']
    adm_info_23_cols = ['23拟录取情况', '23录取']
    adm_info_24_cols = ['24拟录取情况', '24录取', '24复试名单', '24拟录取']

    # --- Find actual column names used in this CSV --- 
    actual_school_name_col = next((col for col in school_name_cols if col in df.columns), None)
    actual_major_code_col = next((col for col in major_code_cols if col in df.columns), None)

    # Heuristic fallbacks if standard names aren't found
    if actual_school_name_col is None:
        actual_school_name_col = next((col for col in df.columns if '校' in col or '大学' in col or '学院' in col), None)
        if actual_school_name_col: print(f"    启发式地选择列 '{actual_school_name_col}' 作为学校名称列。")
        if actual_major_code_col is None:
            actual_major_code_col = next((col for col in df.columns if '代码' in col and '学校代码' not in col and '院校代码' not in col), None)
            if actual_major_code_col: print(f"    启发式地选择列 '{actual_major_code_col}' 作为专业代码列。")

    if not actual_school_name_col: print(f"    严重警告: 文件 \'{os.path.basename(csv_path)}\' 中未找到学校名称列。跳过。"); return
    if not actual_major_code_col: print(f"    警告: 文件 \'{os.path.basename(csv_path)}\' 中未找到专业代码列。跳过。"); return
    print(f"    使用 '{actual_school_name_col}' 作为学校名称列, '{actual_major_code_col}' 作为专业代码列。")

    # --- Preprocessing --- 
    df[actual_school_name_col] = df[actual_school_name_col].ffill()
    df.dropna(subset=[actual_major_code_col], how='all', inplace=True)
    df = df[df[actual_major_code_col].astype(str).str.match(r'^\s*\S+.*')].copy() # Keep if major code not just whitespace
    df.reset_index(drop=True, inplace=True)
    df.dropna(how='all', inplace=True)
    if df.empty: 
        print(f"    文件 \'{os.path.basename(csv_path)}\' 数据为空或所有行均为NA，跳过。") # More explicit message
        return

    # --- Row-by-row processing --- 
    for index, row in df.iterrows():
        try:
            # --- Extract School Info (once per school) ---
            school_name_raw = row.get(actual_school_name_col)
            if pd.isna(school_name_raw) or not str(school_name_raw).strip(): continue
            school_name_cleaned = str(school_name_raw).split('\n')[0].strip()

            print(f"DEBUG: Processing CSV row index {index}, school_name_cleaned: '{school_name_cleaned}'") # Added CSV Index

            if school_name_cleaned not in all_schools_data:
                print(f"DEBUG: School '{school_name_cleaned}' not in all_schools_data. Creating new entry.")
                print(f"DEBUG: Before assigning '{school_name_cleaned}' to all_schools_data.")
                intro_raw = get_first_value_from_row(row, intro_cols[0], intro_cols[1] if len(intro_cols)>1 else None)
                level_val = get_first_value_from_row(row, level_cols[0], level_cols[1] if len(level_cols)>1 else None)
                province = extract_province_smart(row, school_name_cleaned, intro_raw) 
                
                intro_for_level_check = get_multiline_str(intro_raw)

                # --- Refined Computer Rank Extraction ---
                rank_val_raw = get_first_value_from_row(row, rank_cols[0], rank_cols[1]) or \
                               get_first_value_from_row(row, rank_cols[2] if len(rank_cols)>2 else None, rank_cols[3] if len(rank_cols)>3 else None)
                computer_rank_cleaned = "未提供" # Default

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
                            # Regex to find rank as a whole word or with typical surrounding, non-alphanumeric characters
                            # This handles "A+", "(A+)", "A+等", "评级A+" but not "学科A" if 'A' is the rank.
                            # It prioritizes ranks that are clearly demarcated.
                            if re.search(r'(?:^|[^A-Z0-9\w])' + re.escape(r_check) + r'(?:$|[^A-Z0-9\w])', rank_str_upper):
                                computer_rank_cleaned = r_check
                                found_rank_flag = True
                                break
                            # Simpler check if the above is too strict, for ranks that might be embedded
                            elif r_check in rank_str_upper: # Check if 'A+' is simply in 'BLABLA A+ BLABLA'
                                computer_rank_cleaned = r_check 
                                found_rank_flag = True
                                # Don't break immediately for this simpler check if a more specific one (like A+ vs A) might follow for a substring
                                # However, our ORDERED_VALID_RANKS handles A+ before A. So, first simple 'in' match is good.
                                break 
                        
                        if not found_rank_flag:
                            # If no standard A/B/C rank found directly, try cleaning common verbose terms
                            # and see if a valid rank emerges or the string becomes manageable.
                            temp_rank_cleaned_str = rank_str_original
                            noise_patterns = [
                                r"^(第四轮评级：|学科评估：|评估等级：|计算机等级：|计算机评级：|评级：)",
                                r"第[一二三四五六七八九十]轮评估?",
                                r"第四轮",
                                r"学科评估结果?",
                                r"计算机科学与技术",
                                r"软件工程",
                                r"等级",
                                r"[：:]" # Colons
                            ]
                            for pattern in noise_patterns:
                                temp_rank_cleaned_str = re.sub(pattern, "", temp_rank_cleaned_str, flags=re.IGNORECASE).strip()
                            
                            # After cleaning, check again if it matches a standard rank
                            if temp_rank_cleaned_str.upper() in ORDERED_VALID_RANKS:
                                computer_rank_cleaned = temp_rank_cleaned_str.upper()
                            elif temp_rank_cleaned_str : # If something non-empty remains after cleaning
                                computer_rank_cleaned = temp_rank_cleaned_str # Use the cleaned, possibly non-standard, string
                            # If temp_rank_cleaned_str is empty, it defaults to "未提供" (or "无评级" if set earlier)
                # --- End of Refined Computer Rank Extraction ---

                all_schools_data[school_name_cleaned] = {
                    "id": school_name_cleaned, "name": school_name_cleaned,
                    "level": extract_school_level(school_name_cleaned, level_val, intro_for_level_check),
                    "province": province if province else "未知省份",
                    "region": current_sheet_region,
                    "intro": get_multiline_str(intro_for_level_check),
                    "computer_rank": computer_rank_cleaned,
                    "departments": {}, 
                    "enrollment_24_school_total": "未知",
                }
                print(f"DEBUG: After assigning '{school_name_cleaned}' to all_schools_data. Check presence now:")
                if school_name_cleaned not in all_schools_data:
                    print(f"FATAL DEBUG: School '{school_name_cleaned}' STILL NOT in all_schools_data after assignment at row index {index}!")
                else:
                     print(f"DEBUG: School '{school_name_cleaned}' successfully added to all_schools_data.")
            
            school_entry = all_schools_data[school_name_cleaned]

            # --- Extract Department Info --- 
            dept_name_val = get_first_value_from_row(row, dept_cols[0], dept_cols[1]) or \
                            get_first_value_from_row(row, dept_cols[2] if len(dept_cols)>2 else None, dept_cols[3] if len(dept_cols)>3 else None)
            department_name = get_multiline_str(dept_name_val) or '未知院系'
            if department_name not in school_entry['departments']:
                school_entry['departments'][department_name] = {"department_name": department_name, "majors": []}

            # --- Extract Major Info --- 
            major_code_raw = row.get(actual_major_code_col, '')
            major_code_str = str(major_code_raw).strip() if pd.notna(major_code_raw) else ''
            major_name_val = get_first_value_from_row(row, major_name_cols[0], major_name_cols[1] if len(major_name_cols)>1 else None)
            major_name = str(major_name_val).strip() if pd.notna(major_name_val) else ''

            if actual_major_code_col == '专业代码及名称' and major_code_str:
                match_code_name = re.match(r'(\d{6})\s*(.*)', major_code_str)
                if match_code_name:
                    major_code_str = match_code_name.group(1)
                    if not major_name: major_name = match_code_name.group(2).strip()
                elif not re.match(r'^\d+$', major_code_str.split()[0] if major_code_str else '') and not major_name:
                    major_name = major_code_str; major_code_str = '' 
            
            if not major_code_str and not major_name: continue # Skip if no major identifier

            enroll_24_val = get_first_value_from_row(row, enroll_24_cols[0], enroll_24_cols[1]) or \
                            get_first_value_from_row(row, enroll_24_cols[2] if len(enroll_24_cols)>2 else None, enroll_24_cols[3] if len(enroll_24_cols)>3 else None)
            enrollment_24_num = None
            if pd.notna(enroll_24_val):
                enroll_str = str(enroll_24_val).strip()
                match_num = re.search(r'(\d+)', enroll_str)
                if match_num: enrollment_24_num = int(match_num.group(1))
                elif enroll_str.lower() in ['若干', '见官网', '待定']: enrollment_24_num = enroll_str # Keep string representation
            
            exam_subjects_val = get_first_value_from_row(row, exam_subj_cols[0], exam_subj_cols[1] if len(exam_subj_cols)>1 else None)
            
            # Standardize major name if still missing
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
                "reference_books": get_multiline_str(get_first_value_from_row(row, ref_book_cols[0], ref_book_cols[1] if len(ref_book_cols)>1 else None)),
                "retrial_subjects": get_multiline_str(get_first_value_from_row(row, retrial_subj_cols[0])),
                "enrollment_24": enrollment_24_num,
                "tuition_duration": get_multiline_str(get_first_value_from_row(row, tuition_cols[0], tuition_cols[1] if len(tuition_cols)>1 else None)),
                    "score_lines": {
                    "2024": get_multiline_str(get_first_value_from_row(row, score_24_cols[0], score_24_cols[1] if len(score_24_cols)>1 else None)),
                    "2023": get_multiline_str(get_first_value_from_row(row, score_23_cols[0], score_23_cols[1] if len(score_23_cols)>1 else None))
                },
                "admission_info_23": get_multiline_str(get_first_value_from_row(row, adm_info_23_cols[0], adm_info_23_cols[1] if len(adm_info_23_cols)>1 else None)),
                "admission_info_24": get_multiline_str(get_first_value_from_row(row, adm_info_24_cols[0], adm_info_24_cols[1]) or \
                                                  get_first_value_from_row(row, adm_info_24_cols[2] if len(adm_info_24_cols)>2 else None, adm_info_24_cols[3] if len(adm_info_24_cols)>3 else None))
            }
            
            school_entry['departments'][department_name]['majors'].append(major_info)
        except Exception as e_row:
            print(f"    处理文件 \'{os.path.basename(csv_path)}\' 的行 (CSV index {index}) 时发生错误: {e_row}")
            import traceback; traceback.print_exc()
            continue
    print(f"    文件 \'{os.path.basename(csv_path)}\' 处理完成。")

def replace_nan_with_none(obj): # Keep this helper (now at top level)
    if isinstance(obj, list): return [replace_nan_with_none(item) for item in obj]
    if isinstance(obj, dict): return {key: replace_nan_with_none(value) for key, value in obj.items()}
    if isinstance(obj, float) and pd.isna(obj): return None
    if obj is pd.NA: return None
    return obj

def main_process_all_csvs(csv_files_directory, output_json_path):
    all_schools_data = {}
    
    # Define mapping for CSV filenames to a "hint name" used for region/province logic
    # This assumes CSVs are named like "择校文档_安徽.csv", "择校文档_B区.csv", etc.
    # And "择校文档_Sheet1.csv" for the general sheet.
    csv_files_to_process = [f for f in os.listdir(csv_files_directory) if f.startswith("择校文档_") and f.endswith(".csv")]

    for csv_filename in csv_files_to_process:
        hint_name = csv_filename.replace("择校文档_", "").replace(".csv", "") # e.g., "安徽", "B区", "Sheet1"
        csv_full_path = os.path.join(csv_files_directory, csv_filename)
        
        if not os.path.exists(csv_full_path):
            print(f"警告: CSV 文件 {csv_full_path} 未找到。跳过。")
            continue
        
        process_single_csv(csv_full_path, hint_name, all_schools_data)

    # After processing all CSVs, convert departments from dict to list for JSON compatibility
    final_school_list = []
    for school_name, school_data in all_schools_data.items():
        # Ensure departments is a list of dictionaries
        if isinstance(school_data.get('departments'), dict):
            school_data['departments'] = list(school_data['departments'].values())
            for dept in school_data['departments']:
                if isinstance(dept.get('majors'), dict):
                    dept['majors'] = list(dept['majors'].values())
        
        # Aggregate exam subjects summary
        unique_exam_subjects = set()
        if isinstance(school_data.get('departments'), list):
            for dept_data in school_data['departments']:
                if isinstance(dept_data.get('majors'), list):
                    for major in dept_data['majors']:
                        subjects_str = major.get('exam_subjects')
                        if subjects_str and isinstance(subjects_str, str) and subjects_str.strip():
                            # Clean up and split subjects, assuming they might be newline or semicolon separated
                            # Handle cases like "①政治理论②英语一..." or "政治;英语;数学"
                            cleaned_subjects = subjects_str.strip()
                            # Attempt to split by common delimiters or just use the whole string if it's one block
                            # This is a simple approach; more sophisticated parsing might be needed for complex formats
                            parts = []
                            if ';' in cleaned_subjects:
                                parts = [s.strip() for s in cleaned_subjects.split(';') if s.strip()]
                            elif '\n' in cleaned_subjects:
                                parts = [s.strip() for s in cleaned_subjects.split('\n') if s.strip()]
                            else:
                                # If no obvious delimiter, consider it as one block or look for numbered items
                                # For now, let's add the whole cleaned string, or refine if needed
                                parts = [cleaned_subjects] # Could be further split if numbered like ①②③
                            
                            for part in parts:
                                unique_exam_subjects.add(part)

        if unique_exam_subjects:
            summary = " | ".join(sorted(list(unique_exam_subjects)))
            if len(summary) > 150: # Increased limit slightly
                summary = summary[:147] + "..."
            school_data['exam_subjects_summary'] = summary
        else:
            school_data['exam_subjects_summary'] = "见各专业详情"

        final_school_list.append(school_data)

    # Sort the final list by school name for consistent output (optional)
    final_school_list.sort(key=lambda x: (x.get('region', ''), x.get('province', ''), x.get('name', '')))

    cleaned_school_list = replace_nan_with_none(final_school_list)
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_school_list, f, ensure_ascii=False, indent=2)
        print(f"\n成功将处理后的数据写入到: {output_json_path}")
    except IOError as e: print(f"写入 JSON 文件时出错: {e}")
    except Exception as e: print(f"转换或写入 JSON 时发生未知错误: {e}")

if __name__ == "__main__":
    # Assuming CSVs are in the BASE_DIR (project root) for now
    print(f"开始从目录 {CSV_SOURCE_DIR} 处理所有 CSV 文件...")
    main_process_all_csvs(CSV_SOURCE_DIR, OUTPUT_JSON_PATH) 