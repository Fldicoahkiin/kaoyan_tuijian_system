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
import csv # 导入csv模块用于导出CSV文件

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

# 爬虫输出目录
CRAWLER_DIR = os.path.join(DATA_DIR, 'crawler')
CRAWLER_RAW_DATA_FILE = os.path.join(CRAWLER_DIR, 'crawler_raw_data.json')
CRAWLER_SCHOOLS_CSV_FILE = os.path.join(CRAWLER_DIR, 'crawler_schools.csv')
CRAWLER_SUMMARY_FILE = os.path.join(CRAWLER_DIR, 'crawler_summary.json')

# 目标院校列表 (四川省内高校)
TARGET_UNIVERSITIES = {
    "四川大学": "https://yz.scu.edu.cn/",
    "电子科技大学": "https://yz.uestc.edu.cn/",
    "西南交通大学": "https://yz.swjtu.edu.cn/",
    "西南财经大学": "https://yz.swufe.edu.cn/",
    "四川师范大学": "https://yjsc.sicnu.edu.cn/",
    "成都理工大学": "https://gs.cdut.edu.cn/",
    "西南科技大学": "https://graduate.swust.edu.cn/",
    "成都信息工程大学": "https://yjs.cuit.edu.cn/",
    "西华大学": "https://yanjiusheng.xhu.edu.cn/",
    "成都大学": "https://yjsc.cdu.edu.cn/"
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

def save_crawler_raw_data(data_dict):
    """保存爬虫原始数据到JSON文件"""
    os.makedirs(CRAWLER_DIR, exist_ok=True)
    with open(CRAWLER_RAW_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=4)
    print(f"爬虫原始数据已保存到 {CRAWLER_RAW_DATA_FILE}")

def save_crawler_schools_csv(schools_info):
    """保存爬取的学校URL信息到CSV文件"""
    os.makedirs(CRAWLER_DIR, exist_ok=True)
    with open(CRAWLER_SCHOOLS_CSV_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['学校名称', '研究生院网址', '专业目录URL', '分数线URL'])
        for school in schools_info:
            writer.writerow([
                school.get('name', ''),
                school.get('url', ''),
                school.get('major_catalog_url', ''),
                school.get('score_line_url', '')
            ])
    print(f"学校URL信息已保存到 {CRAWLER_SCHOOLS_CSV_FILE}")

def save_crawler_summary(summary_data):
    """保存爬虫汇总数据到JSON文件"""
    os.makedirs(CRAWLER_DIR, exist_ok=True)
    with open(CRAWLER_SUMMARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=4)
    print(f"爬虫汇总数据已保存到 {CRAWLER_SUMMARY_FILE}")

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
        # options.add_argument('--headless') # 移除无头模式，让浏览器可见
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
        "departments": [], # Initialize empty, may not be filled for dynamic sites
        "major_catalog_url": "", # 添加专业目录URL字段
        "score_line_url": ""     # 添加分数线URL字段
    }

    # --- Fetch main page ---
    print(f"  [{school_name}] 获取主页: {base_url}")
    main_page_html = fetch_page(base_url)
    if not main_page_html:
        print(f"-[{school_name}] 无法获取主页内容，跳过。")
        return None

    soup = BeautifulSoup(main_page_html, 'html.parser')

    # Variables to store found URLs and data
    major_catalog_url = None
    score_line_urls = {} # {year: url} - Primarily for SCU
    parsed_majors_by_dept = {} # {dept_name: {major_code: major_dict}}
    yearly_score_line_urls = {} # {year: url} - Primarily for UESTC
    temp_score_data = {} # Initialize temp_score_data HERE, before school-specific blocks

    # --- School-Specific Logic ---
    if school_name == "四川大学":
        print(f"  [{school_name}] 应用四川大学特定解析逻辑...")
        # 1. Find Major Catalog Link
        major_link = soup.select_one('a[href="/sszyml/index"]') # 更精确的选择器
        if major_link:
            major_catalog_url = urljoin(base_url, major_link['href'])
            print(f"  [{school_name}] 找到专业目录链接: {major_catalog_url}")
            school_update_data["major_catalog_url"] = major_catalog_url
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
                            if year == "2024": # 保存最新年份的分数线URL
                                school_update_data["score_line_url"] = score_line_urls[year]
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
                                                    "enrollment": {"2024": enrollment, "2023": 0, "2022": 0},
                                                    "exam_subjects": current_exam_subjects, # Use carried-forward value initially
                                                    "remarks": current_remarks,           # Use carried-forward value initially
                                                    "tuition_duration": current_tuition_duration,
                                                    "research_directions": [],
                                                    "score_lines": {}
                                                }
                                        else:
                                            print(f"          -> Code '{current_major_code}' not in TARGET_MAJOR_CODES. Ignoring this major and its directions.")
                                            current_major_code = None # Reset so subsequent direction rows are skipped
                                    continue # Processed major header, move to next row

                                # --- Check for Direction Row --- 
                                # Must be associated with a valid *target* major code found previously
                                if num_cols == 5 and current_major_code in TARGET_MAJOR_CODES:
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
               
        # --- SCU Score Parsing (Moved INSIDE SCU block) ---
        if score_line_urls:
            print(f"  [{school_name}] (SCU) 开始解析分数线...")
            for year, url in score_line_urls.items():
                print(f"    [{school_name}] 尝试获取 {year} 分数线页面: {url}")
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
                                        continue
                                    elif "专业学位" in header_text:
                                        is_academic_section = False
                                        is_professional_section = True
                                        continue
                                    elif "专项计划" in header_text or "其他" in header_text:
                                        break
                                    continue

                                # --- 提取列数据 ---
                                try:
                                    category_code = s_cols[0].text.strip()
                                    category_name = s_cols[1].text.strip()
                                    total_score_raw = s_cols[4].text.strip()
                                    total_score_match = re.search(r'\d+', total_score_raw)
                                    total_score = total_score_match.group(0) if total_score_match else total_score_raw

                                    if category_code in TARGET_CATEGORY_PREFIXES:
                                        score_type = "学硕" if is_academic_section else ("专硕" if is_professional_section else "未知类型")
                                        print(f"      [{school_name}] {year} 找到目标学科大类({score_type}): {category_code} {category_name} - 总分线: {total_score}")
                                        if year not in temp_score_data: temp_score_data[year] = {}
                                        temp_score_data[year][f"{category_code}_{score_type}"] = total_score

                                except IndexError:
                                    print(f"      [{school_name}] 解析 {year} 分数线某行时列数不足或格式错误 (需要至少5列)。跳过此行: {s_row.prettify()[:100]}...")
                                except Exception as score_row_e:
                                    print(f"      [{school_name}] 解析 {year} 分数线某行时发生未知错误: {score_row_e}。跳过此行。")

                        else:
                            print(f"  [{school_name}] 在 {year} 分数线页未找到可解析的分数线表格。")
                    except Exception as score_e:
                        print(f"  [{school_name}] 解析 {year} 分数线页面时出错: {score_e}")
                else:
                    print(f"  [{school_name}] 无法获取 {year} 分数线页面内容。")
                time.sleep(1)
        else:
             print(f"  [{school_name}] 未找到分数线链接，跳过分数线解析。")

    elif school_name == "电子科技大学":
        print(f"  [{school_name}] 应用电子科技大学特定解析逻辑...")
        uestc_major_catalog_page_url = None # Page listing different years/catalogs
        uestc_score_line_page_url = None # Page listing links to scores per year
        temp_score_data = {} # Initialize temp_score_data HERE, before school-specific blocks

        # Find the main page links
        try:
            # Look for "专业目录" link - might be relative
            catalog_link_tag = soup.find('a', string=re.compile(r'\s*专业目录\s*')) 
            if catalog_link_tag and catalog_link_tag.has_attr('href'):
                uestc_major_catalog_page_url = urljoin(base_url, catalog_link_tag['href'])
                print(f"    [{school_name}] 找到专业目录主链接: {uestc_major_catalog_page_url}")
            else:
                 print(f"    [{school_name}] 未在主页找到'专业目录'链接。")

            # Look for "历年分数" link - might be relative (trying broader search)
            score_link_tag = soup.find('a', string=re.compile(r'(分数线|历年分数)')) # Broader search
            if score_link_tag and score_link_tag.has_attr('href'):
                 uestc_score_line_page_url = urljoin(base_url, score_link_tag['href'])
                 print(f"    [{school_name}] 找到历年分数/分数线主链接: {uestc_score_line_page_url}")
            else:
                 print(f"    [{school_name}] 未在主页找到'历年分数'或'分数线'链接。")
        except Exception as link_find_e:
             print(f"    [{school_name}] 在主页查找链接时出错: {link_find_e}")

        # --- NEW: Fetch and parse the Score Line Page to find links per year --- (Finding links part)
        yearly_score_line_urls = {} # Initialized earlier
        if uestc_score_line_page_url:
            print(f"    [{school_name}] 尝试获取历年分数线入口页: {uestc_score_line_page_url}")
            score_index_html = fetch_page(uestc_score_line_page_url)
            if score_index_html:
                score_index_soup = BeautifulSoup(score_index_html, 'html.parser')
                # Find the relevant container for links (adjust selector if needed)
                # Example: Look for a div with class 'winstyle56972', then links inside
                # --- Updated Selector: Look for a specific div/ul structure --- 
                # Try finding a common container ID or class first
                link_container = score_index_soup.find('div', id='news_list') # Hypothesis 1: div with id='news_list'
                if not link_container:
                    # Fallback: Look for a common list class often used in these CMS
                    link_container = score_index_soup.find('ul', class_='news_list') # Hypothesis 2: ul with class='news_list'
                if not link_container:
                    # Fallback: Look for the main content div
                    link_container = score_index_soup.find('div', id=re.compile(r'vsb_content')) # Hypothesis 3: main content div
                
                if link_container:
                    print(f"      [{school_name}] 在分数线入口页找到初步容器 (Selector: {link_container.name}#{link_container.get('id', '')}.{link_container.get('class', [])})...")

                    # --- Refined: Try finding a UL inside the container first --- 
                    actual_list_container = link_container.find('ul')
                    if actual_list_container:
                        print(f"        -> Found UL inside the container. Using UL as link source.")
                        link_source = actual_list_container
                    else:
                        print(f"        -> Did not find UL inside the container. Using the container itself as link source.")
                        link_source = link_container # Fallback to the original container

                    # --- Find ALL links within the determined source ---
                    all_links_in_source = link_source.find_all('a', href=True) # Find links within the UL or the container
                    print(f"        -> Found {len(all_links_in_source)} total links with href within the source. Checking texts...")

                    found_years = set()
                    for link_tag in all_links_in_source:
                        link_text = link_tag.text.strip()
                        link_href = link_tag.get('href')

                        # Check if link text EXACTLY matches the year
                        for year in ["2024", "2023", "2022"]:
                            if link_text == year:
                                if year not in found_years: # Take the first match for each year
                                    url = urljoin(uestc_score_line_page_url, link_href)
                                    yearly_score_line_urls[year] = url
                                    print(f"        [{school_name}] 找到 {year} 分数线链接: {url} (Text: '{link_text}')")
                                    found_years.add(year)
                                    break # Move to next link once a year is found

                    # Check which years were not found
                    for year in ["2024", "2023", "2022"]:
                        if year not in found_years:
                            print(f"        [{school_name}] 未在容器内的链接中找到匹配 {year} 和关键词（分数线/复试线/基本要求）的链接。")

                else:
                    print(f"      [{school_name}] 在分数线入口页未能找到初步链接容器 (尝试了多种选择器)。")
            else:
                print(f"    [{school_name}] 无法获取历年分数线入口页面内容。")

        # --- UESTC Score Parsing (Moved INSIDE UESTC block) ---
        if yearly_score_line_urls:
            print(f"  [{school_name}] (UESTC) 开始解析分数线...")
            for year, url in yearly_score_line_urls.items():
                print(f"    [{school_name}] 尝试获取 {year} 分数线页面: {url}")
                score_html = fetch_page(url)
                if score_html:
                    score_soup = BeautifulSoup(score_html, 'html.parser')
                    try:
                        # Find the main content area
                        content_div = score_soup.find('div', id=re.compile(r'vsb_content'))
                        if not content_div:
                            content_div = score_soup.find('div', class_='v_news_content')
                        if not content_div:
                            content_div = score_soup.find('div', class_=re.compile(r'(content|main|article)'))

                        if content_div:
                            score_tables = content_div.find_all('table')
                            print(f"      [{school_name}] 在 {year} 分数线页内容区域找到 {len(score_tables)} 个表格。尝试解析...")

                            if not score_tables:
                                print(f"        [{school_name}] 未在内容区域找到 <table>。尝试直接解析内容文本...")
                                paragraphs = content_div.find_all('p')
                                for p in paragraphs:
                                    text = p.get_text(strip=True)
                                    # Regex needs verification!
                                    score_match = re.search(r'(工学)\s*\[?(08)?.*?不低于?(\d{3,})\s*分', text)
                                    if score_match:
                                        category_name, category_code, score = score_match.groups()
                                        print(f"          [{school_name}] {year} 从文本找到目标({category_name}): {category_code} - 分数线: {score}")
                                        if year not in temp_score_data: temp_score_data[year] = {}
                                        temp_score_data[year][category_code] = score # Store by code

                                    score_match_prof = re.search(r'(电子信息)\s*\[?(0854)?.*?不低于?(\d{3,})\s*分', text)
                                    if score_match_prof:
                                        category_name, category_code, score = score_match_prof.groups()
                                        print(f"          [{school_name}] {year} 从文本找到目标({category_name}): {category_code} - 分数线: {score}")
                                        if year not in temp_score_data: temp_score_data[year] = {}
                                        temp_score_data[year][category_code] = score # Store by code
                            else:
                                # Parse the found table(s)
                                # --- Refined Table Parsing for UESTC --- 
                                score_table = content_div.find('table') # Find the first table
                                if score_table:
                                    print(f"      [{school_name}] 在 {year} 分数线页内容区域找到表格 1。开始解析...")
                                    score_rows = score_table.find_all('tr')
                                    current_degree_type = "未知" # Track 学术/专业
                                    header_skipped = False

                                    for r_idx, s_row in enumerate(score_rows):
                                        cols = s_row.find_all('td')
                                        if not cols: continue # Skip rows without <td> (likely header with <th>)

                                        col_texts = [col.get_text(strip=True) for col in cols]

                                        # Check and update degree type based on first column
                                        first_data_col_idx = 0
                                        if cols[0].has_attr('rowspan'):
                                            first_col_text = col_texts[0]
                                            if "学术学位" in first_col_text:
                                                current_degree_type = "学硕"
                                                continue 
                                            elif "专业学位" in first_col_text:
                                                current_degree_type = "专硕"
                                                continue 
                                            else:
                                                continue
                                        else:
                                            first_data_col_idx = 0

                                        # --- Extract Data from relevant columns ---
                                        if len(col_texts) > first_data_col_idx + 1: 
                                            subject_text = col_texts[first_data_col_idx] 
                                            total_score_text = col_texts[-1] 

                                            category_code = ""
                                            code_match = re.match(r'^(0854|08)', subject_text) # Match 0854 first
                                            if code_match:
                                                category_code = code_match.group(1)

                                            score_match = re.search(r'^(\d{3,})$', total_score_text)
                                            score = score_match.group(1) if score_match else None

                                            if category_code in TARGET_CATEGORY_PREFIXES and score:
                                                print(f"            [{school_name}] {year} ({current_degree_type}) 从表格找到目标: {category_code} ({subject_text}) - 总分线: {score}")
                                                if year not in temp_score_data: temp_score_data[year] = {}
                                                temp_score_data[year][category_code] = score
                                        # else: Not enough columns or other issue, skip row

                                else:
                                    # This else corresponds to the outer `if score_table:`
                                    print(f"      [{school_name}] 在 {year} 分数线页内容区域未找到表格。")
                            # --- End of Refined Table Parsing ---
                        
                        else:
                            print(f"      [{school_name}] 在 {year} 分数线页未找到主要内容区域。")
                    except Exception as score_e:
                        print(f"    [{school_name}] 解析 {year} UESTC 分数线页面时出错: {score_e}")
                else:
                    print(f"    [{school_name}] 无法获取 {year} UESTC 分数线页面内容。")
                time.sleep(1)

        # --- Fetch and parse the Major Catalog Page (Keep this after score parsing attempt) ---
        if uestc_major_catalog_page_url:
            # ... existing UESTC Selenium logic to populate parsed_majors_by_dept ...
            latest_major_catalog_url = uestc_major_catalog_page_url # Assign here if needed
            print(f"    [{school_name}] 将找到的目录链接视为最新目录页: {latest_major_catalog_url}")
            # UESTC uses ZTree and iframe, requires specific interaction
            driver = None # Initialize driver variable
            try:
                # --- Configure WebDriver (copied from fetch_dynamic_page_with_selenium for direct use) ---
                options = webdriver.ChromeOptions()
                # options.add_argument('--headless') # Keep browser visible as requested
                options.add_argument('--disable-gpu')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument("user-agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'")

                script_dir = os.path.dirname(__file__)
                project_root = os.path.dirname(script_dir)
                chromedriver_filename = "chromedriver.exe" if platform.system() == "Windows" else "chromedriver"
                chrome_driver_path = os.path.join(project_root, 'utils', chromedriver_filename)
                service = Service(executable_path=chrome_driver_path)
                print(f"      [Selenium] 初始化 WebDriver (目标: UESTC 专业目录)..." )
                driver = webdriver.Chrome(service=service, options=options)

                print(f"      [Selenium] 正在访问主目录页: {latest_major_catalog_url}")
                driver.get(latest_major_catalog_url)

                # 1. Wait for ZTree nodes to load
                print(f"      [Selenium] 等待 ZTree 院系列表加载 ('#zsml-dept-tree li a')..." )
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#zsml-dept-tree li a")))
                print(f"      [Selenium] ZTree 加载完成。查找目标院系..." )

                # 2. Find target department links
                print(f"        --- Printing all found ZTree node links ---") # DEBUG
                department_links_to_click = []
                all_dept_links = driver.find_elements(By.CSS_SELECTOR, "#zsml-dept-tree li a")
                for link in all_dept_links:
                    link_text = link.text.strip()
                    print(f"          - Found node: {link_text}") # DEBUG Print all links
                    # Check if the link is likely a department (might have child `ul`)
                    parent_li = link.find_element(By.XPATH, "./ancestor::li[1]")
                    is_parent_node = len(parent_li.find_elements(By.XPATH, "./ul")) > 0
                    if is_parent_node:
                         print(f"            (Is department node: Yes)") # DEBUG
                    else:
                         print(f"            (Is department node: No - likely a major/direction)") # DEBUG

                print(f"        --- End of ZTree node links ---") # DEBUG

                # Define keywords AFTER printing, using exact names from log
                target_dept_keywords = ["008 计算机科学与工程学院", "009 信息与软件工程学院"] # Use exact names from log
                print(f"        --- Searching for keywords: {target_dept_keywords} ---")

                # Re-iterate to find the actual targets based on keywords
                for link in all_dept_links:
                    link_text = link.text.strip()
                    # Simpler check: Just check if link text contains keywords (removed unreliable is_parent_node check)
                    if any(keyword in link_text for keyword in target_dept_keywords):
                        print(f"        -> 找到目标院系链接: {link_text}" )
                        department_links_to_click.append(link) # Store the WebElement

                if not department_links_to_click:
                     print(f"      [Selenium] 未找到包含关键字 {target_dept_keywords} 的院系链接。" )

                # 3. Iterate through found departments, click, switch to iframe, parse
                for dept_link_element in department_links_to_click:
                    dept_name = dept_link_element.text.strip()
                    # Extract name more robustly (remove code if present)
                    dept_name_match = re.match(r'\d*\s*(.*)', dept_name)
                    dept_name_clean = dept_name_match.group(1) if dept_name_match else dept_name
                    print(f"      [Selenium] 点击院系: '{dept_name_clean}'" )
                    try:
                        dept_link_element.click()
                        # Add a small delay for JS execution after click
                        time.sleep(2)

                        # 4. Wait for iframe and switch to it
                        print(f"        [Selenium] 等待并切换到 iframe ('iframeContent')..." )
                        WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "iframeContent")))
                        print(f"        [Selenium] 已切换到 iframe。等待内容加载 (查找 table)..." )

                        # 5. Wait for content inside iframe (e.g., a table)
                        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
                        print(f"        [Selenium] Iframe 内表格已加载。获取源码..." )

                        # 6. Get iframe source and parse
                        iframe_html = driver.page_source
                        iframe_soup = BeautifulSoup(iframe_html, 'html.parser')

                        # --- UESTC iframe parsing logic --- 
                        major_table_in_iframe = iframe_soup.find('table') # Find table inside iframe
                        if major_table_in_iframe:
                            print(f"          [Parser] 在 '{dept_name_clean}' 的 iframe 中找到表格。开始解析行...")
                            rows = major_table_in_iframe.find_all('tr') # Define rows HERE
                            print(f"            -> 表格共 {len(rows)} 行。")

                            # --- Corrected UESTC iframe parsing logic (inside the if block) --- 
                            for r_idx, row in enumerate(rows):
                                # Keep debug prints (commented out)
                                # if r_idx < 5:
                                #     print(f"              [Row {r_idx+1} Raw HTML]: {str(row)[:300]}...")
                                #     cols_debug = row.find_all(['td', 'th'])
                                #     col_texts = [col.get_text(strip=True) for col in cols_debug]
                                #     print(f"              [Row {r_idx+1} Cells Text]: {col_texts}")

                                cols = row.find_all('td')
                                num_cols = len(cols)

                                # Skip header rows
                                if not cols or row.find('th'):
                                    # print(f"            Skipping header row {r_idx+1}") # Optional debug
                                    continue

                                # Expecting: Code, Name, Enrollment in first 3 cols
                                if num_cols >= 3:
                                    major_code_raw = cols[0].text.strip()
                                    major_code_match = re.match(r'^(\d{6})\s*', major_code_raw)
                                    if major_code_match:
                                        major_code = major_code_match.group(1) # Use this variable

                                        if major_code in TARGET_MAJOR_CODES:
                                            major_name = cols[1].text.strip() # Col 1: Name
                                            enrollment = cols[2].text.strip() # Col 2: Enrollment

                                            # --- Infer types (Educated Guess) ---
                                            degree_type = "Professional" if major_code.startswith("0854") else "Academic"
                                            study_type = "全日制" # Default assumption

                                            # --- Fields not available in this table view ---
                                            exam_subjects = "信息待补充 (需点击查看)"
                                            remarks = "信息待补充 (需点击查看)"
                                            tuition_duration = ""
                                            research_directions = []

                                            print(f"              MATCHED TARGET MAJOR: Code={major_code}, Name={major_name}, Dept={dept_name_clean}, Enrollment={enrollment}, Type={degree_type}/{study_type}" )

                                            # Store major data
                                            if dept_name_clean not in parsed_majors_by_dept:
                                                parsed_majors_by_dept[dept_name_clean] = {}
                                            if major_code not in parsed_majors_by_dept[dept_name_clean]:
                                                parsed_majors_by_dept[dept_name_clean][major_code] = { # Use major_code as key
                                                     "major_code": major_code,
                                                     "major_name": major_name,
                                                     "degree_type": degree_type, # Inferred
                                                     "study_type": study_type,   # Inferred
                                                     "enrollment": enrollment,
                                                     "exam_subjects": exam_subjects,
                                                     "remarks": remarks,
                                                     "tuition_duration": tuition_duration, # Use correct placeholder
                                                     "research_directions": research_directions,
                                                     "score_lines": {}
                                                 }
                                        # else: Major already processed or code not target
                                    # else: Row doesn't start with 6-digit code
                                # else: Row has less than 3 columns

                            # --- End of row processing loop ---
                        else:
                             print(f"          [Parser] 在 '{dept_name_clean}' 的 iframe 中未找到 <table> 元素。" )

                        # 7. Switch back to default content
                        print(f"        [Selenium] 处理完 iframe，切换回主页面。" )
                        driver.switch_to.default_content()
                        # Wait a bit before clicking the next department if any
                        time.sleep(1)

                    except TimeoutException:
                         print(f"        [Selenium] 处理院系 '{dept_name_clean}' 时发生超时 (等待 iframe 或其内容)。" )
                         driver.switch_to.default_content() # Ensure switch back on error
                    except Exception as e_iframe:
                         print(f"        [Selenium/Parser] 处理院系 '{dept_name_clean}' 时发生错误: {e_iframe}" )
                         try: # Attempt to switch back even if error occurred
                             driver.switch_to.default_content()
                         except Exception as switch_err:
                             print(f"          [!] Error switching back from iframe: {switch_err}" )

            except WebDriverException as e_wd:
                # Handle WebDriver specific errors (like chromedriver path)
                print(f"    [Selenium] WebDriver 初始化或操作时出错: {e_wd}" )
            except Exception as e_main:
                print(f"    [Selenium] 获取或处理 UESTC 专业目录时发生未知错误: {e_main}" )
            finally:
                if driver:
                    print(f"      [Selenium] 关闭 WebDriver。" )
                    driver.quit()

            # --- Convert parsed data to final structure --- 
            if parsed_majors_by_dept:
                print(f"      [{school_name}] UESTC 专业目录解析完成。准备构建最终数据结构..." )
                # Build the final list structure for school_update_data['departments']
                final_departments_list = []
                total_target_majors_found = 0
                for dept_key, majors_inner_dict in parsed_majors_by_dept.items():
                    list_of_major_dicts = list(majors_inner_dict.values())
                    if list_of_major_dicts: # Only add department if it has target majors
                        dept_entry = {
                            "department_name": dept_key,
                            "majors": list_of_major_dicts
                        }
                        final_departments_list.append(dept_entry)
                        total_target_majors_found += len(list_of_major_dicts)
                print(f"        -> Processed. Found {total_target_majors_found} target majors in {len(final_departments_list)} departments for UESTC." )
                school_update_data['departments'] = final_departments_list

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

    # --- 5. Populate school_update_data['departments'] from parsed_majors_by_dept --- 
    # This step needs to run AFTER school-specific logic might populate parsed_majors_by_dept
    # Check if 'departments' key was already populated (e.g., by SCU logic)
    if not school_update_data.get('departments') and parsed_majors_by_dept:
         print(f"  [{school_name}] 构建 departments 列表 from parsed_majors_by_dept...")
         school_update_data['departments'] = [
            {"department_name": dept_name, "majors": list(majors_dict.values())}
            for dept_name, majors_dict in parsed_majors_by_dept.items()
         ]
         print(f"    -> 构建完成: {len(school_update_data['departments'])} 个院系条目。")
    elif not school_update_data.get('departments'):
         # Ensure it's an empty list if nothing was parsed and it wasn't initialized
         school_update_data['departments'] = []

    # --- 6. Merge temporary score data into parsed majors ---
    if temp_score_data and school_update_data.get('departments'):
        print(f"  [{school_name}] 尝试将【大类】分数线数据合并到已解析的专业中...")
        majors_updated_with_scores = 0

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
                            # UESTC stores by code only in temp_score_data, so direct key match needed
                            elif score_key_prefix in scores_by_cat_type and year not in major['score_lines']:
                                 major['score_lines'][year] = scores_by_cat_type[score_key_prefix]
                                 updated_score_for_major = True
                                 
                        if updated_score_for_major:
                            majors_updated_with_scores += 1
        print(f"    -> 分数线合并尝试完成，共为 {majors_updated_with_scores} 个专业条目添加/更新了分数线信息。")

    # --- Final Step --- 
    print(f"-[{school_name}] 处理完成。提取到 {len(school_update_data.get('departments', []))} 个院系的数据 (含 {sum(len(d.get('majors',[])) for d in school_update_data.get('departments',[]))} 个目标专业)。")
    # Return data only if departments with target majors were found OR score lines were found
    return school_update_data if school_update_data.get("departments") or temp_score_data else None

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
    updated_fields_count = 0 # New counter for updated fields
    new_dept_count = 0 # New counter for new departments

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
                new_dept_majors = len(dept_update.get('majors',[]))
                print(f"  + 添加新院系: {dept_name_update} (含 {new_dept_majors} 个专业)")
                new_majors_count += new_dept_majors # Count majors in the new dept
                new_dept_count += 1
                merged = True # Set merged flag
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
                            merged = True # Set merged flag
                        else:
                            # 专业存在，更新字段 (选择性更新)
                            # print(f"    * 检查已存在专业: {dept_name_update} - {major_code_update} {major_update.get('major_name')}") # Change log level
                            major_updated_flag = False # Flag for this specific major
                            for key, value in major_update.items():
                                field_updated_flag = False # Flag for this specific field
                                if key == 'score_lines': # 特殊处理分数线合并
                                    if isinstance(value, dict):
                                        if 'score_lines' not in existing_major: existing_major['score_lines'] = {}
                                        for year, score in value.items():
                                            # Update if year not present or score is different
                                            if existing_major['score_lines'].get(year) != score:
                                                existing_major['score_lines'][year] = score
                                                print(f"      - 更新 {major_code_update} 的 {year} 分数线为: {score}")
                                                field_updated_flag = True
                                else:
                                    # 其他字段直接覆盖 (如果值不同 or 键不存在)
                                    if key not in existing_major or existing_major.get(key) != value:
                                         existing_major[key] = value
                                         # Avoid printing very long values like remarks or subjects entirely
                                         value_str = str(value)
                                         print(f"      - 更新 {major_code_update} 的字段 '{key}' 为: {value_str[:70]}{'...' if len(value_str) > 70 else ''}")
                                         field_updated_flag = True

                                if field_updated_flag:
                                    updated_fields_count += 1
                                    major_updated_flag = True
                                    merged = True # Set merged flag if ANY field was updated

                            if major_updated_flag:
                                updated_majors_count += 1 # Count majors that had at least one field updated
                                # print(f"      -> 专业 {major_code_update} 有字段被更新。") # Optional detail

    # 合并其他顶层字段 (如简介) - 示例，当前未爬取简介
    # if update_data.get('intro') and school_entry.get('intro') != update_data['intro']:
    #     school_entry['intro'] = update_data['intro']
    #     print(f"  * 更新学校简介.")
    #     merged = True
    #     updated_fields_count += 1 # Count top-level field updates too

    if merged:
        summary_parts = []
        if new_dept_count > 0: summary_parts.append(f"添加 {new_dept_count} 个新院系")
        if new_majors_count > 0: summary_parts.append(f"添加 {new_majors_count} 个新专业")
        if updated_majors_count > 0: summary_parts.append(f"更新 {updated_majors_count} 个已有专业的 {updated_fields_count} 个字段")
        elif updated_fields_count > 0: summary_parts.append(f"更新 {updated_fields_count} 个字段") # Handle case where only top-level fields updated

        summary = ", ".join(summary_parts) if summary_parts else "数据已合并 (无明显变化)"
        print(f"-[{school_name}] 合并完成。{summary}。")
        existing_schools_list[entry_index] = school_entry # 更新列表中的学校数据
        return True
    else:
        print(f"-[{school_name}] 检查完成，未发现需要合并或更新的数据。")
        return False

def run_scraper():
    """运行爬虫的主函数"""
    print("开始运行爬虫...")
    # 创建爬虫输出目录
    os.makedirs(CRAWLER_DIR, exist_ok=True)

    # 加载学校列表
    schools_list = load_existing_schools()

    # 检查加载是否成功返回列表
    if not isinstance(schools_list, list):
        print("警告：现有学校数据格式错误或加载失败。将创建新的空列表。")
        schools_list = [] # Start with an empty list
    elif not schools_list:
        print("警告：现有学校数据为空。爬取结果将作为新数据保存。")

    # 用于保存爬虫原始数据
    raw_crawler_data = {}
    # 用于保存学校URL信息
    schools_info = []
    # 用于保存爬虫汇总数据
    summary_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target_universities": list(TARGET_UNIVERSITIES.keys()),
        "target_major_codes": list(TARGET_MAJOR_CODES),
        "schools_processed": 0,
        "schools_updated": 0,
        "total_departments_found": 0,
        "total_majors_found": 0
    }

    successful_updates = 0
    for school_name, base_url in TARGET_UNIVERSITIES.items():
        # 记录学校基本URL信息
        school_info = {
            "name": school_name,
            "url": base_url,
            "major_catalog_url": "",
            "score_line_url": ""
        }
        schools_info.append(school_info)
        
        # 爬取学校数据
        update_data = parse_school_data(school_name, base_url)
        if update_data:
            # 更新学校URL信息
            for i, info in enumerate(schools_info):
                if info["name"] == school_name:
                    if "major_catalog_url" in update_data:
                        schools_info[i]["major_catalog_url"] = update_data["major_catalog_url"]
                    if "score_line_url" in update_data:
                        schools_info[i]["score_line_url"] = update_data["score_line_url"]
                    break
            
            # 保存原始爬取数据
            raw_crawler_data[school_name] = update_data
            
            # 更新汇总统计
            summary_data["schools_processed"] += 1
            summary_data["total_departments_found"] += len(update_data.get("departments", []))
            total_majors = sum(len(dept.get("majors", [])) for dept in update_data.get("departments", []))
            summary_data["total_majors_found"] += total_majors
            
            # 传递 schools_list 进行更新
            if update_school_data(schools_list, school_name, update_data):
                successful_updates += 1
                summary_data["schools_updated"] += 1
        else:
            print(f"未能获取或解析学校 {school_name} 的数据。")

        # 添加延时，避免请求过于频繁
        print("--- 等待 2 秒 ---")
        time.sleep(2)

    # 保存爬虫数据
    save_crawler_raw_data(raw_crawler_data)
    save_crawler_schools_csv(schools_info)
    save_crawler_summary(summary_data)

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