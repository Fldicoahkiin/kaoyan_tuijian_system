# Placeholder for web scraping functionalities

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re # 导入 re 用于后续更复杂的数据提取
from urllib.parse import urljoin, quote # quote for filename cleaning
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import platform # 导入 platform 模块用于 OS 检测
import csv # 导入csv模块用于导出CSV文件
from datetime import datetime

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

# 数据保存路径
DATA_DIR = os.path.join(os.path.dirname(__file__), '../data')
SCHOOLS_FILE = os.path.join(DATA_DIR, 'schools.json')

# 爬虫输出目录
CRAWLER_DIR = os.path.join(DATA_DIR, 'crawler')
CRAWLER_RAW_DATA_FILE = os.path.join(CRAWLER_DIR, 'crawler_raw_data.json')
CRAWLER_SCHOOLS_CSV_FILE = os.path.join(CRAWLER_DIR, 'crawler_schools.csv')
CRAWLER_SUMMARY_FILE = os.path.join(CRAWLER_DIR, 'crawler_summary.json')

# --- 爬虫HTML调试日志目录 ---
HTML_DEBUG_DIR = os.path.join(CRAWLER_DIR, 'html_debug_logs')
os.makedirs(HTML_DEBUG_DIR, exist_ok=True) # 确保目录存在

ERROR_LOG_DIR = os.path.join(CRAWLER_DIR, 'error_logs')
os.makedirs(ERROR_LOG_DIR, exist_ok=True)

# --- Global Configuration & Constants ---
# (保持原有常量定义)
# ... (其他常量)
USE_HEADLESS_BROWSER = False # True for production, False for debugging to see browser UI
REQUEST_TIMEOUT = 30 # seconds for requests
SELENIUM_TIMEOUT = 30 # seconds for Selenium explicit waits
RETRY_ATTEMPTS = 2
RETRY_DELAY = 5 # seconds

# --- TARGET_UNIVERSITIES Definition ---
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

# --- Data Loading and Saving Functions ---
def load_existing_schools():
    if os.path.exists(SCHOOLS_FILE):
        with open(SCHOOLS_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                print(f"Error: 无法解析 {SCHOOLS_FILE}")
                return []
    return []

def save_schools_data(data_list):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCHOOLS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data_list, f, ensure_ascii=False, indent=4)
    print(f"数据已保存到 {SCHOOLS_FILE}")

def save_crawler_raw_data(data_dict):
    os.makedirs(CRAWLER_DIR, exist_ok=True)
    with open(CRAWLER_RAW_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=4)
    print(f"爬虫原始数据已保存到 {CRAWLER_RAW_DATA_FILE}")

def save_crawler_schools_csv(schools_info):
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
    os.makedirs(CRAWLER_DIR, exist_ok=True)
    with open(CRAWLER_SUMMARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=4)
    print(f"爬虫汇总数据已保存到 {CRAWLER_SUMMARY_FILE}")

# --- Generic Link Finder ---
def find_generic_link(soup, base_url, keywords):
    if not soup: return None
    for keyword in keywords:
        link_tags = soup.find_all('a', string=re.compile(r'^\\s*' + re.escape(keyword) + r'\\s*$'), href=True)
        if not link_tags:
            link_tags = soup.find_all('a', string=re.compile(re.escape(keyword)), href=True)
        for link_tag in link_tags:
            href = link_tag.get('href')
            if href and not href.startswith(('#', 'javascript:')) and ('.' in href.split('/')[-1] or href.endswith('/') or 'id=' in href or 'newslist' in href or 'category' in href or 'list' in href or 'article' in href):
                return urljoin(base_url, href)
    return None

# --- Exam Subjects Parser ---
def parse_exam_subjects(subject_html_fragment):
    if not subject_html_fragment: return "未知"
    try:
        subject_soup = BeautifulSoup(str(subject_html_fragment), 'html.parser')
        subjects = []
        
        li_items = subject_soup.find_all('li')
        if li_items:
            for li in li_items:
                text = li.get_text(strip=True)
                if text and (re.match(r'^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]\\s*\\d{3}', text) or re.match(r'^\\(\\d+\\)\\s*\\d{3}', text)):
                    subjects.append(text)
            if subjects: return "; ".join(subjects)

        p_tags = subject_soup.find_all('p')
        if p_tags:
            for p_tag in p_tags:
                text = p_tag.get_text(strip=True)
                if text:
                    match = re.match(r'^\\s*([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]\\s*\\d{3})\\s+(.+?)\\s*$', text) or \
                              re.match(r'^\\s*(\\(\\d+\\)|\\d{3})\\s+(.+?)\\s*$', text)
                    if match: subjects.append(f"{match.group(1)} {match.group(2).strip()}")
                    elif len(text) > 3 and not text.startswith(("注：", "备注：")): subjects.append(text.strip())
        else:
            td_content_str = str(subject_html_fragment)
            cleaned_content = BeautifulSoup(td_content_str.replace('<br>', '\\n').replace('<br/>', '\\n').replace('<br />', '\\n'), 'html.parser').get_text(separator='\\n')
            items = [item.strip() for item in cleaned_content.split('\\n') if item.strip()]
            for text in items:
                if text:
                    match = re.match(r'^\\s*([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]\\s*\\d{3})\\s+(.+?)\\s*$', text) or \
                              re.match(r'^\\s*(\\(\\d+\\)|\\d{3})\\s+(.+?)\\s*$', text)
                    if match: subjects.append(f"{match.group(1)} {match.group(2).strip()}")
                    elif len(text) > 3 and not text.startswith(("注：", "备注：")): subjects.append(text.strip())
        
        if subjects: return "; ".join(subjects)
        else: 
            fallback_text = BeautifulSoup(str(subject_html_fragment), 'html.parser').get_text(separator=' ', strip=True)
            return fallback_text if fallback_text else "信息待补充"
            
    except Exception as e:
        print(f"      [!] 解析考试科目时出错: {e}。尝试返回清理后的文本。")
        try:
             cleaned_fallback = BeautifulSoup(str(subject_html_fragment), 'html.parser').get_text(separator=' ', strip=True)
             return cleaned_fallback if cleaned_fallback else "解析出错，原始信息待查"
        except Exception: return "解析科目出错（二次清理失败）"

def save_html_debug_log(html_content, school_name, page_type_suffix, timestamp, url="N/A", page_specific_detail=""):
    try:
        # Sanitize page_specific_detail for filename
        sane_detail = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in page_specific_detail).rstrip()
        detail_suffix = f"_{sane_detail}" if sane_detail else ""
        
        # Sanitize school_name
        sane_school_name = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in school_name).rstrip()

        # 修改后的文件名格式 (去掉了timestamp)
        file_name = f"{sane_school_name}_{page_type_suffix}{detail_suffix}.html"
        file_path = os.path.join(HTML_DEBUG_DIR, file_name)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"<!-- School: {school_name} -->\\n")
            f.write(f"<!-- Page Type: {page_type_suffix}{detail_suffix.replace('_', ' ', 1)} -->\\n")
            f.write(f"<!-- URL: {url} -->\\n")
            if page_specific_detail and detail_suffix != f"_{page_specific_detail}": # Log original if sanitized
                 f.write(f"<!-- Suffix/Detail: {page_specific_detail} -->\\n")
            f.write(f"<!-- Saved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\\n\\n")
            f.write(html_content)
        # print(f"    [Debug] Saved HTML log: {file_path}")
    except Exception as e:
        print(f"    [Error] Failed to save HTML debug log for {school_name} {page_type_suffix}: {e}")

def save_error_log(school_name, error_message, timestamp, exception_obj=None):
    try:
        file_name = f"{school_name}_error_{timestamp}.txt"
        file_path = os.path.join(ERROR_LOG_DIR, file_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"School: {school_name}\\n")
            f.write(f"Timestamp: {timestamp}\\n")
            f.write(f"Error Message: {error_message}\\n\\n")
            if exception_obj:
                f.write(f"Exception Type: {type(exception_obj).__name__}\\n")
                f.write(f"Exception Details: {str(exception_obj)}\\n\\n")
                f.write("Traceback:\\n")
                import traceback
                traceback.print_exc(file=f)
        print(f"    [ErrorLog] Saved error log: {file_path}")
    except Exception as e:
        print(f"    [Critical] Failed to save error log itself: {e}")

# --- Utility: Fetch Page Content ---
def fetch_page(url, school_name_for_log="", page_type_for_log="", page_specific_detail="", retries=RETRY_ATTEMPTS, delay=RETRY_DELAY, year_for_log=None, **kwargs):
    # Use the passed-in log-specific names internally for clarity if needed,
    # or simply use them directly for saving logs.
    school_name = school_name_for_log
    page_type_suffix_for_debug = page_type_for_log

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        # 禁用 SSL 警告
        warnings.filterwarnings('ignore', category=InsecureRequestWarning)
        # 添加 verify=False 来忽略 SSL 证书验证错误
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, verify=False) 
        response.raise_for_status() # 如果请求失败 (4xx, 5xx) 则抛出异常
        response.encoding = response.apparent_encoding 
        # 恢复警告（如果需要在其他地方验证 SSL）
        warnings.resetwarnings()
        
        current_page_specific_detail = page_specific_detail
        if year_for_log:
            # Ensure year_for_log is treated as a string for concatenation
            year_str = str(year_for_log)
            if current_page_specific_detail: # If there's already some detail
                current_page_specific_detail = f"{current_page_specific_detail}_{year_str}"
            else: # If page_specific_detail was empty
                current_page_specific_detail = year_str
        
        if school_name and page_type_suffix_for_debug:
             save_html_debug_log(response.text, school_name, page_type_suffix_for_debug, timestamp, url, current_page_specific_detail)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"  [{school_name}] 获取页面失败 (url: {url}): {e}")
        if retries > 0:
            print(f"    Retrying in {delay} seconds... ({retries} retries left)")
            time.sleep(delay)
            return fetch_page(url, school_name_for_log, page_type_for_log, page_specific_detail, retries - 1, delay, year_for_log, **kwargs)
        else:
            error_message = f"获取页面失败 (url: {url}): {e}"
            save_error_log(school_name, error_message, timestamp, e)
        return None
    except Exception as e_gen:
        print(f"  [{school_name}] 获取页面时发生未知错误 (url: {url}): {e_gen}")
        error_message = f"获取页面时发生未知错误 (url: {url}): {e_gen}"
        save_error_log(school_name, error_message, timestamp, e_gen)
        return None

# --- Utility: Fetch Dynamic Page with Selenium ---
def fetch_dynamic_page_with_selenium(url, school_name, page_type_suffix, selenium_actions=None, page_specific_detail=""):
    """
    使用 Selenium WebDriver 加载页面，可选地选择下拉框选项，点击按钮，
    然后等待特定元素出现，并返回页面源码。同时保存HTML日志。
    select_options: a list of dicts like [{"dropdown_id": "id", "option_value": "value"}]
    """
    html_source = None
    driver = None
    try:
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless') 
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("user-agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'")

        script_dir = os.path.dirname(__file__)
        project_root = os.path.dirname(script_dir)
        chromedriver_filename = "chromedriver.exe" if platform.system() == "Windows" else "chromedriver"
        chrome_driver_path = os.path.join(project_root, 'utils', chromedriver_filename)
        print(f"    [Selenium] 尝试使用 ChromeDriver 路径 ({platform.system()}): {chrome_driver_path}")

        print(f"    [Selenium] 初始化 WebDriver (非 Headless - 调试模式)...")
        try:
            service = Service(executable_path=chrome_driver_path)
            driver = webdriver.Chrome(service=service, options=options)
        except WebDriverException as e:
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

        if selenium_actions:
            for action in selenium_actions:
                dropdown_id = action.get("dropdown_id")
                option_value = action.get("option_value")
                if dropdown_id and option_value:
                    try:
                        print(f"    [Selenium] 尝试在下拉框 '{dropdown_id}' 中选择值 '{option_value}'...")
                        select_element = Select(driver.find_element(By.ID, dropdown_id))
                        select_element.select_by_value(option_value)
                        print(f"      -> 已选择 '{dropdown_id}' 的值为 '{option_value}'")
                        time.sleep(1) 
                    except Exception as select_e:
                        print(f"    [Selenium] 选择下拉框 '{dropdown_id}' 时出错: {select_e}")

        if selenium_actions and selenium_actions[-1].get('click_button_id'):
             try:
                 print(f"    [Selenium] 尝试查找并点击按钮 ID: {selenium_actions[-1]['click_button_id']}")
                 button = driver.find_element(By.ID, selenium_actions[-1]['click_button_id'])
                 button.click()
                 print(f"    [Selenium] 已点击按钮 ID: {selenium_actions[-1]['click_button_id']}")
                 time.sleep(1)
             except Exception as click_e:
                 print(f"    [Selenium] 点击按钮 ID '{selenium_actions[-1]['click_button_id']}' 时出错: {click_e}")
                 
        if selenium_actions and selenium_actions[-1].get('wait_after_click_selector'):
             print(f"    [Selenium] 等待元素选择器 '{selenium_actions[-1]['wait_after_click_selector']}' 匹配 (最多 {SELENIUM_TIMEOUT} 秒)...")
             wait = WebDriverWait(driver, SELENIUM_TIMEOUT)
             wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selenium_actions[-1]['wait_after_click_selector'])))
             print(f"    [Selenium] 元素选择器 '{selenium_actions[-1]['wait_after_click_selector']}' 匹配成功。")
        else:
              print(f"    [Selenium] 未指定等待元素(点击后)，默认等待 5 秒...")
              time.sleep(5)
              
        html_source = driver.page_source
        print(f"    [Selenium] 成功获取页面源码。")
        if html_source:
            save_html_debug_log(html_source, school_name, page_type_suffix, datetime.now().strftime('%Y%m%d_%H%M%S'), url, page_specific_detail)
        
    except TimeoutException:
        print(f"    [Selenium] 错误：等待元素选择器 '{selenium_actions[-1]['wait_after_click_selector']}' 超时 ({SELENIUM_TIMEOUT}秒)。页面可能未完全加载或元素不存在。")
        if driver:
             try:
                 screenshot_path = os.path.join(project_root, 'utils', 'selenium_timeout_screenshot.png')
                 driver.save_screenshot(screenshot_path)
                 print(f"    [Selenium] 已保存超时截图到: {screenshot_path}")
                 # 也尝试保存此时的页面源码
                 timeout_html_source = driver.page_source
                 if timeout_html_source:
                     save_html_debug_log(timeout_html_source, school_name, f"{page_type_suffix}_Timeout", datetime.now().strftime('%Y%m%d_%H%M%S'), url)
             except Exception as screenshot_e:
                 print(f"    [Selenium] 保存截图或超时HTML时出错: {screenshot_e}")
    except WebDriverException as e:
         print(f"    [Selenium] WebDriver 发生错误: {e}")
    except Exception as e:
         print(f"    [Selenium] 获取动态页面时发生未知错误: {e}")
    finally:
         if driver:
             print(f"    [Selenium] 关闭 WebDriver。")
             driver.quit()
             
    return html_source

# --- Utility: Load School Targets ---
def load_school_targets(csv_path):
    # ... (保持原有 load_school_targets 函数内容) ...
    pass

# --- Parsing Helpers ---
# ... (保持原有 parsing helpers, e.g., find_link_by_text_and_href_keywords, parse_exam_subjects, etc.) ...

# --- School Specific Parsers ---
# ... (SCU parsing functions: parse_scu_major_details_from_selenium_table, parse_scu_score_line_page, parse_scu_historical_data_page)
# ... (UESTC parsing functions: parse_uestc_major_catalog_iframe, parse_uestc_score_line_page, parse_uestc_department_iframe)
# ... (Other schools' specific parsers if any)

# --- Generic Parsers ---
# ... (parse_generic_major_catalog, parse_generic_score_page)

# --- Main Parsing Orchestrator ---
def parse_school_data(school_name, base_url, major_catalog_url_override=None, score_line_url_override=None, selenium_actions_str=None):
    """
    解析单个学校的招生信息。
    """
    print(f"-[{school_name}] 开始处理: {base_url}")
    school_update_data = {
        "departments": [], 
        "major_catalog_url": "", 
        "score_line_url": ""     
    }

    print(f"  [{school_name}] 获取主页: {base_url}")
    main_page_html = fetch_page(base_url, school_name_for_log=school_name, page_type_for_log="MainPage")
    if not main_page_html:
        print(f"-[{school_name}] 无法获取主页内容，跳过。")
        return None

    soup = BeautifulSoup(main_page_html, 'html.parser')

    major_catalog_url = None
    score_line_urls = {} 
    parsed_majors_by_dept = {} 
    yearly_score_line_urls = {} 
    temp_score_data = {} 

    if school_name == "四川大学":
        print(f"  [{school_name}] 应用四川大学特定解析逻辑...")
        major_link = soup.select_one('a[href="/sszyml/index"]') 
        if major_link:
            major_catalog_url = urljoin(base_url, major_link['href'])
            print(f"  [{school_name}] 找到专业目录链接: {major_catalog_url}")
            school_update_data["major_catalog_url"] = major_catalog_url
        else:
            print(f"  [{school_name}] 未找到预期的专业目录链接。")

        history_link = soup.select_one('a[href="/zsxx/newslist/a/ls"]') 
        if history_link:
            historical_data_url = urljoin(base_url, history_link['href'])
            print(f"  [{school_name}] 找到历年数据链接: {historical_data_url}")
            history_page_html = fetch_page(historical_data_url, school_name_for_log=school_name, page_type_for_log="HistoricalDataIndexPage_SCU")
            if history_page_html:
                history_soup = BeautifulSoup(history_page_html, 'html.parser')
                print(f"    [{school_name}] 正在解析历年数据页面...")
                data_list_ul = history_soup.find('ul', class_='data-list')
                if data_list_ul:
                    for year in ["2024", "2023", "2022"]:
                        score_link_tag = data_list_ul.find('a', string=re.compile(f'{year}.*硕士.*复试.*成绩基本要求'))
                        if score_link_tag and score_link_tag.has_attr('href'):
                            link_href = score_link_tag['href']
                            score_line_urls[year] = urljoin(historical_data_url, link_href) # Use historical_data_url as base for relative links from this page
                            print(f"      [{school_name}] 找到 {year} 分数线链接: {score_line_urls[year]}")
                            if year == "2024": 
                                school_update_data["score_line_url"] = score_line_urls[year]
                        else:
                            print(f"      [{school_name}] 未在数据列表中找到 {year} 分数线的链接。")
                else:
                    print(f"    [{school_name}] 未在历年数据页找到 class='data-list' 的列表。")
            else:
                 print(f"  [{school_name}] 无法获取历年数据页面内容。")
        else:
            print(f"  [{school_name}] 未找到预期的历年数据链接。")
           
        if major_catalog_url:
            print(f"  [{school_name}] 尝试使用 Selenium 访问专业目录页: {major_catalog_url}")
            scu_selenium_actions = [
                {"dropdown_id": "yxslist", "option_value": "304", "wait_after_select": 1}, # 下拉选择
                {"click_button_id": "searchbtn", "wait_after_click": 2, "wait_after_click_selector": "#datatabel tbody tr"} # 点击并等待
            ]
            catalog_html = fetch_dynamic_page_with_selenium(
                url=major_catalog_url,               # 参数名：url
                school_name=school_name,             # 参数名：school_name
                page_type_suffix="MajorCatalog_SCU_Selenium", # 参数名：page_type_suffix
                selenium_actions=scu_selenium_actions, # 参数名：selenium_actions
                page_specific_detail=""              # 参数名：page_specific_detail (如果不需要特定详情，传空字符串)
            ) 
            if catalog_html:
                # The save_html_debug_log is now called inside fetch_dynamic_page_with_selenium
                # We can still save a copy here if we want a specific name or do further processing before saving
                # For example, if we wanted to save the soup object after parsing
                # with open(os.path.join(HTML_DEBUG_DIR, f"{school_name}_MajorCatalog_ParsedSoup_{time.strftime('%Y%m%d_%H%M%S')}.html"), "w", encoding="utf-8") as f_dump:
                #    f_dump.write(BeautifulSoup(catalog_html, 'html.parser').prettify())
                # print(f"    [{school_name}] ( дополнительно ) Разобранный HTML-каталог специальностей сохранен.")
                
                print(f"    [{school_name}] 使用 BeautifulSoup 解析 Selenium 获取的专业目录源码...")
                catalog_soup = BeautifulSoup(catalog_html, 'html.parser')
                major_table = catalog_soup.find('table', id='datatabel')
                if major_table:
                    tbody = major_table.find('tbody')
                    if tbody:
                        major_rows = tbody.find_all('tr')
                        print(f"      [{school_name}] 在专业目录页找到 ID='datatabel' 的表格，共 {len(major_rows)} 行。开始解析...")
                        
                        current_dept_name = "未知院系" 
                        current_major_code = None
                        current_major_name = None
                        current_degree_type = None
                        current_study_type = None
                        # These need to be reset or carefully handled for each major/direction
                        # Because of rowspan, they might carry over.
                        # We reset them when a new major_header is found.
                        # And when a direction row updates them, it should update the *current* major's dict.
                        
                        # --- Variables to store per-direction data before associating with a major ---
                        # These will be reset for each actual data row (direction row)
                        # This is a change in logic: parse these directly from direction rows
                        # and only update the major if they are present (not relying on carry-over for these)
                        
                        for i, m_row in enumerate(major_rows):
                            m_cols = m_row.find_all('td')
                            num_cols = len(m_cols)

                            try:
                                if num_cols >= 1 and m_cols[0].find('h3'):
                                    dept_name_raw = m_cols[0].find('h3').text.strip()
                                    match = re.match(r'\\d+\\s+(.*)', dept_name_raw) 
                                    current_dept_name = match.group(1) if match else dept_name_raw
                                    print(f"        ---> Detected Department: '{current_dept_name}'")
                                    current_major_code = None # Reset major context when department changes
                                    continue 

                                col0_h4 = m_cols[0].find('h4') if num_cols > 0 else None
                                is_major_header = num_cols == 5 and col0_h4 and re.match(r'^\\d{6}\\s+', col0_h4.text.strip())
                                
                                if is_major_header:
                                    col0_text = col0_h4.text.strip()
                                    major_code_match = re.match(r'^(\\d{6})\\s+(.*)', col0_text)
                                    if major_code_match:
                                        current_major_code = major_code_match.group(1)
                                        current_major_name = major_code_match.group(2).strip()
                                        print(f"  [SCU Debug] Found Major Header: Code={current_major_code}, Name={current_major_name}") # 新增打印
                                        if current_major_code in TARGET_MAJOR_CODES:
                                            print(f"  [SCU Debug] Major {current_major_code} IS a target major.") # 新增打印
                                            print(f"          -> MATCHED TARGET MAJOR! Initializing entry.")
                                            if current_dept_name not in parsed_majors_by_dept:
                                                parsed_majors_by_dept[current_dept_name] = {}
                                            
                                                enrollment_raw = m_cols[2].text.strip()
                                            enrollment_match = re.search(r'\\d+', enrollment_raw)
                                                enrollment = enrollment_match.group(0) if enrollment_match else enrollment_raw
                                            
                                            # Initialize with placeholders, to be filled by direction rows or remain as placeholders
                                                parsed_majors_by_dept[current_dept_name][current_major_code] = {
                                                    "major_code": current_major_code,
                                                    "major_name": current_major_name,
                                                    "degree_type": current_degree_type,
                                                    "study_type": current_study_type,
                                                "enrollment": {"2024": enrollment, "2023": 0, "2022": 0}, # Assuming 2024 from catalog, others TBD
                                                "exam_subjects": "信息待补充", 
                                                "remarks": "信息待补充",          
                                                "tuition_duration": "",
                                                    "research_directions": [],
                                                    "score_lines": {}
                                                }
                                        else: # Not a target major, reset current_major_code so its directions are skipped
                                            print(f"          -> Code '{current_major_code}' not in TARGET_MAJOR_CODES. Ignoring this major header and its subsequent directions.")
                                            current_major_code = None 
                                    else: # Regex for major code and name in h4 failed
                                        current_major_code = None # Ensure safety
                                    continue 

                                # --- Check for Direction Row (num_cols == 5) AND ensure it belongs to a current TARGET major ---
                                # This row type provides details for the major identified in the preceding major_header row
                                if num_cols == 5 and current_major_code and (parsed_majors_by_dept.get(current_dept_name, {}).get(current_major_code) is not None):
                                    # This is a direction row for the current_major_code (which is a target major)
                                    # Extract direction-specific info if available from this row
                                    direction_name = m_cols[0].text.strip()
                                    advisors = m_cols[1].text.strip().replace('\\n', ' ').strip()
                                    
                                    # Get the major_dict to update it
                                    major_dict_to_update = parsed_majors_by_dept[current_dept_name][current_major_code]

                                    # Check if exam_subjects are in this row (col 3, index 2, due to rowspan it might not always be here)
                                    # The HTML structure uses `style="display: none;"` for subsequent rows under a rowspan.
                                    # We only parse if the cell is visible and has content.
                                    subjects_col_html_content = ""
                                    if 'display: none;' not in m_cols[3].get('style', '') and m_cols[3].text.strip():
                                        subjects_col_html_content = str(m_cols[3]) # Pass the HTML of the <td>
                                        parsed_subjects = parse_exam_subjects(subjects_col_html_content)
                                        if parsed_subjects != "信息待补充": # Only update if successfully parsed
                                            major_dict_to_update['exam_subjects'] = parsed_subjects
                                            print(f"            Updated exam_subjects for {current_major_code} from direction row.")


                                    # Check if remarks/tuition/duration are in this row (col 4, index 3)
                                    remarks_col_html_content = ""
                                    if 'display: none;' not in m_cols[4].get('style', '') and m_cols[4].text.strip():
                                        remarks_col_html_content = str(m_cols[4]) # Pass the HTML of the <td>
                                        # Extract remarks text directly
                                        current_remarks_raw = BeautifulSoup(remarks_col_html_content, 'html.parser').get_text(separator=' ', strip=True)
                                        
                                        if current_remarks_raw:
                                            major_dict_to_update['remarks'] = current_remarks_raw
                                         # Try to extract tuition/duration from the full remarks
                                            tuition_match = re.search(r'学费：\\s*(\\d+元/生\\.年)', current_remarks_raw)
                                            duration_match = re.search(r'学制：\\s*(\\d+\\s*年)', current_remarks_raw)
                                         tuition = tuition_match.group(1) if tuition_match else ""
                                         duration = duration_match.group(1) if duration_match else ""
                                         current_tuition_duration = f"{tuition}, {duration}".strip(', ') if (tuition or duration) else ""
                                            if current_tuition_duration:
                                                 major_dict_to_update['tuition_duration'] = current_tuition_duration
                                            print(f"            Updated remarks/tuition for {current_major_code} from direction row.")
                                            
                                    # Append the direction details regardless of whether subjects/remarks were updated from *this specific* direction row
                                    # The major_dict holds the latest subjects/remarks from the first relevant direction row.
                                    if direction_name or advisors: # Only add if there's a name or advisor
                                        major_dict_to_update['research_directions'].append({
                                            "direction_name": direction_name,
                                            "advisors": advisors
                                        })
                                        print(f"          Added Direction: '{direction_name}' to Major '{current_major_code}'")
                                # else:
                                #     print(f"        [Row {i+1}] Skipped: Not a department, not a major header, or not a direction for a current target major.")

                            except Exception as e:
                                print(f"        [Row {i+1}] Exception during processing: {e}")
                        
                    else: 
                        print(f"    [{school_name}] 在专业目录页 ID='datatabel' 的表格中未找到 <tbody>。")
                else: 
                    print(f"    [{school_name}] 未能在专业目录页找到 ID='datatabel' 的表格。")
                
                print(f"      [{school_name}] 专业目录表格解析完成。准备构建最终数据结构...")
                final_departments_list = []
                total_target_majors_found = 0
                for dept_key in parsed_majors_by_dept:
                    majors_dict = parsed_majors_by_dept[dept_key] 
                    list_of_major_dicts = list(majors_dict.values()) 

                    if list_of_major_dicts: 
                        dept_entry = {
                            "department_name": dept_key,
                            "majors": list_of_major_dicts 
                        }
                        final_departments_list.append(dept_entry)
                        total_target_majors_found += len(list_of_major_dicts)

                print(f"      -> Processed. Found {total_target_majors_found} target majors in {len(final_departments_list)} departments.")
                school_update_data['departments'] = final_departments_list
                
            else: # catalog_html is None
                print(f"  [{school_name}] Selenium 未能获取专业目录页面内容。")
               
        if score_line_urls:
            print(f"  [{school_name}] (SCU) 开始解析分数线...")
            for year, url in score_line_urls.items():
                print(f"    [{school_name}] 尝试获取 {year} 分数线页面: {url}")
                score_html = fetch_page(url, school_name_for_log=school_name, page_type_for_log="ScoreLinePage_SCU", year_for_log=year)
                if score_html:
                    score_soup = BeautifulSoup(score_html, 'html.parser')
                    try:
                        score_table = score_soup.find('table', class_='Table')
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
                                if not s_cols or len(s_cols) < 5:
                                    header_text = s_row.get_text(strip=True)
                                    if "学术学位" in header_text:
                                        is_academic_section = True
                                        is_professional_section = False
                                        continue
                                    elif "专业学位" in header_text:
                                        is_academic_section = False
                                        is_professional_section = True
                                        continue
                                    elif "专项计划" in header_text or "其他" in header_text: # Stop before these sections
                                        print(f"        [{school_name}] {year} - Reached '{header_text}', stopping score parsing for this table.")
                                        break
                                    continue
                                try:
                                    category_code_raw = s_cols[0].text.strip()
                                    # Ensure we only take the numeric part for category_code
                                    category_code_match = re.match(r"(\\d+)", category_code_raw)
                                    category_code = category_code_match.group(1) if category_code_match else category_code_raw

                                    category_name = s_cols[1].text.strip()
                                    total_score_raw = s_cols[4].text.strip()
                                    total_score_match = re.search(r'\\d+', total_score_raw)
                                    total_score = total_score_match.group(0) if total_score_match else total_score_raw

                                    # Check against TARGET_CATEGORY_PREFIXES (e.g., '08', '0854')
                                    current_prefix_to_check = category_code[:4] if category_code.startswith("0854") else category_code[:2]
                                    
                                    if current_prefix_to_check in TARGET_CATEGORY_PREFIXES:
                                        score_type_detail = "学硕" if is_academic_section else ("专硕" if is_professional_section else "未知类型")
                                        print(f"      [{school_name}] {year} 找到目标学科大类({score_type_detail}): {category_code} {category_name} - 总分线: {total_score}")
                                        if year not in temp_score_data: temp_score_data[year] = {}
                                        # Store with a key that includes both code prefix and type to differentiate
                                        temp_score_data[year][f"{current_prefix_to_check}_{score_type_detail}"] = total_score
                                except IndexError:
                                    print(f"      [{school_name}] 解析 {year} 分数线某行时列数不足或格式错误。跳过此行.")
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
        uestc_major_catalog_page_url = None 
        uestc_score_line_page_url = None 
        temp_score_data = {} 

        target_catalog_year = 2025 
        known_catalog_url_pattern = f"https://yzbm.uestc.edu.cn/zsml/sszsml/index/{target_catalog_year}"
        print(f"    [{school_name}] 优先尝试使用已知模式的专业目录URL: {known_catalog_url_pattern}")
        
        # Test this known URL
        # test_catalog_html = fetch_page(known_catalog_url_pattern, school_name_for_log=school_name, page_type_for_log=f"MajorCatalogTest_UESTC_{target_catalog_year}")
        # if test_catalog_html and ("zsml-dept-tree" in test_catalog_html or "iframeContent" in test_catalog_html): # Check for expected elements
        #     print(f"      -> 已知模式URL ({known_catalog_url_pattern}) 初步测试通过 (存在特征元素)。")
        #     uestc_major_catalog_page_url = known_catalog_url_pattern
        #     school_update_data["major_catalog_url"] = uestc_major_catalog_page_url
        # else:
        #     print(f"      -> 已知模式URL ({known_catalog_url_pattern}) 测试失败或未包含特征元素。将尝试从主页搜索。")
        # Simplified: Directly assign and proceed. If Selenium part fails, this URL was likely the issue.
        uestc_major_catalog_page_url = known_catalog_url_pattern
        school_update_data["major_catalog_url"] = uestc_major_catalog_page_url
        print(f"      -> 直接使用已知模式URL: {uestc_major_catalog_page_url}")


        if not uestc_major_catalog_page_url: 
            print(f"    [{school_name}] 未能通过已知模式获取专业目录URL，现在尝试从主页 ({base_url}) 查找...")
            try:
                catalog_link_tag = soup.find('a', string=re.compile(r'^\s*专业目录\s*$'), href=re.compile(r'(zsml|zyml)')) 
                if not catalog_link_tag:
                    all_links = soup.find_all('a', string=re.compile(r'专业目录'), href=True)
                    if all_links:
                        for link_tag_cand in all_links:
                            href_val = link_tag_cand['href']
                            if href_val and not href_val.startswith(('#', 'javascript:')) and ('.htm' in href_val or '.html' in href_val or href_val.endswith('/') or 'id=' in href_val):
                                catalog_link_tag = link_tag_cand
                                print(f"    [{school_name}] 通过备用逻辑找到'专业目录'链接: {catalog_link_tag.get('href')}")
                                break
                        if not catalog_link_tag and all_links: 
                            for link_tag_cand in all_links:
                                 href_val = link_tag_cand['href']
                                 if href_val and not href_val.startswith(('#', 'javascript:')):
                                    catalog_link_tag = link_tag_cand
                                    print(f"    [{school_name}] 通过最宽松备用逻辑找到'专业目录'链接: {catalog_link_tag.get('href')}")
                                    break
                
                if catalog_link_tag and catalog_link_tag.has_attr('href'):
                    found_on_main_page_url = urljoin(base_url, catalog_link_tag['href'])
                    print(f"    [{school_name}] 在主页找到专业目录链接: {found_on_main_page_url}")
                    if not uestc_major_catalog_page_url:
                        uestc_major_catalog_page_url = found_on_main_page_url
                        school_update_data["major_catalog_url"] = uestc_major_catalog_page_url
                else:
                    if not uestc_major_catalog_page_url: 
                        print(f"    [{school_name}] 在主页也未能找到'专业目录'链接。")
            except Exception as link_find_e:
                print(f"    [{school_name}] 在主页查找链接时出错: {link_find_e}")
            
        if not uestc_major_catalog_page_url:
            print(f"!!! [{school_name}] 关键错误：最终未能确定有效的专业目录URL。将跳过专业目录解析。")

        try:
            score_link_tag = soup.find('a', string=re.compile(r'(分数线|历年分数|复试线)')) 
            if score_link_tag and score_link_tag.has_attr('href'):
                href_val = score_link_tag['href']
                if href_val and not href_val.startswith(('#', 'javascript:')):
                    uestc_score_line_page_url = urljoin(base_url, href_val)
                    print(f"    [{school_name}] 找到历年分数/分数线主链接: {uestc_score_line_page_url}")
                    school_update_data["score_line_url"] = uestc_score_line_page_url 
                else:
                    print(f"    [{school_name}] 找到的'历年分数/分数线'链接无效: {href_val}")
            else:
                print(f"    [{school_name}] 未在主页找到'历年分数'或'分数线'链接。")
        except Exception as link_find_e:
            print(f"    [{school_name}] 在主页查找分数线链接时出错: {link_find_e}")

        yearly_score_line_urls = {} 
        if uestc_score_line_page_url:
            print(f"    [{school_name}] 尝试获取历年分数线入口页: {uestc_score_line_page_url}")
            score_index_html = fetch_page(uestc_score_line_page_url, school_name_for_log=school_name, page_type_for_log="ScoreIndexPage_UESTC")
            if score_index_html:
                score_index_soup = BeautifulSoup(score_index_html, 'html.parser')
                link_container = score_index_soup.find('div', id='news_list') 
                if not link_container:
                    link_container = score_index_soup.find('ul', class_='news_list') 
                if not link_container:
                    link_container = score_index_soup.find('div', id=re.compile(r'vsb_content')) 
                
                if link_container:
                    print(f"      [{school_name}] 在分数线入口页找到初步容器 (Selector: {link_container.name}#{link_container.get('id', '')}.{link_container.get('class', [])})...")
                    actual_list_container = link_container.find('ul')
                    link_source = actual_list_container if actual_list_container else link_container
                    print(f"        -> Link source: {link_source.name} (Class: {link_source.get('class', [])}, ID: {link_source.get('id', '')})")
                    
                    all_links_in_source = link_source.find_all('a', href=True) 
                    print(f"        -> Found {len(all_links_in_source)} total links with href within the source. Checking texts...")

                    found_years = set()
                    for link_tag in all_links_in_source:
                        link_text = link_tag.text.strip()
                        link_href = link_tag.get('href')
                        for year_str in ["2024", "2023", "2022"]: # Ensure year_str is string for regex
                            # Regex to find year possibly surrounded by other text, and keywords for score lines
                            if re.search(year_str, link_text) and re.search(r'(复试|分数线|基本要求)', link_text):
                                if year_str not in found_years: 
                                    url = urljoin(uestc_score_line_page_url, link_href) # Use uestc_score_line_page_url as base
                                    yearly_score_line_urls[year_str] = url
                                    print(f"        [{school_name}] 找到 {year_str} 分数线链接: {url} (Text: '{link_text}')")
                                    found_years.add(year_str)
                                    # Update main score_line_url if this is the latest year we are looking for
                                    if year_str == "2024" and school_update_data.get("score_line_url") != url : # Check if already set to this one
                                        school_update_data["score_line_url"] = url 
                                        print(f"          -> 更新最新分数线URL为: {url}")
                                    break 
                    
                    if not school_update_data.get("score_line_url") and "2023" in yearly_score_line_urls : # Fallback if 2024 not found
                        school_update_data["score_line_url"] = yearly_score_line_urls["2023"]
                        print(f"        [{school_name}] 最新分数线URL (2024) 未找到，使用2023年链接: {yearly_score_line_urls['2023']}")
                    elif not school_update_data.get("score_line_url") and "2022" in yearly_score_line_urls: # Fallback if 2023 also not found
                        school_update_data["score_line_url"] = yearly_score_line_urls["2022"]
                        print(f"        [{school_name}] 最新分数线URL (2024/23) 未找到，使用2022年链接: {yearly_score_line_urls['2022']}")


                    for year_check in ["2024", "2023", "2022"]:
                        if year_check not in found_years:
                            print(f"        [{school_name}] 未找到 {year_check} 的分数线链接。")
                else:
                    print(f"      [{school_name}] 在分数线入口页未能找到初步链接容器。")
            else:
                print(f"    [{school_name}] 无法获取历年分数线入口页面内容。")

        if yearly_score_line_urls:
            print(f"  [{school_name}] (UESTC) 开始解析已找到的各年份分数线...")
            for year, url in yearly_score_line_urls.items():
                print(f"    [{school_name}] 尝试获取 {year} 分数线页面: {url}")
                score_html = fetch_page(url, school_name_for_log=school_name, page_type_for_log="ScoreLinePage_UESTC", year_for_log=year)
                if score_html:
                    score_soup = BeautifulSoup(score_html, 'html.parser')
                    try:
                        content_div = score_soup.find('div', id=re.compile(r'vsb_content')) \
                                   or score_soup.find('div', class_='v_news_content') \
                                   or score_soup.find('div', class_=re.compile(r'(content|main|article)'))

                        if content_div:
                            score_tables = content_div.find_all('table')
                            print(f"      [{school_name}] 在 {year} 分数线页内容区域找到 {len(score_tables)} 个表格。尝试解析...")

                            if not score_tables: # If no tables, try direct text parsing
                                print(f"        [{school_name}] 未在内容区域找到 <table>。尝试直接解析内容文本...")
                                # ... (text parsing logic - can be enhanced) ...
                            else:
                                # Parse the first found table
                                score_table = score_tables[0]
                                    print(f"      [{school_name}] 在 {year} 分数线页内容区域找到表格 1。开始解析...")
                                    score_rows = score_table.find_all('tr')
                                current_degree_type_from_table = "未知" 

                                    for r_idx, s_row in enumerate(score_rows):
                                    cols = s_row.find_all(['td', 'th']) # Include <th> for headers
                                    if not cols: continue

                                        col_texts = [col.get_text(strip=True) for col in cols]

                                    # Attempt to determine degree type from row/section headers
                                    # This part might need specific selectors for UESTC's table structure
                                    if any("学术学位" in text for text in col_texts):
                                        current_degree_type_from_table = "学硕"
                                                continue 
                                    if any("专业学位" in text for text in col_texts):
                                        current_degree_type_from_table = "专硕"
                                                continue 
                                    if len(col_texts) < 2 : continue # Skip rows too short for data

                                    subject_text = col_texts[0] # Assuming first col is subject/category
                                    total_score_text = col_texts[-1] # Assuming last col is total score

                                    category_code_prefix = ""
                                    # More robustly extract potential code, e.g., (08) or [0854]
                                    code_match_in_text = re.search(r'[(（]?(\d{2,4})[)）]?', subject_text)
                                    if code_match_in_text:
                                        extracted_code = code_match_in_text.group(1)
                                        if extracted_code.startswith("0854") and "0854" in TARGET_CATEGORY_PREFIXES:
                                            category_code_prefix = "0854"
                                        elif extracted_code.startswith("08") and "08" in TARGET_CATEGORY_PREFIXES:
                                             category_code_prefix = "08"
                                    
                                    score_val_match = re.search(r'^(\\d{3,})$', total_score_text)
                                    score = score_val_match.group(1) if score_val_match else None

                                    if category_code_prefix and score:
                                        # Use determined degree type or infer if still "未知"
                                        final_degree_type = current_degree_type_from_table
                                        # Basic inference if table headers didn't specify
                                        if final_degree_type == "未知":
                                            if "电子信息" in subject_text or category_code_prefix == "0854": final_degree_type = "专硕"
                                            elif "工学" in subject_text or category_code_prefix == "08": final_degree_type = "学硕"


                                        print(f"            [{school_name}] {year} ({final_degree_type}) 从表格找到目标: {category_code_prefix} ({subject_text}) - 总分线: {score}")
                                        if year not in temp_score_data: temp_score_data[year] = {}
                                        # Store with a key that includes both code prefix and type
                                        temp_score_data[year][f"{category_code_prefix}_{final_degree_type}"] = score
                        else:
                            print(f"      [{school_name}] 在 {year} 分数线页未找到主要内容区域。")
                    except Exception as score_e:
                        print(f"    [{school_name}] 解析 {year} UESTC 分数线页面时出错: {score_e}")
                else:
                    print(f"    [{school_name}] 无法获取 {year} UESTC 分数线页面内容。")
                time.sleep(1)

        if uestc_major_catalog_page_url:
            latest_major_catalog_url = uestc_major_catalog_page_url 
            if not school_update_data.get("major_catalog_url"): # Ensure it's set if not by earlier logic
                 school_update_data["major_catalog_url"] = latest_major_catalog_url

            print(f"    [{school_name}] 将找到的目录链接视为最新目录页: {latest_major_catalog_url}")
            driver = None 
            try:
                options = webdriver.ChromeOptions()
                # options.add_argument('--headless') 
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
                # Save the main catalog page HTML (before iframe interaction)
                save_html_debug_log(driver.page_source, school_name, "MajorCatalog_UESTC_MainPage_Selenium", datetime.now().strftime('%Y%m%d_%H%M%S'), url=latest_major_catalog_url)


                print(f"      [Selenium] 等待 ZTree 院系列表加载 ('#zsml-dept-tree li a')..." )
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#zsml-dept-tree li a")))
                print(f"      [Selenium] ZTree 加载完成。查找目标院系..." )

                department_links_to_click = []
                all_dept_links = driver.find_elements(By.CSS_SELECTOR, "#zsml-dept-tree li a")
                
                target_dept_keywords = ["计算机科学与工程学院", "信息与软件工程学院"] # Removed codes for broader match
                print(f"        --- Searching for keywords in ZTree: {target_dept_keywords} ---")

                for link in all_dept_links:
                    link_text = link.text.strip()
                    if any(keyword in link_text for keyword in target_dept_keywords):
                        # Heuristic: if it has child 'ul', it's more likely a department node
                        try:
                            parent_li = link.find_element(By.XPATH, "./ancestor::li[1]")
                            if parent_li.find_elements(By.XPATH, "./ul/li"): # Check if it has list items as children
                                print(f"        -> 找到目标院系链接 (有子节点): {link_text}" )
                                department_links_to_click.append(link) 
                                continue # Prioritize nodes that expand
                        except: pass # Ignore if XPATH fails, might not be a parent
                        # Fallback: if no child ul, but text matches, still consider it (some might not expand if single level)
                        print(f"        -> 找到目标院系链接 (无子节点或检查失败): {link_text}" )
                        department_links_to_click.append(link)


                if not department_links_to_click:
                     print(f"      [Selenium] 未找到包含关键字 {target_dept_keywords} 的院系链接。" )

                for dept_link_element in department_links_to_click:
                    dept_name_raw = dept_link_element.text.strip()
                    dept_name_match = re.match(r'\\d*\\s*(.*)', dept_name_raw)
                    dept_name_clean = dept_name_match.group(1).strip() if dept_name_match and dept_name_match.group(1) else dept_name_raw.strip()
                    print(f"      [Selenium] 点击院系: '{dept_name_clean}'" )
                    try:
                        dept_link_element.click()
                        time.sleep(2)

                        print(f"        [Selenium] 等待并切换到 iframe ('iframeContent')..." )
                        WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "iframeContent")))
                        print(f"        [Selenium] 已切换到 iframe。等待内容加载 (查找 table)..." )

                        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
                        print(f"        [Selenium] Iframe 内表格已加载。获取源码..." )

                        iframe_html = driver.page_source
                        save_html_debug_log(iframe_html, school_name, f"MajorCatalog_UESTC_iframe", datetime.now().strftime('%Y%m%d_%H%M%S'), url=driver.current_url, page_specific_detail=dept_name_clean)

                        iframe_soup = BeautifulSoup(iframe_html, 'html.parser')
                        major_table_in_iframe = iframe_soup.find('table') 
                        if major_table_in_iframe:
                            print(f"          [Parser] 在 '{dept_name_clean}' 的 iframe 中找到表格。开始解析行...")
                            rows = major_table_in_iframe.find_all('tr') 
                            print(f"            -> 表格共 {len(rows)} 行。")
                            for r_idx, row in enumerate(rows):
                                cols = row.find_all('td')
                                num_cols = len(cols)
                                if not cols or row.find('th'):
                                    continue
                                if num_cols >= 3:
                                    major_code_raw = cols[0].text.strip()
                                    major_code_match = re.match(r'^(\\d{6})\\s*', major_code_raw)
                                    if major_code_match:
                                        major_code = major_code_match.group(1) 
                                        if major_code in TARGET_MAJOR_CODES:
                                            major_name = cols[1].text.strip() 
                                            enrollment = cols[2].text.strip() 
                                            degree_type = "Professional" if major_code.startswith("0854") else "Academic"
                                            study_type = "全日制" 
                                            exam_subjects = "信息待补充 (需点击查看)" # UESTC iframe often lacks this detail directly
                                            remarks = "信息待补充 (需点击查看)"
                                            tuition_duration = ""
                                            research_directions = []
                                            print(f"              MATCHED TARGET MAJOR: Code={major_code}, Name={major_name}, Dept={dept_name_clean}, Enrollment={enrollment}, Type={degree_type}/{study_type}" )
                                            if dept_name_clean not in parsed_majors_by_dept:
                                                parsed_majors_by_dept[dept_name_clean] = {}
                                            # Use a tuple (major_code, degree_type, study_type) for uniqueness if needed, but here just major_code
                                            # Ensure we don't overwrite if same major code appears under same dept (e.g. full-time/part-time if distinguishable)
                                            # For now, assume major_code per department is unique enough for this simplified table
                                            if major_code not in parsed_majors_by_dept[dept_name_clean]:
                                                parsed_majors_by_dept[dept_name_clean][major_code] = { 
                                                     "major_code": major_code,
                                                     "major_name": major_name,
                                                     "degree_type": degree_type, 
                                                     "study_type": study_type,   
                                                     "enrollment": enrollment, # Store raw, can be parsed later if it's like "计划:10"
                                                     "exam_subjects": exam_subjects,
                                                     "remarks": remarks,
                                                     "tuition_duration": tuition_duration, 
                                                     "research_directions": research_directions,
                                                     "score_lines": {}
                                                 }
                        else:
                             print(f"          [Parser] 在 '{dept_name_clean}' 的 iframe 中未找到 <table> 元素。" )

                        print(f"        [Selenium] 处理完 iframe，切换回主页面。" )
                        driver.switch_to.default_content()
                        time.sleep(1)

                    except TimeoutException:
                         print(f"        [Selenium] 处理院系 '{dept_name_clean}' 时发生超时 (等待 iframe 或其内容)。" )
                         driver.switch_to.default_content() 
                    except Exception as e_iframe:
                         print(f"        [Selenium/Parser] 处理院系 '{dept_name_clean}' 时发生错误: {e_iframe}" )
                         try: 
                             driver.switch_to.default_content()
                         except Exception as switch_err:
                             print(f"          [!] Error switching back from iframe: {switch_err}" )
            except WebDriverException as e_wd:
                print(f"    [Selenium] WebDriver 初始化或操作时出错: {e_wd}" )
            except Exception as e_main:
                print(f"    [Selenium] 获取或处理 UESTC 专业目录时发生未知错误: {e_main}" )
            finally:
                if driver:
                    print(f"      [Selenium] 关闭 WebDriver。" )
                    driver.quit()

            if parsed_majors_by_dept:
                print(f"      [{school_name}] UESTC 专业目录解析完成。准备构建最终数据结构..." )
                final_departments_list = []
                total_target_majors_found = 0
                for dept_key, majors_inner_dict in parsed_majors_by_dept.items():
                    list_of_major_dicts = list(majors_inner_dict.values())
                    if list_of_major_dicts: 
                        dept_entry = {
                            "department_name": dept_key,
                            "majors": list_of_major_dicts
                        }
                        final_departments_list.append(dept_entry)
                        total_target_majors_found += len(list_of_major_dicts)
                print(f"        -> Processed. Found {total_target_majors_found} target majors in {len(final_departments_list)} departments for UESTC." )
                school_update_data['departments'] = final_departments_list
        else: # uestc_major_catalog_page_url was None
            print(f"  [{school_name}] 由于未找到专业目录链接，跳过 Selenium 专业目录解析 (UESTC)。")

    elif school_name == "西南交通大学":
        print(f"  [{school_name}] 应用西南交通大学特定解析逻辑...")
        # Placeholder: try to find generic links
        major_catalog_url = find_generic_link(soup, base_url, ["专业目录", "招生专业", "硕士目录", "招生简章"])
        score_line_url = find_generic_link(soup, base_url, ["分数线", "复试线", "历年分数", "录取分数"])
        if major_catalog_url:
            school_update_data["major_catalog_url"] = major_catalog_url
            print(f"    [{school_name}] (通用查找) 找到疑似专业目录链接: {major_catalog_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到专业目录链接。")
        if score_line_url:
            school_update_data["score_line_url"] = score_line_url
            print(f"    [{school_name}] (通用查找) 找到疑似分数线链接: {score_line_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到分数线链接。")
        print(f"  [{school_name}] 西南交通大学的详细解析逻辑待实现。")
        pass # Actual parsing logic needs to be implemented

    elif school_name == "西南财经大学":
        print(f"  [{school_name}] 应用西南财经大学特定解析逻辑...")
        major_catalog_url = find_generic_link(soup, base_url, ["专业目录", "招生专业", "硕士目录", "招生简章"])
        score_line_url = find_generic_link(soup, base_url, ["分数线", "复试线", "历年分数", "录取分数"])
        if major_catalog_url:
            school_update_data["major_catalog_url"] = major_catalog_url
            print(f"    [{school_name}] (通用查找) 找到疑似专业目录链接: {major_catalog_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到专业目录链接。")
        if score_line_url:
            school_update_data["score_line_url"] = score_line_url
            print(f"    [{school_name}] (通用查找) 找到疑似分数线链接: {score_line_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到分数线链接。")
        print(f"  [{school_name}] 西南财经大学的详细解析逻辑待实现。")
        pass
    
    elif school_name == "四川师范大学":
        print(f"  [{school_name}] 应用四川师范大学特定解析逻辑...")
        major_catalog_url = find_generic_link(soup, base_url, ["专业目录", "招生专业", "硕士目录", "招生简章"])
        score_line_url = find_generic_link(soup, base_url, ["分数线", "复试线", "历年分数", "录取分数"])
        if major_catalog_url:
            school_update_data["major_catalog_url"] = major_catalog_url
            print(f"    [{school_name}] (通用查找) 找到疑似专业目录链接: {major_catalog_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到专业目录链接。")
        if score_line_url:
            school_update_data["score_line_url"] = score_line_url
            print(f"    [{school_name}] (通用查找) 找到疑似分数线链接: {score_line_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到分数线链接。")
        print(f"  [{school_name}] 四川师范大学的详细解析逻辑待实现。")
        pass

    elif school_name == "成都理工大学":
        print(f"  [{school_name}] 应用成都理工大学特定解析逻辑...")
        major_catalog_url = find_generic_link(soup, base_url, ["专业目录", "招生专业", "硕士目录", "招生简章"])
        score_line_url = find_generic_link(soup, base_url, ["分数线", "复试线", "历年分数", "录取分数"])
        if major_catalog_url:
            school_update_data["major_catalog_url"] = major_catalog_url
            print(f"    [{school_name}] (通用查找) 找到疑似专业目录链接: {major_catalog_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到专业目录链接。")
        if score_line_url:
            school_update_data["score_line_url"] = score_line_url
            print(f"    [{school_name}] (通用查找) 找到疑似分数线链接: {score_line_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到分数线链接。")
        print(f"  [{school_name}] 成都理工大学的详细解析逻辑待实现。")
        pass

    elif school_name == "西南科技大学":
        print(f"  [{school_name}] 应用西南科技大学特定解析逻辑...")
        major_catalog_url = find_generic_link(soup, base_url, ["专业目录", "招生专业", "硕士目录", "招生简章"])
        score_line_url = find_generic_link(soup, base_url, ["分数线", "复试线", "历年分数", "录取分数"])
        if major_catalog_url:
            school_update_data["major_catalog_url"] = major_catalog_url
            print(f"    [{school_name}] (通用查找) 找到疑似专业目录链接: {major_catalog_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到专业目录链接。")
        if score_line_url:
            school_update_data["score_line_url"] = score_line_url
            print(f"    [{school_name}] (通用查找) 找到疑似分数线链接: {score_line_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到分数线链接。")
        print(f"  [{school_name}] 西南科技大学的详细解析逻辑待实现。")
        pass

    elif school_name == "成都信息工程大学":
        print(f"  [{school_name}] 应用成都信息工程大学特定解析逻辑...")
        major_catalog_url = find_generic_link(soup, base_url, ["专业目录", "招生专业", "硕士目录", "招生简章"])
        score_line_url = find_generic_link(soup, base_url, ["分数线", "复试线", "历年分数", "录取分数"])
        if major_catalog_url:
            school_update_data["major_catalog_url"] = major_catalog_url
            print(f"    [{school_name}] (通用查找) 找到疑似专业目录链接: {major_catalog_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到专业目录链接。")
        if score_line_url:
            school_update_data["score_line_url"] = score_line_url
            print(f"    [{school_name}] (通用查找) 找到疑似分数线链接: {score_line_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到分数线链接。")
        print(f"  [{school_name}] 成都信息工程大学的详细解析逻辑待实现。")
        pass

    elif school_name == "西华大学":
        print(f"  [{school_name}] 应用西华大学特定解析逻辑...")
        major_catalog_url = find_generic_link(soup, base_url, ["专业目录", "招生专业", "硕士目录", "招生简章"])
        score_line_url = find_generic_link(soup, base_url, ["分数线", "复试线", "历年分数", "录取分数"])
        if major_catalog_url:
            school_update_data["major_catalog_url"] = major_catalog_url
            print(f"    [{school_name}] (通用查找) 找到疑似专业目录链接: {major_catalog_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到专业目录链接。")
        if score_line_url:
            school_update_data["score_line_url"] = score_line_url
            print(f"    [{school_name}] (通用查找) 找到疑似分数线链接: {score_line_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到分数线链接。")
        print(f"  [{school_name}] 西华大学的详细解析逻辑待实现。")
        pass

    elif school_name == "成都大学":
        print(f"  [{school_name}] 应用成都大学特定解析逻辑...")
        major_catalog_url = find_generic_link(soup, base_url, ["专业目录", "招生专业", "硕士目录", "招生简章"])
        score_line_url = find_generic_link(soup, base_url, ["分数线", "复试线", "历年分数", "录取分数"])
        if major_catalog_url:
            school_update_data["major_catalog_url"] = major_catalog_url
            print(f"    [{school_name}] (通用查找) 找到疑似专业目录链接: {major_catalog_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到专业目录链接。")
        if score_line_url:
            school_update_data["score_line_url"] = score_line_url
            print(f"    [{school_name}] (通用查找) 找到疑似分数线链接: {score_line_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到分数线链接。")
        print(f"  [{school_name}] 成都大学的详细解析逻辑待实现。")
        pass
    # ... add other universities as needed ...
    else:
        print(f"  [{school_name}] 未识别的学校或未实现该学校的特定解析逻辑。尝试通用链接查找...")
        major_catalog_url = find_generic_link(soup, base_url, ["专业目录", "招生专业", "硕士目录", "招生简章"])
        score_line_url = find_generic_link(soup, base_url, ["分数线", "复试线", "历年分数", "录取分数"])
        if major_catalog_url:
            school_update_data["major_catalog_url"] = major_catalog_url
            print(f"    [{school_name}] (通用查找) 找到疑似专业目录链接: {major_catalog_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到专业目录链接。")
        if score_line_url:
            school_update_data["score_line_url"] = score_line_url
            print(f"    [{school_name}] (通用查找) 找到疑似分数线链接: {score_line_url}")
        else:
            print(f"    [{school_name}] (通用查找) 未找到分数线链接。")

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

    # --- Final step: Parse individual score year pages ---
    if school_update_data['score_lines']:
        # ... (existing logic to fetch and parse individual year score pages) ...
        # This part populates temp_score_data[year] = parsed_year_scores
        # For SCU, it calls parse_scu_score_line_page
        # For UESTC, specific parsing of year pages might be needed if the index page isn't enough

    # --- Merge temporary score data into school_update_data['departments'][dept_idx]['majors'][major_idx]['score_lines'] ---
    if temp_score_data and school_update_data.get('departments'):
        print(f"  [{school_name}] 尝试将【大类】分数线数据合并到已解析的专业中...")
        majors_updated_with_scores = 0
        for dept_data in school_update_data['departments']: # Iterate through the list of department dicts
            if not isinstance(dept_data, dict): # Add this check
                print(f"    [Merge Error] Expected a dictionary for department data, got {type(dept_data)}. Skipping.")
                continue
            for major_data_item in dept_data.get('majors', []): # Get majors list from department dict
                if not isinstance(major_data_item, dict): # Add this check
                    print(f"    [Merge Error] Expected a dictionary for major data, got {type(major_data_item)}. Skipping.")
                    continue
                major_code = major_data_item.get('code')
                if not major_code: continue

                major_prefix_to_match = major_code[:4] if major_code.startswith("0854") else major_code[:2]
                degree_type_for_score = "专硕" if major_data_item.get('is_professional_degree', False) else "学硕"
                score_key_to_find = f"{major_prefix_to_match}_{degree_type_for_score}"

                for year, year_scores in temp_score_data.items():
                    if score_key_to_find in year_scores:
                        major_data_item.setdefault('score_lines', {})[year] = year_scores[score_key_to_find]
                        majors_updated_with_scores += 1
                    elif major_prefix_to_match in year_scores: # Fallback for general prefix match
                         major_data_item.setdefault('score_lines', {})[year] = year_scores[major_prefix_to_match]
                         majors_updated_with_scores += 1
        if majors_updated_with_scores > 0:
            print(f"    -> 完成分数线合并，共为 {majors_updated_with_scores} 个专业条目（跨年份）添加了分数线。")
        else:
            print(f"    -> 未能将任何大类分数线合并到专业数据中。")
            
    return school_update_data

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