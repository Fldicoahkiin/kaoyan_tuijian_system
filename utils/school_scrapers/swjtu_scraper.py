from ..scraper import fetch_page, TARGET_MAJOR_CODES, find_generic_link, save_html_debug_log, parse_exam_subjects, TARGET_CATEGORY_PREFIXES
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin

def scrape_swjtu_data(base_url, school_name, **kwargs):
    """
    爬取西南交通大学的研究生招生信息。
    """
    print(f"  [{school_name}] 开始为西南交通大学抓取数据...")
    school_update_data = {
        "departments": [],
        "major_catalog_url": "",
        "score_line_url": ""
    }
    parsed_majors_by_dept = {}
    temp_score_data = {}

    # 1. 获取主页内容并查找链接
    print(f"    [{school_name}] 获取主页: {base_url}")
    main_page_html = fetch_page(base_url, school_name_for_log=school_name, page_type_for_log="MainPage")
    if not main_page_html:
        print(f"    [{school_name}] 无法获取主页内容，跳过西南交通大学。")
        return None
    
    soup = BeautifulSoup(main_page_html, 'html.parser')
    save_html_debug_log(main_page_html, school_name, "MainPage_Fetched", "initial_swjtu")

    # 尝试找到专业目录链接 (通常在"招生信息" -> "硕士招生"下)
    # 西南交大网站结构可能将专业目录放在特定栏目下，如 /xwgg/zsgg.htm, /list.htm?type=7
    # 或者直接搜索 "专业目录" "招生简章"
    catalog_keywords = ["硕士专业目录", "招生专业目录", "招生简章", "硕士研究生招生专业"]
    # 查找包含这些关键词的链接，并且URL可能包含 'zsml', 'zyml', 'list', 'detail'
    found_catalog_url = find_generic_link(soup, base_url, catalog_keywords)
    # 补充查找：检查是否有直接指向 /zsxx/zyml/ 或类似路径的链接
    if not found_catalog_url:
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            text = link_tag.get_text(strip=True)
            if ("专业目录" in text or "招生简章" in text) and (re.search(r'/(zsxx|zyml|sszs)/.*(zyml|ml)', href) or "list" in href or ".htm" in href):
                found_catalog_url = urljoin(base_url, href)
                break
    
    if found_catalog_url:
        school_update_data["major_catalog_url"] = found_catalog_url
        print(f"    [{school_name}] 找到疑似专业目录/简章链接: {found_catalog_url}")
        # TODO: 需要进一步解析此页面，可能是一个列表页或者直接是PDF/Word文档链接
        # 如果是列表页，需要找到具体的专业目录文件或页面
        # 此处仅记录入口URL，具体解析待细化
    else:
        print(f"    [{school_name}] 未能自动找到专业目录/简章链接。")

    # 尝试找到分数线链接 (通常在"招生信息" -> "硕士招生" -> "复试分数线")
    score_keywords = ["硕士复试分数线", "历年分数线", "复试分数线", "复试基本分数线"]
    yearly_score_line_urls = {}
    # 查找包含这些关键词的链接，并且URL可能包含 'fsx', 'lnfs', 'score'
    # 西南交大的分数线页面通常是新闻列表形式
    # 尝试寻找一个总的入口页面，如 "历年分数线" 或 "复试通知"
    score_index_page_url = find_generic_link(soup, base_url, ["复试与录取", "复试分数线", "历年分数线", "招生动态"])

    if score_index_page_url:
        print(f"    [{school_name}] 找到疑似分数线索引页: {score_index_page_url}")
        score_index_html = fetch_page(score_index_page_url, school_name_for_log=school_name, page_type_for_log="ScoreIndexPage_SWJTU")
        if score_index_html:
            score_index_soup = BeautifulSoup(score_index_html, 'html.parser')
            save_html_debug_log(score_index_html, school_name, "ScoreIndexPage_Fetched", "swjtu")
            # 在索引页中查找具体年份的分数线链接
            for year in ["2024", "2023", "2022"]:
                # 例如: "西南交通大学2024年硕士研究生招生复试基本分数线"
                year_score_link = score_index_soup.find('a', string=re.compile(f'{year}.*硕士.*复试.*分数线'), href=True)
                if not year_score_link:
                     year_score_link = score_index_soup.find('a', title=re.compile(f'{year}.*硕士.*复试.*分数线'), href=True)
                if year_score_link:
                    link_href = year_score_link['href']
                    abs_link = urljoin(score_index_page_url, link_href) # 确保是绝对路径
                    yearly_score_line_urls[year] = abs_link
                    print(f"      [{school_name}] 找到 {year} 分数线链接: {abs_link}")
                    if year == "2024": # 将最新年份的设置为主分数线URL
                        school_update_data["score_line_url"] = abs_link
            if not school_update_data["score_line_url"] and "2023" in yearly_score_line_urls: # Fallback
                school_update_data["score_line_url"] = yearly_score_line_urls["2023"]
    else:
        print(f"    [{school_name}] 未能自动找到分数线索引页。")

    # 3. 解析专业目录 (如果找到链接)
    # 西南交大的专业目录通常是HTML表格或者PDF附件。这里优先处理HTML表格。
    if school_update_data["major_catalog_url"] and not school_update_data["major_catalog_url"].lower().endswith(('.pdf', '.doc', '.docx')):
        print(f"    [{school_name}] 尝试解析专业目录页面: {school_update_data['major_catalog_url']}")
        catalog_html = fetch_page(school_update_data["major_catalog_url"], school_name_for_log=school_name, page_type_for_log="MajorCatalog_SWJTU")
        if catalog_html:
            save_html_debug_log(catalog_html, school_name, "MajorCatalog_Fetched", "swjtu")
            catalog_soup = BeautifulSoup(catalog_html, 'html.parser')
            # TODO: 西南交通大学专业目录HTML结构分析与解析
            # 查找包含专业信息的表格，通常会有表头如 "学院名称", "专业代码", "专业名称", "拟招生人数", "考试科目"
            tables = catalog_soup.find_all('table') # 或者更精确的 table selector
            # print(f"      [{school_name}] 找到 {len(tables)} 个表格，尝试解析...")
            # for table_idx, table in enumerate(tables):
                # try:
                    # major_rows = table.find_all('tr')
                    # current_dept = "未知院系"
                    # for row in major_rows[1:]: # 跳过表头
                        # cols = row.find_all('td')
                        # if len(cols) > 4: # 假设至少有 专业代码、名称、招生人数、考试科目等列
                            # major_code = cols[1].get_text(strip=True)
                            # if major_code in TARGET_MAJOR_CODES:
                                # dept_name_raw = cols[0].get_text(strip=True) # 假设第一列是院系
                                # if dept_name_raw: current_dept = dept_name_raw
                                # major_name = cols[2].get_text(strip=True)
                                # enrollment = cols[3].get_text(strip=True)
                                # exam_subjects_html = cols[4] # HTML片段
                                # exam_subjects = parse_exam_subjects(exam_subjects_html)
                                
                                # degree_type = "专业学位" if major_code.startswith("0854") else "学术学位"
                                # study_type = "全日制"
                                
                                # if current_dept not in parsed_majors_by_dept:
                                #     parsed_majors_by_dept[current_dept] = {}
                                # parsed_majors_by_dept[current_dept][major_code] = {
                                #     "major_code": major_code, "major_name": major_name,
                                #     "degree_type": degree_type, "study_type": study_type,
                                #     "enrollment": {"2024": enrollment}, "exam_subjects": exam_subjects,
                                #     "remarks": "", "tuition_duration": "",
                                #     "research_directions": [], "score_lines": {}
                                # }
                # except Exception as e:
                    # print(f"      [{school_name}] 解析专业目录表格 {table_idx} 出错: {e}")
            print(f"    [{school_name}] TODO: 西南交通大学专业目录HTML表格解析逻辑需要根据实际页面结构实现。")
    elif school_update_data["major_catalog_url"]:
        print(f"    [{school_name}] 专业目录链接可能是文件: {school_update_data['major_catalog_url']}，需要手动下载和解析。")

    # 4. 解析分数线 (如果找到链接)
    if yearly_score_line_urls:
        print(f"  [{school_name}] 开始解析分数线...")
        for year, url in yearly_score_line_urls.items():
            print(f"    [{school_name}] 尝试获取 {year} 分数线页面: {url}")
            score_html = fetch_page(url, school_name_for_log=school_name, page_type_for_log="ScoreLinePage_SWJTU", year_for_log=year)
            if score_html:
                save_html_debug_log(score_html, school_name, f"ScorePage_{year}_Fetched", "swjtu")
                score_soup = BeautifulSoup(score_html, 'html.parser')
                # TODO: 西南交通大学分数线页面HTML结构分析与解析
                # 通常分数线信息也在表格中，包含 "学科门类"/"专业学位类别", "总分", "单科" 等
                # tables = score_soup.find_all('table')
                # for table in tables:
                    # rows = table.find_all('tr')
                    # for row in rows[1:]:
                        # cols = row.find_all('td')
                        # if len(cols) > 2: # 假设至少有类别、总分
                            # category_name_raw = cols[0].get_text(strip=True)
                            # total_score_raw = cols[1].get_text(strip=True) # 或者其他列
                            # score_match = re.search(r'\d+', total_score_raw)
                            # if score_match:
                                # total_score = score_match.group(0)
                                # for prefix in TARGET_CATEGORY_PREFIXES:
                                    # if prefix in category_name_raw or any(target_code.startswith(prefix) for target_code in TARGET_MAJOR_CODES if category_name_raw in target_code_to_name_map.get(target_code, "")):
                                        # if year not in temp_score_data: temp_score_data[year] = {}
                                        # temp_score_data[year][prefix + "_综合"] = total_score # 使用更通用的键
                print(f"    [{school_name}] TODO: 西南交通大学 {year} 分数线解析逻辑需要根据实际页面结构实现。")
            time.sleep(1)

    # 5. 整合数据
    if parsed_majors_by_dept:
        for dept_name, majors in parsed_majors_by_dept.items():
            school_update_data["departments"].append({"department_name": dept_name, "majors": list(majors.values())})
    
    # 合并分数线到专业 (如果专业数据和分数线数据都已解析)
    # if temp_score_data and school_update_data["departments"]:
    #     for dept_info in school_update_data["departments"]:
    #         for major_info in dept_info["majors"]:
    #             major_code = major_info["major_code"]
    #             prefix_to_check = major_code[:4] if major_code.startswith("0854") else major_code[:2]
    #             for year, scores in temp_score_data.items():
    #                 if (prefix_to_check + "_综合") in scores:
    #                     if "score_lines" not in major_info: major_info["score_lines"] = {}
    #                     major_info["score_lines"][year] = scores[prefix_to_check + "_综合"]

    print(f"  [{school_name}] 西南交通大学数据抓取完成。")
    if not school_update_data["major_catalog_url"] and not school_update_data["score_line_url"] and not school_update_data["departments"]:
        print(f"    [{school_name}] 未找到西南交通大学的任何有效信息，返回 None。")
        return None
        
    return school_update_data

if __name__ == '__main__':
    print("Direct test placeholder for swjtu_scraper.py")
    # test_data = scrape_swjtu_data("https://yz.swjtu.edu.cn/", "西南交通大学")
    # if test_data:
    #     import json
    #     print(json.dumps(test_data, indent=4, ensure_ascii=False)) 