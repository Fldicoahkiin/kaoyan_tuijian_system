import re
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from selenium import webdriver # For type hinting or direct use if options are complex
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service 
import platform
from datetime import datetime # For save_html_debug_log timestamp if used directly
import os

from ..scraper import (
    fetch_page,
    fetch_dynamic_page_with_selenium, # Although UESTC logic might call webdriver directly
    save_html_debug_log, 
    parse_exam_subjects, # Though UESTC iframe often lacks this directly
    TARGET_MAJOR_CODES,
    TARGET_CATEGORY_PREFIXES,
    # SELENIUM_TIMEOUT, # Constants like this might be better in a shared config or passed
    # REQUEST_TIMEOUT
)

# It might be better to pass driver options or the driver itself if the setup is complex
# For now, UESTC's selenium logic is quite specific and might be kept largely self-contained within its function

def _init_selenium_driver_for_uestc(project_root):
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') 
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("user-agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'")
    
    chromedriver_filename = "chromedriver.exe" if platform.system() == "Windows" else "chromedriver"
    chrome_driver_path = os.path.join(project_root, 'utils', chromedriver_filename)
    try:
        service = Service(executable_path=chrome_driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except WebDriverException as e_wd:
        print(f"    [Selenium UESTC] WebDriver 初始化错误: {e_wd}")
        return None
    except Exception as e_gen:
        print(f"    [Selenium UESTC] WebDriver 初始化时发生未知错误: {e_gen}")
        return None

def scrape_uestc_data(base_url, school_name, project_root_dir="../"):
    """
    Scrapes University of Electronic Science and Technology of China (UESTC) data.
    project_root_dir is relative to the location of this uestc_scraper.py file.
    """
    print(f"  [{school_name}] 应用电子科技大学特定解析逻辑 (from uestc_scraper.py)...")
    school_update_data = {
        "departments": [], 
        "major_catalog_url": "", 
        "score_line_url": ""     
    }
    parsed_majors_by_dept = {} 
    temp_score_data = {} # For storing parsed score lines before merging
    yearly_score_line_urls = {}

    # Fetch main page for link finding
    main_page_html = fetch_page(base_url, school_name_for_log=school_name, page_type_for_log="MainPage_UESTC_scraper")
    if not main_page_html:
        print(f"  [{school_name}] UESTC: 无法获取主页内容，跳过。")
        return None
    soup = BeautifulSoup(main_page_html, 'html.parser')

    # 1. Determine Major Catalog URL for UESTC
    target_catalog_year = 2025 # Or make this dynamic / a parameter
    known_catalog_url_pattern = f"https://yzbm.uestc.edu.cn/zsml/sszsml/index/{target_catalog_year}"
    print(f"    [{school_name}] UESTC: 优先尝试已知模式专业目录URL: {known_catalog_url_pattern}")
    # Simplified: Assume known pattern is the primary, fallback if Selenium fails later.
    uestc_major_catalog_page_url = known_catalog_url_pattern
    school_update_data["major_catalog_url"] = uestc_major_catalog_page_url
    # Fallback logic from main page if needed (can be re-added if direct URL fails often)
    # ... (code for finding catalog_link_tag from soup) ...

    # 2. Determine Score Line URLs for UESTC
    # Try to find a general score page link first
    score_link_main_tag = soup.find('a', string=re.compile(r'(分数线|历年分数|复试线)')) 
    uestc_score_line_index_page_url = None
    if score_link_main_tag and score_link_main_tag.has_attr('href'):
        href_val = score_link_main_tag['href']
        if href_val and not href_val.startswith(('#', 'javascript:')):
            uestc_score_line_index_page_url = urljoin(base_url, href_val)
            print(f"    [{school_name}] UESTC: 找到历年分数/分数线主链接: {uestc_score_line_index_page_url}")
            # Tentatively set this as the main score_line_url, may be overwritten by specific year
            school_update_data["score_line_url"] = uestc_score_line_index_page_url 
    else:
        print(f"    [{school_name}] UESTC: 未在主页找到主要的'历年分数'或'分数线'链接。")

    if uestc_score_line_index_page_url:
        score_index_html = fetch_page(uestc_score_line_index_page_url, school_name_for_log=school_name, page_type_for_log="ScoreIndexPage_UESTC_scraper")
        if score_index_html:
            score_index_soup = BeautifulSoup(score_index_html, 'html.parser')
            link_container = score_index_soup.find('div', id='news_list') or \
                             score_index_soup.find('ul', class_='news_list') or \
                             score_index_soup.find('div', id=re.compile(r'vsb_content'))
            if link_container:
                link_source = link_container.find('ul') or link_container
                all_links_in_source = link_source.find_all('a', href=True) 
                found_years_scores = set()
                for link_tag in all_links_in_source:
                    link_text = link_tag.text.strip()
                    link_href = link_tag.get('href')
                    for year_str in ["2024", "2023", "2022"]:
                        if re.search(year_str, link_text) and re.search(r'(复试|分数线|基本要求)', link_text):
                            if year_str not in found_years_scores:
                                url = urljoin(uestc_score_line_index_page_url, link_href)
                                yearly_score_line_urls[year_str] = url
                                print(f"        [{school_name}] UESTC: 找到 {year_str} 分数线链接: {url}")
                                found_years_scores.add(year_str)
                                if year_str == "2024": school_update_data["score_line_url"] = url
                                break
                if "2024" not in found_years_scores and "2023" in yearly_score_line_urls:
                    school_update_data["score_line_url"] = yearly_score_line_urls["2023"]
                elif "2024" not in found_years_scores and "2023" not in found_years_scores and "2022" in yearly_score_line_urls:
                    school_update_data["score_line_url"] = yearly_score_line_urls["2022"]
            else: print(f"      [{school_name}] UESTC: 在分数线入口页未能找到链接容器。")
        else: print(f"    [{school_name}] UESTC: 无法获取分数线入口页。")

    # 3. Parse Major Catalog (Selenium part for UESTC)
    if uestc_major_catalog_page_url:
        # This project_root_dir needs to be correctly determined or passed for chromedriver path
        # It assumes this script is in utils/school_scrapers, so utils is one level up.
        # The main scraper.py is in utils. If utils/chromedriver exists, this path should be utils/chromedriver
        # Let's assume the main scraper calls this and passes its own os.path.dirname(__file__) as project_utils_dir
        # Or more simply, the main scraper has the chromedriver path and passes it.
        # For now, using a simplified chromedriver path based on a conventional project structure.
        
        # Calculate project root from this script's location for chromedriver
        # utils/school_scrapers/uestc_scraper.py -> utils/ -> project_root
        current_script_dir = os.path.dirname(__file__)
        utils_dir = os.path.dirname(current_script_dir) # Should be utils/
        project_root = os.path.dirname(utils_dir) # Should be the main project root
        
        driver = None
        try:
            print(f"      [Selenium UESTC] 初始化 WebDriver...")
            # The chromedriver path is now calculated relative to this script's project root
            options = webdriver.ChromeOptions()
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument("user-agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'")
            # If USE_HEADLESS_BROWSER is needed, import from ..scraper
            # from ..scraper import USE_HEADLESS_BROWSER
            # if USE_HEADLESS_BROWSER: options.add_argument('--headless')
            
            chromedriver_filename = "chromedriver.exe" if platform.system() == "Windows" else "chromedriver"
            # Assuming chromedriver is in project_root/utils/
            chrome_driver_path = os.path.join(project_root, 'utils', chromedriver_filename) 
            
            service = Service(executable_path=chrome_driver_path)
            driver = webdriver.Chrome(service=service, options=options)
            print(f"      [Selenium UESTC] WebDriver 初始化成功。路径: {chrome_driver_path}")

            print(f"      [Selenium UESTC] 正在访问主目录页: {uestc_major_catalog_page_url}")
            driver.get(uestc_major_catalog_page_url)
            save_html_debug_log(driver.page_source, school_name, "MajorCatalog_UESTC_MainPage_Selenium_scraper", datetime.now().strftime('%Y%m%d_%H%M%S'), url=uestc_major_catalog_page_url)

            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#zsml-dept-tree li a")))
            department_links_to_click = []
            all_dept_links = driver.find_elements(By.CSS_SELECTOR, "#zsml-dept-tree li a")
            target_dept_keywords = ["计算机科学与工程学院", "信息与软件工程学院"]
            for link in all_dept_links:
                if any(keyword in link.text.strip() for keyword in target_dept_keywords):
                    department_links_to_click.append(link)
            
            if not department_links_to_click: print(f"      [Selenium UESTC] 未找到目标院系链接。" )

            for dept_link_element in department_links_to_click:
                dept_name_raw = dept_link_element.text.strip()
                dept_name_match = re.match(r'\d*\s*(.*)', dept_name_raw)
                dept_name_clean = dept_name_match.group(1).strip() if dept_name_match and dept_name_match.group(1) else dept_name_raw.strip()
                print(f"      [Selenium UESTC] 点击院系: '{dept_name_clean}'")
                try:
                    dept_link_element.click(); time.sleep(2)
                    WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "iframeContent")))
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
                    iframe_html = driver.page_source
                    save_html_debug_log(iframe_html, school_name, f"MajorCatalog_UESTC_iframe_scraper", datetime.now().strftime('%Y%m%d_%H%M%S'), url=driver.current_url, page_specific_detail=dept_name_clean)
                    iframe_soup = BeautifulSoup(iframe_html, 'html.parser')
                    major_table_in_iframe = iframe_soup.find('table')
                    if major_table_in_iframe:
                        rows = major_table_in_iframe.find_all('tr')
                        for r_idx, row in enumerate(rows):
                            cols = row.find_all('td')
                            if not cols or row.find('th') or len(cols) < 3: continue
                            major_code_raw = cols[0].text.strip()
                            major_code_match = re.match(r'^(\d{6})\s*', major_code_raw)
                            if major_code_match:
                                major_code = major_code_match.group(1)
                                if major_code in TARGET_MAJOR_CODES:
                                    major_name = cols[1].text.strip()
                                    enrollment = cols[2].text.strip()
                                    degree_type = "专业学位" if major_code.startswith("0854") else "学术学位"
                                    study_type = "全日制"
                                    if dept_name_clean not in parsed_majors_by_dept: parsed_majors_by_dept[dept_name_clean] = {}
                                    if major_code not in parsed_majors_by_dept[dept_name_clean]:
                                        parsed_majors_by_dept[dept_name_clean][major_code] = {
                                            "major_code": major_code, "major_name": major_name,
                                            "degree_type": degree_type, "study_type": study_type,
                                            "enrollment": enrollment, "exam_subjects": "信息待补充 (需点击详情)",
                                            "remarks": "信息待补充 (需点击详情)", "tuition_duration": "",
                                            "research_directions": [], "score_lines": {}
                                        }
                    driver.switch_to.default_content(); time.sleep(1)
                except TimeoutException: print(f"        [Selenium UESTC] 处理院系 '{dept_name_clean}' 时超时。" ); driver.switch_to.default_content()
                except Exception as e_iframe: print(f"        [Selenium/Parser UESTC] 处理院系 '{dept_name_clean}' 时出错: {e_iframe}"); driver.switch_to.default_content()
        except WebDriverException as e_wd:
            print(f"    [Selenium UESTC] WebDriver 操作时出错: {e_wd}")
        except Exception as e_main_sel:
            print(f"    [Selenium UESTC] 处理专业目录时发生未知错误: {e_main_sel}")
        finally:
            if driver: driver.quit()

        if parsed_majors_by_dept:
            final_departments_list = []
            for dept_key, majors_inner_dict in parsed_majors_by_dept.items():
                final_departments_list.append({"department_name": dept_key, "majors": list(majors_inner_dict.values())})
            school_update_data['departments'] = final_departments_list
            print(f"        -> UESTC 专业目录解析完成. 提取到 {len(final_departments_list)} 个院系.")
    else:
        print(f"  [{school_name}] UESTC: 未找到专业目录链接，跳过 Selenium 解析。")

    # 4. Parse Score Line Pages for UESTC
    if yearly_score_line_urls:
        print(f"  [{school_name}] UESTC: 开始解析各年份分数线...")
        for year, url in yearly_score_line_urls.items():
            score_html = fetch_page(url, school_name_for_log=school_name, page_type_for_log="ScoreLinePage_UESTC_scraper", year_for_log=year)
            if score_html:
                score_soup = BeautifulSoup(score_html, 'html.parser')
                content_div = score_soup.find('div', id=re.compile(r'vsb_content')) or \
                              score_soup.find('div', class_='v_news_content') or \
                              score_soup.find('div', class_=re.compile(r'(content|main|article)'))
                if content_div:
                    score_tables = content_div.find_all('table')
                    if score_tables:
                        score_table = score_tables[0] # Assume first table is the relevant one
                        rows = score_table.find_all('tr')
                        current_degree_type_from_table = "未知"
                        for r_idx, s_row in enumerate(rows):
                            cols = s_row.find_all(['td', 'th'])
                            if not cols: continue
                            col_texts = [col.get_text(strip=True) for col in cols]
                            if any("学术学位" in text for text in col_texts): current_degree_type_from_table = "学硕"; continue
                            if any("专业学位" in text for text in col_texts): current_degree_type_from_table = "专硕"; continue
                            if len(col_texts) < 2: continue
                            subject_text = col_texts[0]; total_score_text = col_texts[-1]
                            code_match_in_text = re.search(r'[(（]?(\d{2,4})[)）]?', subject_text)
                            category_code_prefix = ""
                            if code_match_in_text:
                                extracted_code = code_match_in_text.group(1)
                                if extracted_code.startswith("0854") and "0854" in TARGET_CATEGORY_PREFIXES: category_code_prefix = "0854"
                                elif extracted_code.startswith("08") and "08" in TARGET_CATEGORY_PREFIXES: category_code_prefix = "08"
                            score_val_match = re.search(r'^(\d{3,})$', total_score_text)
                            score = score_val_match.group(1) if score_val_match else None
                            if category_code_prefix and score:
                                final_degree_type = current_degree_type_from_table
                                if final_degree_type == "未知": # Basic inference
                                    if "电子信息" in subject_text or category_code_prefix == "0854": final_degree_type = "专硕"
                                    elif "工学" in subject_text or category_code_prefix == "08": final_degree_type = "学硕"
                                if year not in temp_score_data: temp_score_data[year] = {}
                                temp_score_data[year][f"{category_code_prefix}_{final_degree_type}"] = score
                    else: print(f"        [{school_name}] UESTC: {year} 分数线页内容区域未找到表格。")
                else: print(f"      [{school_name}] UESTC: {year} 分数线页未找到主要内容区域。")
            else: print(f"    [{school_name}] UESTC: 无法获取 {year} 分数线页面内容。")
            time.sleep(1)

    # 5. Merge score data into school_update_data['departments'] for UESTC
    if temp_score_data and school_update_data.get('departments'):
        print(f"  [{school_name}] UESTC: 开始将分数线数据合并到专业中...")
        majors_updated_with_scores = 0
        for dept in school_update_data['departments']:
            for major in dept.get('majors', []):
                major_code = major.get('major_code')
                if major_code:
                    score_key_prefix = '0854' if major_code.startswith('0854') else ( '08' if major_code.startswith('08') else "")
                    if score_key_prefix:
                        major_degree_type = major.get("degree_type", "")
                        major_type_for_score = "专硕" if "专业" in major_degree_type else "学硕"
                        score_key = f"{score_key_prefix}_{major_type_for_score}"
                        updated_score_for_major = False
                        if 'score_lines' not in major: major['score_lines'] = {}
                        for year, scores_by_cat_type in temp_score_data.items():
                            if score_key in scores_by_cat_type:
                                if major['score_lines'].get(year) != scores_by_cat_type[score_key]:
                                     major['score_lines'][year] = scores_by_cat_type[score_key]
                                     updated_score_for_major = True
                        if updated_score_for_major: majors_updated_with_scores += 1
        if majors_updated_with_scores > 0:
            print(f"    -> UESTC: 分数线合并完成，为 {majors_updated_with_scores} 个专业条目更新了分数线。")
        else:
            print(f"    -> UESTC: 未能合并分数线或数据已最新。")

    return school_update_data

if __name__ == '__main__':
    print("Direct test placeholder for uestc_scraper.py")
    # Add test code here if needed, e.g.:
    # test_data = scrape_uestc_data("https://yz.uestc.edu.cn/", "电子科技大学", project_root_dir="../../")
    # if test_data:
    #     import json
    #     print(json.dumps(test_data, indent=4, ensure_ascii=False)) 