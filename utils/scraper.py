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
import importlib

# --- Selenium Imports ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service # 导入 Service
from selenium.webdriver.support.ui import Select # 导入 Select

# --- Attempt to use undetected-chromedriver --- 
import undetected_chromedriver as uc

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
# HTML_DEBUG_DIR = os.path.join(CRAWLER_DIR, 'html_debug_logs')
# os.makedirs(HTML_DEBUG_DIR, exist_ok=True) # 确保目录存在

ERROR_LOG_DIR = os.path.join(CRAWLER_DIR, 'error_logs')
os.makedirs(ERROR_LOG_DIR, exist_ok=True)

# --- Global Configuration & Constants ---
# (保持原有常量定义)
# ... (其他常量)
USE_HEADLESS_BROWSER = False # True for production, False for debugging to see browser UI
REQUEST_TIMEOUT = 30 # seconds for requests
SELENIUM_TIMEOUT = 30 # seconds for selenium waits
RETRY_DELAY = 5  # seconds
MAX_RETRIES = 3

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# --- TARGET_UNIVERSITIES Definition ---
TARGET_UNIVERSITIES = {
    "四川大学": "https://yz.scu.edu.cn/",
    "电子科技大学": "https://yz.uestc.edu.cn/",
    "西南交通大学": "https://yz.swjtu.edu.cn/",
    "西南财经大学": "https://yz.swufe.edu.cn/",
    "四川师范大学": "https://yjsc.sicnu.edu.cn/",
    "成都理工大学": "https://gra.cdut.edu.cn/",
    "西南科技大学": "http://www.swust.edu.cn/",
    "成都信息工程大学": "https://yjsc.cuit.edu.cn/",
    "西华大学": "https://yjs.xhu.edu.cn/",
    "成都大学": "https://yjsc.cdu.edu.cn/"
}

# --- School Module Mapping ---
# Maps school names to their corresponding scraper module filenames (without .py)
SCHOOL_MODULE_MAPPING = {
    "四川大学": "scu_scraper",
    "电子科技大学": "uestc_scraper",
    "西南交通大学": "swjtu_scraper",
    "西南财经大学": "swufe_scraper",
    "四川师范大学": "sicnu_scraper",
    "成都理工大学": "cdut_scraper",
    "西南科技大学": "swust_scraper",
    "成都信息工程大学": "cuit_scraper",
    "西华大学": "xhu_scraper",
    "成都大学": "cdu_scraper"
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

# def save_html_debug_log(html_content, school_name, page_type_suffix, timestamp, url="N/A", page_specific_detail=""):
#     try:
#         # Sanitize page_specific_detail for filename
#         sane_detail = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in page_specific_detail).rstrip()
#         detail_suffix = f"_{sane_detail}" if sane_detail else ""
#         
#         # Sanitize school_name
#         sane_school_name = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in school_name).rstrip()
#
#         # 修改后的文件名格式 (去掉了timestamp)
#         file_name = f"{sane_school_name}_{page_type_suffix}{detail_suffix}.html"
#         file_path = os.path.join(HTML_DEBUG_DIR, file_name)
#         
#         with open(file_path, 'w', encoding='utf-8') as f:
#             f.write(f"<!-- School: {school_name} -->\\n")
#             f.write(f"<!-- Page Type: {page_type_suffix}{detail_suffix.replace('_', ' ', 1)} -->\\n")
#             f.write(f"<!-- URL: {url} -->\\n")
#             if page_specific_detail and detail_suffix != f"_{page_specific_detail}": # Log original if sanitized
#                  f.write(f"<!-- Suffix/Detail: {page_specific_detail} -->\\n")
#             f.write(f"<!-- Saved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\\n\\n")
#             f.write(html_content)
#         # print(f"    [Debug] Saved HTML log: {file_path}")
#     except Exception as e:
#         print(f"    [Error] Failed to save HTML debug log for {school_name} {page_type_suffix}: {e}")

def save_error_log(school_name, error_message, timestamp, exception_obj=None):
    try:
        # 修改文件名，移除时间戳，确保每个学校只有一个日志文件，新的日志会覆盖旧的
        # Sanitize school_name for filename to avoid issues with special characters
        sane_school_name = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in school_name).rstrip()
        file_name = f"{sane_school_name}_error.txt"
        file_path = os.path.join(ERROR_LOG_DIR, file_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"School: {school_name}\n")
            f.write(f"Timestamp: {timestamp}\n") # 仍然在文件内容中记录时间戳
            f.write(f"Error Message: {error_message}\n\n")
            if exception_obj:
                f.write(f"Exception Type: {type(exception_obj).__name__}\n")
                f.write(f"Exception Details: {str(exception_obj)}\n\n")
                f.write("Traceback:\n")
                import traceback
                traceback.print_exc(file=f)
        print(f"    [ErrorLog] Saved error log: {file_path}")
    except Exception as e:
        print(f"    [Critical] Failed to save error log itself: {e}")

# --- Utility: Fetch Page Content ---
def fetch_page(url, school_name_for_log="", page_type_for_log="", page_specific_detail="", retries=MAX_RETRIES, delay=RETRY_DELAY, year_for_log=None, **kwargs):
    # Use the passed-in log-specific names internally for clarity if needed,
    # or simply use them directly for saving logs.
    school_name = school_name_for_log
    page_type_suffix_for_debug = page_type_for_log

    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_prefix = f"    [{school_name_for_log if school_name_for_log else 'Unknown School'}]"
    if year_for_log:
        log_prefix += f" ({year_for_log})"

    # Define headers locally within the function to ensure they are always fresh for each call
    active_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    # Always add these additional headers for all requests in fetch_page
    active_headers['DNT'] = '1'
    active_headers['Sec-Fetch-Dest'] = 'document'
    active_headers['Sec-Fetch-Mode'] = 'navigate'
    active_headers['Sec-Fetch-Site'] = 'none'
    active_headers['Sec-Fetch-User'] = '?1'
    active_headers['Cache-Control'] = 'max-age=0'

    if 'gra.cdut.edu.cn' in url:
        print(f"{log_prefix} Note: CDUT URL ({url}) is now using the standard full header set for requests-based fetch.")
    # No else needed, as all URLs processed by fetch_page will use the full set defined above

    try:
        # Suppress only the InsecureRequestWarning from urllib3 needed during development for bad SSL certs
        warnings.filterwarnings('ignore', category=InsecureRequestWarning)
        # Use headers_to_use instead of DEFAULT_HEADERS directly
        response = requests.get(url, headers=active_headers, timeout=REQUEST_TIMEOUT, verify=False, **kwargs) # Added verify=False, consider certs
        response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)
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
            # save_html_debug_log(response.text, school_name, page_type_suffix_for_debug, current_timestamp, url, current_page_specific_detail)
            pass # HTML 日志已禁用
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"  [{school_name}] 获取页面失败 (url: {url}): {e}")
        if retries > 0:
            print(f"    Retrying in {delay} seconds... ({retries} retries left)")
            time.sleep(delay)
            return fetch_page(url, school_name_for_log, page_type_for_log, page_specific_detail, retries - 1, delay, year_for_log, **kwargs)
        else:
            error_message = f"获取页面失败 (url: {url}): {e}"
            save_error_log(school_name, error_message, current_timestamp, e)
        return None
    except Exception as e_gen:
        print(f"  [{school_name}] 获取页面时发生未知错误 (url: {url}): {e_gen}")
        error_message = f"获取页面时发生未知错误 (url: {url}): {e_gen}"
        save_error_log(school_name, error_message, current_timestamp, e_gen)
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
        # options.add_argument('--headless') # Keep this commented for debugging for now
        options.add_argument('--disable-gpu') # Generally safe
        options.add_argument('--no-sandbox') # Often needed in containerized/CI environments
        options.add_argument('--disable-dev-shm-usage') # Also common for stability

        # Logic to decide WebDriver type based on the module-level switch
        if not _CURRENTLY_USING_UNDETECTED_DRIVER:
            # Options for standard Selenium WebDriver
            options.add_argument("user-agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            script_dir = os.path.dirname(__file__)
            project_root = os.path.dirname(script_dir)
            chromedriver_filename = "chromedriver.exe" if platform.system() == "Windows" else "chromedriver"
            chrome_driver_path = os.path.join(project_root, 'utils', chromedriver_filename)
            print(f"    [Selenium] 使用标准 ChromeDriver，路径: {chrome_driver_path}")
            service = Service(executable_path=chrome_driver_path)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            # Options for undetected_chromedriver (it handles many anti-detection measures itself)
            print(f"    [Selenium] 初始化 undetected_chromedriver (非 Headless - 调试模式)...")
            driver = uc.Chrome(options=options) 

    except WebDriverException as e:
        if not _CURRENTLY_USING_UNDETECTED_DRIVER:
            if "executable needs to be in PATH" in str(e) or "cannot be found" in str(e):
                 print(f"    [Selenium] 错误：在路径 '{chrome_driver_path}' 找不到 chromedriver...")
            elif "'chromedriver' executable may have wrong permissions" in str(e):
                  print(f"    [Selenium] 错误：'{chrome_driver_path}' 可能权限不足...")
            else:
                  print(f"    [Selenium] 初始化标准 WebDriver 时出错: {e}")
        else: # Errors specific to or when using undetected_chromedriver
            if "'chromedriver' executable may have wrong permissions" in str(e):
                 print(f"    [Selenium] 错误：chromedriver 可能权限不足 (uc)...")
            elif "session not created" in str(e).lower(): 
                 print(f"    [Selenium] WebDriver session not created (uc). Error: {e}")
                 print(f"                 确保您的 Chrome 浏览器已安装并且版本与 undetected_chromedriver 兼容。")
                 print(f"                 undetected_chromedriver 通常会自动下载匹配的 ChromeDriver。")
            else:
                 print(f"    [Selenium] 初始化 undetected_chromedriver 时出错: {e}")
        return None
    except Exception as e: # Catch-all for other potential errors during setup or get
         print(f"    [Selenium] 获取动态页面时发生未知错误 (Setup or Get): {e}")
         if driver: # try to quit driver if it was initialized
             driver.quit()
         return None

    # The rest of the function (driver.get(), actions, page_source, finally block) remains largely the same
    try:
        print(f"    [Selenium] 正在访问: {url}")
        driver.get(url)
        time.sleep(2) # Initial wait for page to begin loading

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
              print(f"    [Selenium] 未指定等待元素(点击后)，默认等待 10 秒...")
              time.sleep(10) # Increased from 5
              
        html_source = driver.page_source
        print(f"    [Selenium] 成功获取页面源码。")
        if html_source:
            # save_html_debug_log(html_source, school_name, page_type_suffix, datetime.now().strftime('%Y%m%d_%H%M%S'), url, page_specific_detail)
            pass # HTML 日志已禁用
        
    except TimeoutException:
        print(f"    [Selenium] 错误：等待元素选择器 '{selenium_actions[-1]['wait_after_click_selector']}' 超时 ({SELENIUM_TIMEOUT}秒)。页面可能未完全加载或元素不存在。")
        if driver:
             try:
                 screenshot_path = os.path.join(os.path.dirname(__file__), 'selenium_timeout_screenshot.png')
                 driver.save_screenshot(screenshot_path)
                 print(f"    [Selenium] 已保存超时截图到: {screenshot_path}")
                 # 也尝试保存此时的页面源码
                 timeout_html_source = driver.page_source
                 if timeout_html_source:
                     # save_html_debug_log(timeout_html_source, school_name, f"{page_type_suffix}_Timeout", datetime.now().strftime('%Y%m%d_%H%M%S'), url)
                     pass # HTML 日志已禁用
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
             
    print(f"    [Selenium] Returning html_source. Type: {type(html_source)}, Length: {len(html_source) if html_source is not None else 'None'}")
    
    # Save the HTML source to a debug file if it's not None
    if html_source is not None:
        sane_school_name = "".join(c if c.isalnum() else '_' for c in school_name)
        sane_page_type = "".join(c if c.isalnum() else '_' for c in page_type_suffix)
        sane_detail = "".join(c if c.isalnum() else '_' for c in page_specific_detail) if page_specific_detail else ""
        
        detail_part = f"_{sane_detail}" if sane_detail else ""
        debug_filename = f"selenium_debug_{sane_school_name}_{sane_page_type}{detail_part}.html"
        debug_file_path = os.path.join(os.path.dirname(__file__), debug_filename)
        try:
            with open(debug_file_path, 'w', encoding='utf-8') as f_debug:
                f_debug.write(f"<!-- URL: {url} -->\n")
                f_debug.write(f"<!-- School: {school_name}, Page Type: {page_type_suffix}, Detail: {page_specific_detail} -->\n")
                f_debug.write(f"<!-- Fetched at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\n")
                f_debug.write(html_source)
            print(f"    [Selenium] Saved HTML output for debugging to: {debug_file_path}")
        except Exception as e_save:
            print(f"    [Selenium] Error saving HTML debug output: {e_save}")
            
    return html_source

# --- Utility: Load School Targets ---
# def load_school_targets(csv_path): # 函数未使用，予以移除
#     # ... (保持原有 load_school_targets 函数内容) ...
#     pass 

# --- Main Parsing Orchestrator ---
# 该函数已被删除，其功能已由各个学校独立的爬虫模块和 run_scraper 中的动态调用取代。
# 旧的 parse_school_data 函数 (原行号 405-1307) 已移除。

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

def run_scraper(target_school_name=None): # Added optional parameter
    print("开始运行爬虫...")
    if target_school_name:
        print(f"目标大学: {target_school_name}")

    os.makedirs(CRAWLER_DIR, exist_ok=True) # Ensure crawler output directory exists

    schools_list = load_existing_schools()
    if not isinstance(schools_list, list):
        print("警告：现有学校数据格式错误或加载失败。将创建新的空列表。")
        schools_list = []
    elif not schools_list:
        print("警告：现有学校数据为空。爬取结果将作为新数据保存。")

    raw_crawler_data = {}
    schools_info_for_csv = [] 
    summary_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target_universities": list(TARGET_UNIVERSITIES.keys()) if not target_school_name else [target_school_name],
        "target_major_codes": list(TARGET_MAJOR_CODES),
        "schools_processed": 0,
        "schools_updated": 0,
        "total_departments_found": 0,
        "total_majors_found": 0
    }
    successful_updates = 0

    # utils_dir = os.path.dirname(os.path.abspath(__file__))
    # project_root = os.path.dirname(utils_dir)

    universities_to_process = {}
    if target_school_name:
        if target_school_name in TARGET_UNIVERSITIES:
            universities_to_process[target_school_name] = TARGET_UNIVERSITIES[target_school_name]
        else:
            print(f"!! 错误: 指定的大学 '{target_school_name}' 不在 TARGET_UNIVERSITIES 列表中。可用列表: {list(TARGET_UNIVERSITIES.keys())}")
            return
    else:
        universities_to_process = TARGET_UNIVERSITIES

    # --- 选择 WebDriver 类型 --- 
    # True 使用 undetected_chromedriver; False 使用标准 Selenium
    use_uc_driver_for_this_run = True 
    # --------------------------

    global _CURRENTLY_USING_UNDETECTED_DRIVER # Declare intent to modify global
    _CURRENTLY_USING_UNDETECTED_DRIVER = use_uc_driver_for_this_run

    if _CURRENTLY_USING_UNDETECTED_DRIVER:
        print("--- 本次运行将尝试使用 Undetected ChromeDriver ---")
    else:
        print("--- 本次运行将使用标准 Selenium WebDriver ---")

    for school_name, base_url in universities_to_process.items(): # Use the filtered list
        print(f"\n>>> 开始处理大学: {school_name} ({base_url})")
        current_school_info_for_csv = {
            "name": school_name, "url": base_url,
            "major_catalog_url": "", "score_line_url": ""
        }
        update_data = None
        
        module_short_name = SCHOOL_MODULE_MAPPING.get(school_name)

        if module_short_name:
            try:
                module_full_path = f"utils.school_scrapers.{module_short_name}"
                school_module = importlib.import_module(module_full_path)
                
                # 约定函数名为 scrape_{short_name_without_scraper}_data
                # e.g., scu_scraper -> scrape_scu_data
                # e.g., swufe_scraper -> scrape_swufe_data
                base_func_name_part = module_short_name.replace("_scraper", "")
                scrape_function_name = f"scrape_{base_func_name_part}_data"
                
                if hasattr(school_module, scrape_function_name):
                    scrape_function = getattr(school_module, scrape_function_name)
                    print(f"  -> 调用模块: {module_full_path}, 函数: {scrape_function_name}")
                    
                    # 传递参数给特定学校的爬虫函数
                    # 如果特定学校的爬虫需要 project_root 或 utils_dir，可以在这里传递
                    # update_data = scrape_function(base_url, school_name, project_root_dir=project_root)
                    update_data = scrape_function(base_url, school_name)
                else:
                    print(f"!! 错误: 在模块 {module_full_path} 中未找到函数 {scrape_function_name}。请确保函数名遵循约定。")
            except ImportError as e:
                print(f"!! 错误: 无法导入模块 {module_full_path} for {school_name}: {e}")
            except Exception as e_module:
                print(f"!! 错误: 运行 {school_name} 的爬虫模块 {module_short_name} 时发生错误: {e_module}")
                import traceback
                traceback.print_exc() # 打印详细的模块内错误堆栈
        else:
            print(f"!! 警告: 未在 SCHOOL_MODULE_MAPPING 中找到 {school_name} 对应的模块名。跳过。")

        if update_data:
            print(f"  -- 学校 {school_name} 返回了数据，准备处理...")
            current_school_info_for_csv["major_catalog_url"] = update_data.get("major_catalog_url", "")
            current_school_info_for_csv["score_line_url"] = update_data.get("score_line_url", "")
            raw_crawler_data[school_name] = update_data
            summary_data["schools_processed"] += 1
            
            departments_data = update_data.get("departments", [])
            if isinstance(departments_data, list):
                summary_data["total_departments_found"] += len(departments_data)
                total_majors_in_school = 0
                for dept in departments_data:
                    if isinstance(dept, dict) and isinstance(dept.get("majors"), list):
                        total_majors_in_school += len(dept["majors"])
                summary_data["total_majors_found"] += total_majors_in_school
                print(f"     提取到 {len(departments_data)} 个院系, {total_majors_in_school} 个专业.")
            else:
                print(f"  ![{school_name}] 警告: 'departments' data is not a list, skipping summary.")

            if update_school_data(schools_list, school_name, update_data): # update_school_data 函数保持不变
                successful_updates += 1
                summary_data["schools_updated"] += 1
        else:
            print(f"  -- 学校 {school_name} 未返回有效数据或爬取跳过。")

        schools_info_for_csv.append(current_school_info_for_csv)
        print(f"--- 等待 2 秒 (处理完: {school_name}) ---")
        time.sleep(2)

    save_crawler_raw_data(raw_crawler_data)
    save_crawler_schools_csv(schools_info_for_csv) 
    save_crawler_summary(summary_data)

    if successful_updates > 0:
        print(f"\n共成功更新 {successful_updates} 个学校的数据，正在保存到 {SCHOOLS_FILE}...")
        save_schools_data(schools_list)
    else:
        print(f"\n没有学校数据被成功更新，未保存 {SCHOOLS_FILE}。")
        
    print("\n爬虫运行结束。")

if __name__ == "__main__": 
    # --- 选择 WebDriver 类型 --- 
    # True 使用 undetected_chromedriver; False 使用标准 Selenium
    use_uc_driver_for_this_run = False
    # --------------------------

    global _CURRENTLY_USING_UNDETECTED_DRIVER # Declare intent to modify global
    _CURRENTLY_USING_UNDETECTED_DRIVER = use_uc_driver_for_this_run

    if _CURRENTLY_USING_UNDETECTED_DRIVER:
        print("--- 本次运行将尝试使用 Undetected ChromeDriver ---")
    else:
        print("--- 本次运行将使用标准 Selenium WebDriver ---")

    # 运行指定学校的爬虫，或所有学校
    # run_scraper(target_school_name="成都理工大学") 
    run_scraper() # 运行所有学校