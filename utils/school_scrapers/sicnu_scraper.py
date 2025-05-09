# utils/school_scrapers/sicnu_scraper.py
from ..scraper import fetch_page, TARGET_MAJOR_CODES, find_generic_link, parse_exam_subjects, TARGET_CATEGORY_PREFIXES
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin

# (如果学校爬虫需要Selenium，也可能需要导入)
# from öffentlichescraper import fetch_dynamic_page_with_selenium, webdriver, By, WebDriverWait, EC, TimeoutException, Service, Select

def scrape_sicnu_data(base_url, school_name):
    """
    四川师范大学的爬虫函数。
    """
    print(f"  [{school_name}] 开始为四川师范大学抓取数据...")
    school_update_data = {
        "departments": [],
        "major_catalog_url": "", 
        "score_line_url": ""     
    }
    parsed_majors_by_dept = {}
    temp_score_data = {}
    yearly_score_line_urls = {}
    
    # 1. 获取主页内容
    print(f"    [{school_name}] 获取主页: {base_url}")
    main_page_html = fetch_page(base_url, school_name_for_log=school_name, page_type_for_log="MainPage")
    if not main_page_html:
        print(f"    [{school_name}] 无法获取主页内容，跳过。")
        return None
    
    soup = BeautifulSoup(main_page_html, 'html.parser')

    # 2. 尝试找到专业目录链接和分数线链接
    # 川师的链接通常在 "招生工作" -> "硕士招生" 下的栏目
    catalog_keywords = ["硕士研究生招生专业目录", "招生专业目录", "招生简章"]
    # 检查是否有直接指向 /zsgz/sszs/zsjz.htm 或 /zsgz/sszs/zyml.htm 的链接
    found_catalog_url = find_generic_link(soup, base_url, catalog_keywords)
    if not found_catalog_url:
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            text = link_tag.get_text(strip=True)
            if ("专业目录" in text or "招生简章" in text) and \
                (re.search(r'/(zsjz|zyml|sszs)', href) or ".htm" in href):
                possible_url = urljoin(base_url, href)
                if "newsDetail" not in possible_url: # 避免点进具体新闻页，期望列表页或直接文件
                    found_catalog_url = possible_url
                    break

    if found_catalog_url:
        school_update_data["major_catalog_url"] = found_catalog_url
        print(f"    [{school_name}] (通用查找) 找到疑似专业目录链接: {found_catalog_url}")
    else:
        print(f"    [{school_name}] (通用查找) 未找到专业目录链接。")

    score_keywords = ["硕士研究生复试分数线", "复试分数线", "历年分数线"]
    # 检查是否有直接指向 /zsgz/sszs/fsfcx.htm 或新闻列表页
    score_index_page_url = find_generic_link(soup, base_url, score_keywords)
    if not score_index_page_url: # 尝试更通用的父级菜单
         parent_menu_link = soup.find('a', string=re.compile(r"复试与录取|分数线|历年信息"))
         if parent_menu_link and parent_menu_link.has_attr('href'):
             score_index_page_url = urljoin(base_url, parent_menu_link['href'])

    if score_index_page_url:
        print(f"    [{school_name}] 找到疑似分数线索引页: {score_index_page_url}")
        score_index_html = fetch_page(score_index_page_url, school_name_for_log=school_name, page_type_for_log="ScoreIndexPage_SICNU")
        if score_index_html:
            score_index_soup = BeautifulSoup(score_index_html, 'html.parser')
            for year in ["2024", "2023", "2022"]:
                year_score_link = score_index_soup.find('a', string=re.compile(f'{year}.*硕士.*复试.*分数线'), href=True)
                if not year_score_link: # 有些学校用title属性
                    year_score_link = score_index_soup.find('a', title=re.compile(f'{year}.*硕士.*复试.*分数线'), href=True)
                if year_score_link:
                    link_href = year_score_link['href']
                    abs_link = urljoin(score_index_page_url, link_href)
                    yearly_score_line_urls[year] = abs_link
                    print(f"      [{school_name}] 找到 {year} 分数线链接: {abs_link}")
                    if year == "2024": school_update_data["score_line_url"] = abs_link
            if not school_update_data["score_line_url"] and "2023" in yearly_score_line_urls:
                school_update_data["score_line_url"] = yearly_score_line_urls["2023"]
    else:
        print(f"    [{school_name}] (通用查找) 未找到分数线索引页。")

    # 3. 解析专业目录
    if school_update_data["major_catalog_url"] and not school_update_data["major_catalog_url"].lower().endswith(('.pdf', '.doc', '.docx')):
        print(f"    [{school_name}] 尝试解析专业目录页面: {school_update_data['major_catalog_url']}")
        catalog_html = fetch_page(school_update_data["major_catalog_url"], school_name_for_log=school_name, page_type_for_log="MajorCatalog_SICNU")
        if catalog_html:
            catalog_soup = BeautifulSoup(catalog_html, 'html.parser')
            # TODO: 四川师范大学专业目录HTML结构分析与解析，通常是表格
            # print(f"    [{school_name}] TODO: 四川师范大学专业目录HTML表格解析逻辑需实现。")

    elif school_update_data["major_catalog_url"]:
        print(f"    [{school_name}] 专业目录链接可能是文件: {school_update_data['major_catalog_url']}，需手动处理。")

    # 4. 解析分数线
    if yearly_score_line_urls:
        print(f"  [{school_name}] 开始解析分数线...")
        for year, url in yearly_score_line_urls.items():
            print(f"    [{school_name}] 尝试获取 {year} 分数线页面: {url}")
            score_html = fetch_page(url, school_name_for_log=school_name, page_type_for_log="ScoreLinePage_SICNU", year_for_log=year)
            if score_html:
                score_soup = BeautifulSoup(score_html, 'html.parser')
                # TODO: 四川师范大学分数线页面HTML结构分析与解析，通常是表格
                # print(f"    [{school_name}] TODO: 四川师范大学 {year} 分数线解析逻辑需实现。")
            time.sleep(1)
    
    # 5. 整合数据
    if parsed_majors_by_dept:
        for dept_name, majors in parsed_majors_by_dept.items():
            school_update_data["departments"].append({"department_name": dept_name, "majors": list(majors.values())})
    # TODO: 实现分数线数据 temp_score_data 到 school_update_data 的合并

    print(f"  [{school_name}] 四川师范大学数据抓取完成 (占位符)。")
    if not school_update_data["major_catalog_url"] and not school_update_data["score_line_url"] and not school_update_data["departments"]:
        print(f"    [{school_name}] 未找到任何有效信息，返回 None。")
        return None
        
    return school_update_data

# 示例辅助函数 (如果需要特定解析，可以取消注释并实现)
# def parse_sicnu_major_catalog(html_content, catalog_url):
#     # ...
#     return []

# def parse_sicnu_score_lines(html_content, score_url):
#     # ...
#     return {}

# def merge_score_data_into_departments(school_data, score_data):
#     # ...
#     return school_data 