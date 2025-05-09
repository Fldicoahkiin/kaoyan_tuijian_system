# utils/school_scrapers/swufe_scraper.py
# from ..scraper import fetch_page, find_generic_link # Import when needed

from ..scraper import fetch_page, TARGET_MAJOR_CODES, find_generic_link, save_html_debug_log, parse_exam_subjects, TARGET_CATEGORY_PREFIXES
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin

def scrape_swufe_data(base_url, school_name, **kwargs):
    """
    爬取西南财经大学的研究生招生信息。
    """
    print(f"  [{school_name}] 开始为西南财经大学抓取数据...")
    school_update_data = {
        "departments": [],
        "major_catalog_url": "",
        "score_line_url": ""
    }
    parsed_majors_by_dept = {}
    temp_score_data = {}
    yearly_score_line_urls = {}

    # 1. 获取主页内容并查找链接
    print(f"    [{school_name}] 获取主页: {base_url}")
    main_page_html = fetch_page(base_url, school_name_for_log=school_name, page_type_for_log="MainPage")
    if not main_page_html:
        print(f"    [{school_name}] 无法获取主页内容，跳过西南财经大学。")
        return None
    
    soup = BeautifulSoup(main_page_html, 'html.parser')
    save_html_debug_log(main_page_html, school_name, "MainPage_Fetched", "initial_swufe")

    # 尝试找到专业目录链接 (通常在"硕士招生" -> "招生简章"或"专业目录")
    catalog_keywords = ["硕士专业目录", "招生专业目录", "招生简章", "硕士研究生招生专业", "硕士招生简章"]
    # SWUFE 网站可能将链接放在特定栏目，如 /index/zsjz.htm 或 /zysml/sszyml.htm
    found_catalog_url = find_generic_link(soup, base_url, catalog_keywords)
    if not found_catalog_url:
        # 补充查找：检查特定模式的链接
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            text = link_tag.get_text(strip=True)
            if ("专业目录" in text or "招生简章" in text) and \
                (re.search(r'/(zsjz|zysml|ml)', href) or ".htm" in href or "list" in href):
                found_catalog_url = urljoin(base_url, href)
                break

    if found_catalog_url:
        school_update_data["major_catalog_url"] = found_catalog_url
        print(f"    [{school_name}] 找到疑似专业目录/简章链接: {found_catalog_url}")
        # TODO: 解析专业目录/简章页面。SWUFE专业目录可能是HTML页面或PDF。
    else:
        print(f"    [{school_name}] 未能自动找到专业目录/简章链接。")

    # 尝试找到分数线链接 (通常在"硕士招生" -> "复试分数线"或"历年数据")
    score_keywords = ["硕士复试分数线", "历年分数线", "复试分数线", "复试基本分数线", "往年数据"]
    # SWUFE 网站可能将分数线放在类似 /index/lnfs.htm 的地方
    score_index_page_url = find_generic_link(soup, base_url, score_keywords)
    if not score_index_page_url: # 备用查找，更宽松的关键词
        score_index_page_url = find_generic_link(soup, base_url, ["分数线", "复试录取", "招生信息"])

    if score_index_page_url:
        print(f"    [{school_name}] 找到疑似分数线索引页: {score_index_page_url}")
        score_index_html = fetch_page(score_index_page_url, school_name_for_log=school_name, page_type_for_log="ScoreIndexPage_SWUFE")
        if score_index_html:
            score_index_soup = BeautifulSoup(score_index_html, 'html.parser')
            save_html_debug_log(score_index_html, school_name, "ScoreIndexPage_Fetched", "swufe")
            for year in ["2024", "2023", "2022"]:
                year_score_link = score_index_soup.find('a', string=re.compile(f'{year}.*硕士.*复试.*分数线'), href=True)
                if not year_score_link:
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
        print(f"    [{school_name}] 未能自动找到分数线索引页。")

    # 3. 解析专业目录 (如果找到链接且为HTML)
    if school_update_data["major_catalog_url"] and not school_update_data["major_catalog_url"].lower().endswith(('.pdf', '.doc', '.docx')):
        print(f"    [{school_name}] 尝试解析专业目录页面: {school_update_data['major_catalog_url']}")
        catalog_html = fetch_page(school_update_data["major_catalog_url"], school_name_for_log=school_name, page_type_for_log="MajorCatalog_SWUFE")
        if catalog_html:
            save_html_debug_log(catalog_html, school_name, "MajorCatalog_Fetched", "swufe")
            catalog_soup = BeautifulSoup(catalog_html, 'html.parser')
            # TODO: 西南财经大学专业目录HTML结构分析与解析 (通常为表格)
            # print(f"    [{school_name}] TODO: 西南财经大学专业目录HTML表格解析逻辑需要根据实际页面结构实现。")
            tables = catalog_soup.find_all('table') # 寻找所有表格，可能需要更精确的定位
            # for table in tables:
                # try:
                    # rows = table.find_all('tr')
                    # if not rows: continue
                    # header_texts = [th.get_text(strip=True) for th in rows[0].find_all('th')]
                    # # 根据表头确定列索引，例如：
                    # # code_idx, name_idx, dept_idx, enroll_idx, subjects_idx = -1, -1, -1, -1, -1
                    # # ... (逻辑来从header_texts填充索引) ...
                    # for row in rows[1:]:
                        # cols = row.find_all('td')
                        # if len(cols) == len(header_texts):
                            # major_code = cols[code_idx].get_text(strip=True) if code_idx != -1 else ""
                            # if major_code in TARGET_MAJOR_CODES:
                                # dept_name = cols[dept_idx].get_text(strip=True) if dept_idx != -1 else "经济数学学院" # SWUFE特色
                                # major_name = cols[name_idx].get_text(strip=True) if name_idx != -1 else ""
                                # enrollment = cols[enroll_idx].get_text(strip=True) if enroll_idx != -1 else ""
                                # exam_subjects_html = cols[subjects_idx] if subjects_idx != -1 else ""
                                # exam_subjects = parse_exam_subjects(exam_subjects_html)
                                # # ... (构建major_dict并存入parsed_majors_by_dept)
                # except Exception as e:
                    # print(f"      [{school_name}] 解析专业目录表格出错: {e}")
            print(f"    [{school_name}] TODO: 西南财经大学专业目录HTML表格解析逻辑需实现。")

    elif school_update_data["major_catalog_url"]:
        print(f"    [{school_name}] 专业目录链接可能是文件: {school_update_data['major_catalog_url']}，需要手动处理。")

    # 4. 解析分数线 (如果找到链接)
    if yearly_score_line_urls:
        print(f"  [{school_name}] 开始解析分数线...")
        for year, url in yearly_score_line_urls.items():
            print(f"    [{school_name}] 尝试获取 {year} 分数线页面: {url}")
            score_html = fetch_page(url, school_name_for_log=school_name, page_type_for_log="ScoreLinePage_SWUFE", year_for_log=year)
            if score_html:
                save_html_debug_log(score_html, school_name, f"ScorePage_{year}_Fetched", "swufe")
                score_soup = BeautifulSoup(score_html, 'html.parser')
                # TODO: 西南财经大学分数线页面HTML结构分析与解析 (通常为表格)
                # print(f"    [{school_name}] TODO: 西南财经大学 {year} 分数线解析逻辑需要根据实际页面结构实现。")
            time.sleep(1)

    # 5. 整合数据 (与swjtu类似)
    if parsed_majors_by_dept:
        for dept_name, majors in parsed_majors_by_dept.items():
            school_update_data["departments"].append({"department_name": dept_name, "majors": list(majors.values())})
    # TODO: 实现分数线数据 temp_score_data 到 school_update_data["departments"][...]["majors"][...]["score_lines"] 的合并

    print(f"  [{school_name}] 西南财经大学数据抓取完成。")
    if not school_update_data["major_catalog_url"] and not school_update_data["score_line_url"] and not school_update_data["departments"]:
        print(f"    [{school_name}] 未找到西南财经大学的任何有效信息，返回 None。")
        return None
        
    return school_update_data

if __name__ == '__main__':
    print("Direct test placeholder for swufe_scraper.py")
    # test_data = scrape_swufe_data("https://yz.swufe.edu.cn/", "西南财经大学")
    # if test_data:
    #     import json
    #     print(json.dumps(test_data, indent=4, ensure_ascii=False)) 