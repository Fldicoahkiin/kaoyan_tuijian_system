# Placeholder for web scraping functionalities

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re # 导入 re 用于后续更复杂的数据提取
from urllib.parse import urljoin
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import platform # 导入 platform 模块用于 OS 检测

# --- Selenium Imports ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service # 导入 Service
from selenium.webdriver.support.ui import Select # 导入 Select

# --- 目标计算机相关专业代码集合 ---
TARGET_MAJOR_CODES = {
    '081200', # 计算机科学与技术 (学硕)
    '083500', # 软件工程 (学硕)
    '083900', # 网络空间安全 (学硕)
    '085400', # 电子信息 (专硕大类)
    '085404', # 计算机技术 (电子信息专硕方向)
    '085405', # 软件工程 (电子信息专硕方向)
    '085410', # 人工智能 (电子信息专硕方向)
    '085411'  # 大数据技术与工程 (电子信息专硕方向)
}

# --- 由目标专业代码衍生的目标学科大类前缀 (用于匹配分数线页面) ---
# 例如 081200 属于 08, 085404 属于 0854
TARGET_CATEGORY_PREFIXES = set()
for code in TARGET_MAJOR_CODES:
    if len(code) >= 2:
        TARGET_CATEGORY_PREFIXES.add(code[:2]) # 添加 2 位前缀 (如 08)
    if len(code) >= 4 and code.startswith('0854'): # 对 0854 特殊处理，也添加 4 位前缀
        TARGET_CATEGORY_PREFIXES.add(code[:4]) # 添加 4 位前缀 (如 0854)
# 移除可能存在的不必要的更短前缀，如果完整代码本身就是大类
if '085400' in TARGET_MAJOR_CODES:
     TARGET_CATEGORY_PREFIXES.add('0854') # 确保 0854 大类被包含
# print(f"DEBUG: Target category prefixes for score matching: {TARGET_CATEGORY_PREFIXES}") # Optional debug print

# 数据保存路径 (可以根据需要调整)
DATA_DIR = os.path.join(os.path.dirname(__file__), '../data')
SCHOOLS_FILE = os.path.join(DATA_DIR, 'schools.json')

# 目标院校列表 (示例，需要根据实际情况填充四川省高校)
TARGET_UNIVERSITIES = {
    "四川大学": "https://yz.scu.edu.cn/",
    "电子科技大学": "https://yz.uestc.edu.cn/",
    "西南交通大学": "https://yz.swjtu.edu.cn/", # 示例 URL，需核实
    "西南财经大学": "https://yz.swufe.edu.cn/", # 示例 URL，需核实
    "四川师范大学": "https://yjsc.sicnu.edu.cn/", # 示例 URL，需核实
    # 添加更多四川省的高校...
}

def load_existing_schools():
    """加载现有的 schools.json 数据 (预期为列表)"""
    if os.path.exists(SCHOOLS_FILE):
        with open(SCHOOLS_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                # 确保返回的是列表
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                print(f"Error: 无法解析 {SCHOOLS_FILE}")
                return [] # 出错时返回空列表
    return [] # 文件不存在时返回空列表

def save_schools_data(data_list):
    """保存学校列表数据到 schools.json"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCHOOLS_FILE, 'w', encoding='utf-8') as f:
        # 直接保存列表
        json.dump(data_list, f, ensure_ascii=False, indent=4)
    print(f"数据已保存到 {SCHOOLS_FILE}")

def fetch_page(url):
    """获取网页内容，增加 SSL 验证忽略选项"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # 禁用 SSL 警告
        warnings.filterwarnings('ignore', category=InsecureRequestWarning)
        # 添加 verify=False 来忽略 SSL 证书验证错误
        response = requests.get(url, headers=headers, timeout=15, verify=False) 
        response.raise_for_status() # 如果请求失败 (4xx, 5xx) 则抛出异常
        response.encoding = response.apparent_encoding 
        # 恢复警告（如果需要在其他地方验证 SSL）
        warnings.resetwarnings()
        return response.text
    except requests.exceptions.SSLError as ssl_err:
        print(f"请求 SSL 错误: {url}, 错误: {ssl_err} (已尝试忽略验证)")
        warnings.resetwarnings()
        return None
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {url}, 错误: {e}")
        warnings.resetwarnings()
        return None
    except Exception as e:
        print(f"获取页面时发生未知错误: {url}, 错误: {e}")
        warnings.resetwarnings()
        return None

# --- 新增：使用 Selenium 获取动态加载内容的页面 --- 
def fetch_dynamic_page_with_selenium(url, select_options=None, click_button_id=None, wait_after_click_selector=None, timeout=30):
    """
    使用 Selenium WebDriver 加载页面，可选地选择下拉框选项，点击按钮，
    然后等待特定元素出现，并返回页面源码。
    select_options: a list of dicts like [{"dropdown_id": "id", "option_value": "value"}]
    """
    html_source = None
    driver = None
    try:
        # --- 配置 WebDriver (移除 Headless) --- 
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless') # 暂时禁用无头模式进行调试
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("user-agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'")

        # --- 构造 ChromeDriver 路径 (跨平台) ---
        script_dir = os.path.dirname(__file__)
        project_root = os.path.dirname(script_dir)
        chromedriver_filename = "chromedriver.exe" if platform.system() == "Windows" else "chromedriver"
        chrome_driver_path = os.path.join(project_root, 'utils', chromedriver_filename)
        print(f"    [Selenium] 尝试使用 ChromeDriver 路径 ({platform.system()}): {chrome_driver_path}")

        # --- 初始化 WebDriver (使用 Service 对象) --- 
        print(f"    [Selenium] 初始化 WebDriver (非 Headless - 调试模式)...")
        try:
            service = Service(executable_path=chrome_driver_path)
            driver = webdriver.Chrome(service=service, options=options)
        except WebDriverException as e:
             # ... (error handling remains the same) ...
             if "executable needs to be in PATH" in str(e) or "cannot be found" in str(e):
                 print(f"    [Selenium] 错误：在路径 '{chrome_driver_path}' 找不到 chromedriver...")
             elif "'chromedriver' executable may have wrong permissions" in str(e):
                  print(f"    [Selenium] 错误：'{chrome_driver_path}' 可能权限不足...")
             else:
                  print(f"    [Selenium] 初始化 WebDriver 时出错: {e}")
             return None

        print(f"    [Selenium] 正在访问: {url}")
        driver.get(url)
        time.sleep(2)

        # --- 选择下拉框选项 (如果指定了) --- 
        if select_options:
            for selection in select_options:
                dropdown_id = selection.get("dropdown_id")
                option_value = selection.get("option_value")
                if dropdown_id and option_value:
                    try:
                        print(f"    [Selenium] 尝试在下拉框 '{dropdown_id}' 中选择值 '{option_value}'...")
                        select_element = Select(driver.find_element(By.ID, dropdown_id))
                        select_element.select_by_value(option_value)
                        print(f"      -> 已选择 '{dropdown_id}' 的值为 '{option_value}'")
                        time.sleep(1) # Wait a moment for any potential JS triggered by selection
                    except Exception as select_e:
                        print(f"    [Selenium] 选择下拉框 '{dropdown_id}' 时出错: {select_e}")

        # --- 点击按钮 (如果指定了 ID) --- 
        if click_button_id:
             try:
                 print(f"    [Selenium] 尝试查找并点击按钮 ID: {click_button_id}")
                 button = driver.find_element(By.ID, click_button_id)
                 button.click()
                 print(f"    [Selenium] 已点击按钮 ID: {click_button_id}")
                 time.sleep(1)
             except Exception as click_e:
                 print(f"    [Selenium] 点击按钮 ID '{click_button_id}' 时出错: {click_e}")
                 
        # --- 等待点击后的动态内容加载 --- 
        if wait_after_click_selector:
             print(f"    [Selenium] 等待元素选择器 '{wait_after_click_selector}' 匹配 (最多 {timeout} 秒)...")
             wait = WebDriverWait(driver, timeout)
             wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, wait_after_click_selector)))
             print(f"    [Selenium] 元素选择器 '{wait_after_click_selector}' 匹配成功。")
        else:
              print(f"    [Selenium] 未指定等待元素(点击后)，默认等待 5 秒...")
              time.sleep(5)
              
        # --- 获取页面源码 --- 
        html_source = driver.page_source
        print(f"    [Selenium] 成功获取页面源码。")
        
    except TimeoutException:
        print(f"    [Selenium] 错误：等待元素选择器 '{wait_after_click_selector}' 超时 ({timeout}秒)。页面可能未完全加载或元素不存在。")
        if driver:
             try:
                 screenshot_path = os.path.join(project_root, 'utils', 'selenium_timeout_screenshot.png')
                 driver.save_screenshot(screenshot_path)
                 print(f"    [Selenium] 已保存超时截图到: {screenshot_path}")
             except Exception as screenshot_e:
                 print(f"    [Selenium] 保存截图时出错: {screenshot_e}")
    except WebDriverException as e:
         print(f"    [Selenium] WebDriver 发生错误: {e}")
    except Exception as e:
         print(f"    [Selenium] 获取动态页面时发生未知错误: {e}")
    finally:
         if driver:
             print(f"    [Selenium] 关闭 WebDriver。")
             driver.quit()
             
    return html_source

# --- 新增：辅助函数 - 解析考试科目 ---
def parse_exam_subjects(subject_html_fragment):
    """
    尝试解析包含考试科目信息的 HTML 片段。
    输入: 一小段 HTML 字符串 (比如 <td>...</td> 的内容)
    输出: 结构化的字符串 (如 "科目代码1 科目名称1; ...") 或原始 HTML (如果解析失败)
    (需要根据实际网站 HTML 结构进行大量定制!)
    """
    if not subject_html_fragment:
        return "未知"
    try:
        subject_soup = BeautifulSoup(subject_html_fragment, 'html.parser')
        subjects = []
        items = subject_soup.find_all(['p', 'li'])
        if not items:
            plain_text = subject_soup.get_text(separator='\n', strip=True)
            items = plain_text.split('\n')
            
        for item in items:
            text = "".join(item.stripped_strings) if hasattr(item, 'stripped_strings') else str(item).strip()
            if text:
                match = re.match(r'^\s*(\d{3})\s+(.+?)\s*$', text)
                if match:
                    subjects.append(f"{match.group(1)} {match.group(2)}")
                elif len(text) > 3:
                    subjects.append(text)
                   
        if subjects:
            return "; ".join(subjects)
        else:
            fallback_text = subject_soup.get_text(separator=' ', strip=True)
            return fallback_text if fallback_text else "信息待补充"
        
    except Exception as e:
        print(f"      [!] 解析考试科目时出错: {e}。尝试返回清理后的文本。")
        # 出错时尝试返回清理后的文本
        try:
             cleaned_fallback = BeautifulSoup(subject_html_fragment, 'html.parser').get_text(separator=' ', strip=True)
             return cleaned_fallback if cleaned_fallback else "解析出错，原始信息待查"
        except Exception: # 捕获清理时可能发生的异常
             return "解析科目出错（二次清理失败）"

def parse_school_data(school_name, base_url):
    """
    解析单个学校的招生信息。
    需要针对具体学校的网站结构进行实现。
    返回一个包含该学校信息的字典，结构应与 schools.json 中的学校条目类似。
    例如：查找招生简章、专业目录、历年分数线等。
    """
    print(f"-[{school_name}] 开始处理: {base_url}")
    school_update_data = {
        "departments": [] # Initialize empty, may not be filled for dynamic sites
    }

    # --- Fetch main page --- 
    main_page_html = fetch_page(base_url)
    if not main_page_html:
        print(f"-[{school_name}] 无法获取主页内容，跳过。")
        return None
    
    soup = BeautifulSoup(main_page_html, 'html.parser')
    
    # --- School-Specific Logic --- 
    major_catalog_url = None
    score_line_urls = {} # {year: url}
    parsed_majors_by_dept = {} # {dept_name: [major_dict, ...]} # Changed name for clarity

    # --- Sichuan University (SCU) Specific Logic --- 
    if school_name == "四川大学":
        print(f"  [{school_name}] 应用四川大学特定解析逻辑...")
        # 1. Find Major Catalog Link
        major_link = soup.select_one('a[href="/sszyml/index"]') # 更精确的选择器
        if major_link:
            major_catalog_url = urljoin(base_url, major_link['href'])
            print(f"  [{school_name}] 找到专业目录链接: {major_catalog_url}")
        else:
            print(f"  [{school_name}] 未找到预期的专业目录链接。")

        # 2. Find Historical Data Link -> Find Score Line Links
        history_link = soup.select_one('a[href="/zsxx/newslist/a/ls"]') # 更精确的选择器
        if history_link:
            historical_data_url = urljoin(base_url, history_link['href'])
            print(f"  [{school_name}] 找到历年数据链接: {historical_data_url}")
            history_page_html = fetch_page(historical_data_url)
            if history_page_html:
                history_soup = BeautifulSoup(history_page_html, 'html.parser')
                print(f"    [{school_name}] 正在解析历年数据页面...")
                data_list_ul = history_soup.find('ul', class_='data-list')
                if data_list_ul:
                    for year in ["2024", "2023", "2022"]:
                        score_link_tag = data_list_ul.find('a', string=re.compile(f'{year}.*硕士.*复试.*成绩基本要求'))
                        if score_link_tag and score_link_tag.has_attr('href'):
                            score_line_urls[year] = urljoin(historical_data_url, score_link_tag['href'])
                            print(f"      [{school_name}] 找到 {year} 分数线链接: {score_line_urls[year]}")
                        else:
                            print(f"      [{school_name}] 未在数据列表中找到 {year} 分数线的链接。")
                else:
                    print(f"    [{school_name}] 未在历年数据页找到 class='data-list' 的列表。")
            else:
                 print(f"  [{school_name}] 无法获取历年数据页面内容。")
        else:
            print(f"  [{school_name}] 未找到预期的历年数据链接。")
           
        # 3. Parse Major Catalog using Selenium
        if major_catalog_url:
            print(f"  [{school_name}] 尝试使用 Selenium 访问专业目录页: {major_catalog_url}")
            # --- Select department, click search, then wait --- 
            catalog_html = fetch_dynamic_page_with_selenium(
                major_catalog_url, 
                select_options=[{"dropdown_id": "yxslist", "option_value": "304"}], # Select Computer Science
                click_button_id='searchbtn', 
                wait_after_click_selector='#datatabel tbody tr'
            ) 
            if catalog_html:
                print(f"    [{school_name}] 使用 BeautifulSoup 解析 Selenium 获取的专业目录源码...")
                catalog_soup = BeautifulSoup(catalog_html, 'html.parser')
                major_table = catalog_soup.find('table', id='datatabel')
                if major_table:
                    tbody = major_table.find('tbody')
                    if tbody:
                        major_rows = tbody.find_all('tr')
                        print(f"      [{school_name}] 在专业目录页找到 ID='datatabel' 的表格，共 {len(major_rows)} 行。开始解析...")
                        
                        # --- State variables for parsing context --- 
                        current_dept_name = "未知院系" # Default if header not found before majors
                        current_major_code = None
                        current_major_name = None
                        current_degree_type = None
                        current_study_type = None
                        current_exam_subjects = "信息待补充" # Carry forward due to rowspan
                        current_remarks = "信息待补充" # Carry forward due to rowspan
                        current_tuition_duration = ""
                        
                        for i, m_row in enumerate(major_rows):
                            m_cols = m_row.find_all('td')
                            num_cols = len(m_cols)
                            # print(f"        [Row {i+1}] Found {num_cols} columns.") # Optional debug
                            # print(f"        [Row {i+1}] HTML: {m_row.prettify()[:500]}...") # Optional debug

                            try:
                                # --- Check for Department Header Row --- 
                                if num_cols >= 1 and m_cols[0].find('h3'):
                                    dept_name_raw = m_cols[0].find('h3').text.strip()
                                    match = re.match(r'\d+\s+(.*)', dept_name_raw) # Extract name after code
                                    current_dept_name = match.group(1) if match else dept_name_raw
                                    print(f"        ---> Detected Department: '{current_dept_name}'")
                                    continue # Move to next row

                                # --- Check for Major Header Row --- 
                                col0_h4 = m_cols[0].find('h4') if num_cols > 0 else None
                                is_major_header = num_cols == 5 and col0_h4 and re.match(r'^\d{6}\s+', col0_h4.text.strip())
                                
                                if is_major_header:
                                    col0_text = col0_h4.text.strip()
                                    major_code_match = re.match(r'^(\d{6})\s+(.*)', col0_text)
                                    if major_code_match:
                                        current_major_code = major_code_match.group(1)
                                        current_major_name = major_code_match.group(2)
                                        # Reset direction-specific info for new major
                                        current_exam_subjects = "信息待补充"
                                        current_remarks = "信息待补充"
                                        current_tuition_duration = ""
                                        
                                        degree_type_raw = m_cols[4].text.strip()
                                        current_degree_type = "Academic" if "学术" in degree_type_raw else ("Professional" if "专业" in degree_type_raw else "Unknown")
                                        study_type_text = m_cols[4].text.strip() # Also check col 4 for non-full-time
                                        current_study_type = "非全日制" if "非全日制" in study_type_text else "全日制"

                                        print(f"        ---> Detected Major: Code='{current_major_code}', Name='{current_major_name}', Type='{current_degree_type}', Study='{current_study_type}'")

                                        if current_major_code in TARGET_MAJOR_CODES:
                                            print(f"          -> MATCHED TARGET MAJOR! Initializing entry.")
                                            if current_dept_name not in parsed_majors_by_dept:
                                                parsed_majors_by_dept[current_dept_name] = {}
                                            if current_major_code not in parsed_majors_by_dept[current_dept_name]:
                                                enrollment_raw = m_cols[2].text.strip()
                                                enrollment_match = re.search(r'\d+', enrollment_raw)
                                                enrollment = enrollment_match.group(0) if enrollment_match else enrollment_raw
                                                parsed_majors_by_dept[current_dept_name][current_major_code] = {
                                                    "major_code": current_major_code,
                                                    "major_name": current_major_name,
                                                    "degree_type": current_degree_type,
                                                    "study_type": current_study_type,
                                                    "enrollment": enrollment,
                                                    "exam_subjects": current_exam_subjects, # Use carried-forward value initially
                                                    "remarks": current_remarks,           # Use carried-forward value initially
                                                    "tuition_duration": current_tuition_duration,
                                                    "research_directions": [],
                                                    "score_lines": {}
                                                }
                                        else:
                                            print(f"          -> Code '{current_major_code}' not in TARGET_MAJOR_CODES. Ignoring this major and its directions.")
                                            current_major_code = None # Reset so subsequent direction rows are skipped
                                else:
                                    current_major_code = None # Match failed, reset
                                continue # Processed major header, move to next row

                                # --- Check for Direction Row --- 
                                # Must be associated with a valid *target* major code found previously
                                if num_cols == 5 and current_major_code:
                                    direction_name = m_cols[0].text.strip()
                                    advisors = m_cols[1].text.strip().replace('\n', ' ').strip()
                                    
                                    # Handle rowspan for subjects (col 3) and remarks (col 4)
                                    subjects_col = m_cols[3]
                                    remarks_col = m_cols[4]
                                    
                                    subjects_updated = False
                                    if 'display: none;' not in subjects_col.get('style', '') and subjects_col.text.strip():
                                        current_exam_subjects = parse_exam_subjects(str(subjects_col))
                                        subjects_updated = True
                                        
                                    remarks_updated = False
                                    if 'display: none;' not in remarks_col.get('style', '') and remarks_col.text.strip():
                                         current_remarks_raw = remarks_col.text.strip().replace('\n', ' ')
                                         # Try to extract tuition/duration from the full remarks
                                         tuition_match = re.search(r'学费：\s*(\d+元/生\.年)', current_remarks_raw)
                                         duration_match = re.search(r'学制：\s*(\d+\s*年)', current_remarks_raw)
                                         tuition = tuition_match.group(1) if tuition_match else ""
                                         duration = duration_match.group(1) if duration_match else ""
                                         current_tuition_duration = f"{tuition}, {duration}".strip(', ') if (tuition or duration) else ""
                                         # Store the potentially cleaned remarks text itself
                                         current_remarks = current_remarks_raw 
                                         remarks_updated = True

                                    # --- Update the Major dictionary --- 
                                    # Find the dict for the current target major
                                    major_dict = parsed_majors_by_dept.get(current_dept_name, {}).get(current_major_code)
                                    if major_dict:
                                        # Update subjects/remarks/tuition if they were found in this row
                                        if subjects_updated:
                                            major_dict['exam_subjects'] = current_exam_subjects
                                        if remarks_updated: # Update remarks and tuition based on this row's finding
                                            major_dict['remarks'] = current_remarks
                                            major_dict['tuition_duration'] = current_tuition_duration
                                            
                                        # Append the direction details
                                        major_dict['research_directions'].append({
                                            "direction_name": direction_name,
                                            "advisors": advisors
                                        })
                                        print(f"          Added Direction: '{direction_name}' to Major '{current_major_code}'")
                                    # else: Major code was target but somehow dict not initialized? Should not happen based on above logic.

                            except Exception as e:
                                print(f"        [Row {i+1}] Exception during processing: {e}")

                        # --- End of Loop --- 
                        
                    else: 
                        print(f"    [{school_name}] 在专业目录页 ID='datatabel' 的表格中未找到 <tbody>。")
                else: 
                    print(f"    [{school_name}] 未能在专业目录页找到 ID='datatabel' 的表格。")
                
                # --- Convert dict structure to list structure AFTER the loop (Rewritten) --- 
                print(f"      [{school_name}] 专业目录表格解析完成。准备构建最终数据结构...")
                final_departments_list = []
                total_target_majors_found = 0
                # parsed_majors_by_dept looks like {'CompSci': {'081200': {...}, '083500': {...}}}
                for dept_key in parsed_majors_by_dept:
                    majors_dict = parsed_majors_by_dept[dept_key] # Get the inner dict
                    
                    # Explicitly create the list of major dictionaries
                    list_of_major_dicts = []
                    for major_code_key in majors_dict:
                        list_of_major_dicts.append(majors_dict[major_code_key]) # Append the dict value

                    if list_of_major_dicts: # Only add department if it has target majors
                        dept_entry = {
                            "department_name": dept_key,
                            "majors": list_of_major_dicts # Assign the created list
                        }
                        final_departments_list.append(dept_entry)
                        total_target_majors_found += len(list_of_major_dicts)

                print(f"      -> Processed. Found {total_target_majors_found} target majors in {len(final_departments_list)} departments.")
                school_update_data['departments'] = final_departments_list
                
            else:
                print(f"  [{school_name}] Selenium 未能获取专业目录页面内容。")
               
    # --- Add elif blocks for other universities here --- 
    elif school_name == "电子科技大学":
        print(f"  [{school_name}] 需要添加电子科技大学的特定解析逻辑...")
        # TODO: Find UESTC major catalog and score line links/parsing logic based on its HTML
        pass 
    elif school_name == "西南交通大学":
        print(f"  [{school_name}] 需要添加西南交通大学的特定解析逻辑...")
        # TODO: Find SWJTU major catalog and score line links/parsing logic based on its HTML
        pass
    elif school_name == "西南财经大学":
        print(f"  [{school_name}] 需要添加西南财经大学的特定解析逻辑...")
        # TODO: Find SWUFE major catalog and score line links/parsing logic based on its HTML
        pass
    # ... add other universities as needed ...
    else:
        print(f"  [{school_name}] 未实现该学校的特定解析逻辑。")

    # --- 4. Parse Score Lines (if URLs were found) --- 
    temp_score_data = {} # Store scores temporarily {year: {category_code_type: score}}
    if score_line_urls:
        for year, url in score_line_urls.items():
            print(f"  [{school_name}] 尝试获取 {year} 分数线页面: {url}")
            score_html = fetch_page(url)
            if score_html:
                score_soup = BeautifulSoup(score_html, 'html.parser')
                try:
                    # 优先尝试查找 class='Table' 的表格 (适配 2024)
                    score_table = score_soup.find('table', class_='Table')
                    
                    # 如果找不到带 class 的表格，则查找 content-box 内的第一个 table (适配 2023, 2022)
                    if not score_table:
                        print(f"    [{school_name}] 未找到 class='Table' 的表格，尝试查找 content-box 内的第一个表格...")
                        content_box_div = score_soup.find('div', class_='content-box')
                        if content_box_div:
                            score_table = content_box_div.find('table') 
                        
                    if score_table:
                        score_rows = score_table.find_all('tr')
                        print(f"    [{school_name}] 在 {year} 分数线页找到表格，共 {len(score_rows)} 行(含表头/分隔)。开始解析...")
                        
                        is_academic_section = False
                        is_professional_section = False

                        for s_row in score_rows:
                            s_cols = s_row.find_all('td')
                            
                            # 检查是否是分隔行或标题行 (列数不足5)
                            if not s_cols or len(s_cols) < 5: 
                                # 检查是否是切换区域的标题行
                                header_text = s_row.get_text(strip=True)
                                if "学术学位" in header_text:
                                     is_academic_section = True
                                     is_professional_section = False
                                     # print(f"        切换到 学术学位 section") # Optional debug
                                     continue
                                elif "专业学位" in header_text:
                                     is_academic_section = False
                                     is_professional_section = True
                                     # print(f"        切换到 专业学位 section") # Optional debug
                                     continue
                                elif "专项计划" in header_text or "其他" in header_text: # 停止解析普通专业分数
                                     # print(f"        遇到 专项计划/其他 section，停止解析") # Optional debug
                                     break 
                                # print(f"        跳过无效/标题行: {s_row.get_text(strip=True)[:50]}...") # Optional debug
                                continue 

                            # --- 提取列数据 ---
                            # 列索引: 0-代码, 1-名称, 2-单科(<100), 3-单科(>100), 4-总分
                            try:
                                category_code = s_cols[0].text.strip()
                                category_name = s_cols[1].text.strip()
                                # 尝试提取总分，处理可能的格式问题（如包含非数字字符）
                                total_score_raw = s_cols[4].text.strip() 
                                total_score_match = re.search(r'\d+', total_score_raw) # 提取数字部分
                                total_score = total_score_match.group(0) if total_score_match else total_score_raw # 保留原始字符串以防万一

                                # 检查是否是我们关心的学科大类代码
                                if category_code in TARGET_CATEGORY_PREFIXES:
                                    # 根据当前区域判断是学硕还是专硕分数 
                                    score_type = "学硕" if is_academic_section else ("专硕" if is_professional_section else "未知类型")
                                    
                                    print(f"      [{school_name}] {year} 找到目标学科大类({score_type}): {category_code} {category_name} - 总分线: {total_score}")
                                    # Store temporarily by year and category code + type
                                    if year not in temp_score_data: temp_score_data[year] = {}
                                    temp_score_data[year][f"{category_code}_{score_type}"] = total_score 
                                    
                            except IndexError:
                                 print(f"      [{school_name}] 解析 {year} 分数线某行时列数不足或格式错误 (需要至少5列)。跳过此行: {s_row.prettify()[:100]}...")
                            except Exception as score_row_e:
                                 print(f"      [{school_name}] 解析 {year} 分数线某行时发生未知错误: {score_row_e}。跳过此行。")
                                 
                    else:
                         print(f"  [{school_name}] 在 {year} 分数线页未找到可解析的分数线表格 (尝试了 class='Table' 和 content-box 内的第一个 table)。")
                except Exception as score_e:
                    print(f"  [{school_name}] 解析 {year} 分数线页面时出错: {score_e}")
            else:
                print(f"  [{school_name}] 无法获取 {year} 分数线页面内容。")
            time.sleep(1) 
            
    # --- 5. Populate school_update_data['departments'] from parsed_majors_by_dept --- 
    # This step is now done above, after parsing the catalog for SCU.
    # We need to ensure it's also done if the SCU logic is skipped or for other universities.
    # Let's move the conversion logic outside the SCU block but keep the print inside.
    # The logic below will handle cases where parsed_majors_by_dept wasn't populated by SCU logic.
    if not school_update_data.get('departments') and parsed_majors_by_dept:
         print(f"  [{school_name}] (Non-SCU or SCU catalog failed) 构建 departments 列表...")
         school_update_data['departments'] = [
            {"department_name": dept_name, "majors": list(majors_dict.values())}
            for dept_name, majors_dict in parsed_majors_by_dept.items()
         ]
         print(f"    -> 构建完成: {len(school_update_data['departments'])} 个院系条目。")
    elif not school_update_data.get('departments'):
         # Ensure it's an empty list if nothing was parsed
         school_update_data['departments'] = [] 
         print(f"  [{school_name}] 没有解析到专业信息，departments 列表为空。")

    # --- 6. Merge temporary score data into parsed majors ---
    if temp_score_data and school_update_data.get('departments'):
        print(f"  [{school_name}] 尝试将【大类】分数线数据合并到已解析的专业中...")
        majors_updated_with_scores = 0

        # --- Remove previous DEBUG prints --- 

        for dept_index, dept in enumerate(school_update_data['departments']): 
            # dept should now correctly be a dictionary like {'department_name': ..., 'majors': [...]} 
            majors_list = dept.get('majors', []) 
            # majors_list should now correctly be a list of major dictionaries
            for major_index, major in enumerate(majors_list): 
                # major should now correctly be a dictionary
                major_code = major.get('major_code')
                if major_code:
                    score_key_prefix = ""
                    if major_code.startswith('0854'): score_key_prefix = '0854'
                    elif major_code.startswith('08'): score_key_prefix = '08'
                    
                    if score_key_prefix:
                        major_type = "专硕" if major.get('degree_type') == 'Professional' else "学硕"
                        score_key = f"{score_key_prefix}_{major_type}"
                        
                        updated_score_for_major = False
                        # Ensure score_lines exists
                        if 'score_lines' not in major: major['score_lines'] = {}
                        
                        for year, scores_by_cat_type in temp_score_data.items():
                            if score_key in scores_by_cat_type:
                                if major['score_lines'].get(year) != scores_by_cat_type[score_key]:
                                     major['score_lines'][year] = scores_by_cat_type[score_key]
                                     updated_score_for_major = True
                            # Fallback to prefix only if specific type not found and year not yet filled
                            elif score_key_prefix in scores_by_cat_type and year not in major['score_lines']:
                                 major['score_lines'][year] = scores_by_cat_type[score_key_prefix]
                                 updated_score_for_major = True
                                 
                        if updated_score_for_major:
                            majors_updated_with_scores += 1
                            # print(f"      -> 应用了分数线到 {dept['department_name']} - {major_code}") # Optional verbose print
        print(f"    -> 分数线合并尝试完成，共为 {majors_updated_with_scores} 个专业条目添加/更新了分数线信息。")

    # --- Final Step --- 
    print(f"-[{school_name}] 处理完成。提取到 {len(school_update_data.get('departments', []))} 个院系的数据 (含 {sum(len(d.get('majors',[])) for d in school_update_data.get('departments',[]))} 个目标专业)。")
    # Return data only if departments with target majors were found OR score lines were found
    return school_update_data if school_update_data.get("departments") or score_line_urls else None

def update_school_data(existing_schools_list, school_name, update_data):
    """
    将爬取到的单个学校数据(update_data)合并到现有学校列表(existing_schools_list)中。
    尝试按 院系名称 和 专业代码 进行匹配和更新。
    """
    school_entry = None
    entry_index = -1
    for i, school in enumerate(existing_schools_list):
        if school.get('name') == school_name:
            school_entry = school
            entry_index = i
            break

    if not school_entry:
        print(f"![{school_name}] 未在现有数据中找到，无法合并。")
        # 可以在这里决定是否要将 update_data 作为一个新学校添加到 existing_schools_list
        # new_school = {'name': school_name, 'id': school_name, ... , **update_data}
        # existing_schools_list.append(new_school)
        # return True # 如果添加了新学校，返回 True
        return False

    print(f"-[{school_name}] 开始合并数据...")
    merged = False
    updated_majors_count = 0
    new_majors_count = 0

    # 合并院系和专业信息
    if 'departments' in update_data:
        for dept_update in update_data['departments']:
            dept_name_update = dept_update.get('department_name')
            if not dept_name_update:
                continue # 跳过没有名称的院系数据

            # 查找现有数据中是否有同名院系
            existing_dept = next((d for d in school_entry.get('departments', []) if d.get('department_name') == dept_name_update), None)
            
            if not existing_dept:
                # 如果院系不存在，直接添加整个新院系（包括其下的专业）
                if 'departments' not in school_entry: school_entry['departments'] = []
                school_entry['departments'].append(dept_update)
                print(f"  + 添加新院系: {dept_name_update} (含 {len(dept_update.get('majors',[]))} 个专业)")
                new_majors_count += len(dept_update.get('majors',[]))
                merged = True
            else:
                # 如果院系存在，则遍历新院系下的专业，尝试更新或添加
                if 'majors' in dept_update:
                    for major_update in dept_update['majors']:
                        major_code_update = major_update.get('major_code')
                        if not major_code_update:
                            continue # 跳过没有代码的专业数据
                            
                        # 查找现有院系下是否有同代码的专业
                        existing_major = next((m for m in existing_dept.get('majors', []) if m.get('major_code') == major_code_update), None)
                        
                        if not existing_major:
                            # 专业不存在，添加新专业
                            if 'majors' not in existing_dept: existing_dept['majors'] = []
                            existing_dept['majors'].append(major_update)
                            print(f"    + 添加新专业到 {dept_name_update}: {major_code_update} {major_update.get('major_name')}")
                            new_majors_count += 1
                            merged = True
                        else:
                            # 专业存在，更新字段 (选择性更新)
                            print(f"    * 更新已存在专业: {dept_name_update} - {major_code_update} {major_update.get('major_name')}")
                            update_occurred = False
                            for key, value in major_update.items():
                                if key == 'score_lines': # 特殊处理分数线合并
                                    if isinstance(value, dict):
                                        if 'score_lines' not in existing_major: existing_major['score_lines'] = {}
                                        for year, score in value.items():
                                            if existing_major['score_lines'].get(year) != score:
                                                existing_major['score_lines'][year] = score
                                                print(f"      - 更新 {year} 分数线为: {score}")
                                                update_occurred = True
                                else:
                                    # 其他字段直接覆盖 (如果值不同)
                                    if existing_major.get(key) != value:
                                         existing_major[key] = value
                                         print(f"      - 更新字段 '{key}' 为: {str(value)[:50]}...") # 打印部分值避免过长
                                         update_occurred = True
                            if update_occurred:
                                updated_majors_count += 1
                                merged = True
                               
    # 合并其他顶层字段 (如简介)
    if update_data.get('intro') and school_entry.get('intro') != update_data['intro']:
        school_entry['intro'] = update_data['intro']
        print(f"  * 更新学校简介.")
        merged = True
        
    if merged:
        print(f"-[{school_name}] 合并完成。更新了 {updated_majors_count} 个专业的字段，添加了 {new_majors_count} 个新专业。")
        existing_schools_list[entry_index] = school_entry # 更新列表中的学校数据
        return True
    else:
        print(f"-[{school_name}] 没有数据需要合并或更新。")
        return False

def run_scraper():
    """运行爬虫的主函数"""
    print("开始运行爬虫...")
    # 加载学校列表
    schools_list = load_existing_schools()

    # 检查加载是否成功返回列表
    if not isinstance(schools_list, list):
        print("警告：现有学校数据格式错误或加载失败。将创建新的空列表。")
        schools_list = [] # Start with an empty list
    elif not schools_list:
        print("警告：现有学校数据为空。爬取结果将作为新数据保存。")

    successful_updates = 0
    for school_name, base_url in TARGET_UNIVERSITIES.items():
        update_data = parse_school_data(school_name, base_url)
        if update_data:
            # 传递 schools_list 进行更新
            if update_school_data(schools_list, school_name, update_data):
                successful_updates += 1
        else:
            print(f"未能获取或解析学校 {school_name} 的数据。")

        # 添加延时，避免请求过于频繁
        print("--- 等待 2 秒 ---")
        time.sleep(2)

    # 爬取完成后保存数据 (只有在至少成功更新了一个学校时才保存)
    if successful_updates > 0:
        print(f"共成功更新 {successful_updates} 个学校的数据，正在保存...")
        # 保存更新后的列表
        save_schools_data(schools_list)
    else:
        print("没有学校数据被成功更新，未保存文件。")
        
    print("爬虫运行结束。")

if __name__ == "__main__":
    # 可以直接运行此脚本来测试爬虫
    run_scraper()

    # Placeholder for potentially scraping other schools or data types
    print("Scraper script executed (Placeholder).") 