import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time # Added for potential delays
import os # For HTML_DEBUG_DIR if used directly, though save_html_debug_log handles it

# Import common utilities from the parent 'scraper' module
# Assuming scraper.py will be the main coordinator and provide these
from ..scraper import (
    fetch_page, 
    fetch_dynamic_page_with_selenium,
    parse_exam_subjects,
    save_html_debug_log, # If SCU specific HTML logging is needed beyond what fetch_page does
    TARGET_MAJOR_CODES,
    TARGET_CATEGORY_PREFIXES,
    # HTML_DEBUG_DIR # Not directly needed if save_html_debug_log is used
)

def scrape_scu_data(base_url, school_name):
    """
    Scrapes Sichuan University's postgraduate admission information.
    """
    print(f"  [{school_name}] 应用四川大学特定解析逻辑 (from scu_scraper.py)...")
    school_update_data = {
        "departments": [], 
        "major_catalog_url": "", 
        "score_line_url": ""     
    }
    parsed_majors_by_dept = {} 
    temp_score_data = {} # For storing parsed score lines before merging
    score_line_urls = {} # Stores URLs for different years' score pages


    # Fetch main page to find links (if not overridden)
    # This part might be slightly different if main_page_html is passed or fetched by coordinator
    main_page_html = fetch_page(base_url, school_name_for_log=school_name, page_type_for_log="MainPage_SCU_scraper")
    if not main_page_html:
        print(f"  [{school_name}] SCU: 无法获取主页内容，跳过。")
        return None
    soup = BeautifulSoup(main_page_html, 'html.parser')

    # 1. Find Major Catalog URL from SCU main page
    major_link = soup.select_one('a[href="/sszyml/index"]') 
    if major_link:
        major_catalog_url = urljoin(base_url, major_link['href'])
        print(f"  [{school_name}] SCU: 找到专业目录链接: {major_catalog_url}")
        school_update_data["major_catalog_url"] = major_catalog_url
    else:
        print(f"  [{school_name}] SCU: 未找到预期的专业目录链接。")
        major_catalog_url = None # Ensure it's None if not found

    # 2. Find Historical Data / Score Line URLs from SCU main page
    history_link = soup.select_one('a[href="/zsxx/newslist/a/ls"]') 
    if history_link:
        historical_data_url = urljoin(base_url, history_link['href'])
        print(f"  [{school_name}] SCU: 找到历年数据链接: {historical_data_url}")
        history_page_html = fetch_page(historical_data_url, school_name_for_log=school_name, page_type_for_log="HistoricalDataIndexPage_SCU_scraper")
        if history_page_html:
            history_soup = BeautifulSoup(history_page_html, 'html.parser')
            print(f"    [{school_name}] SCU: 正在解析历年数据页面...")
            data_list_ul = history_soup.find('ul', class_='data-list')
            if data_list_ul:
                for year in ["2024", "2023", "2022"]:
                    score_link_tag = data_list_ul.find('a', string=re.compile(f'{year}.*硕士.*复试.*成绩基本要求'))
                    if score_link_tag and score_link_tag.has_attr('href'):
                        link_href = score_link_tag['href']
                        # Use historical_data_url as base for relative links from this page
                        score_line_urls[year] = urljoin(historical_data_url, link_href) 
                        print(f"      [{school_name}] SCU: 找到 {year} 分数线链接: {score_line_urls[year]}")
                        if year == "2024": 
                            school_update_data["score_line_url"] = score_line_urls[year]
                    else:
                        print(f"      [{school_name}] SCU: 未在数据列表中找到 {year} 分数线的链接。")
            else:
                print(f"    [{school_name}] SCU: 未在历年数据页找到 class='data-list' 的列表。")
        else:
             print(f"  [{school_name}] SCU: 无法获取历年数据页面内容。")
    else:
        print(f"  [{school_name}] SCU: 未找到预期的历年数据链接。")
       
    # 3. Parse Major Catalog (Selenium part)
    if major_catalog_url:
        print(f"  [{school_name}] SCU: 尝试使用 Selenium 访问专业目录页: {major_catalog_url}")
        # Note: Selenium actions for SCU might need to be defined here or passed
        # For now, assuming a simplified action or that it's embedded in fetch_dynamic_page_with_selenium if specific to SCU
        scu_selenium_actions = [
            # Example: {"dropdown_id": "yxslist", "option_value": "304", "wait_after_select": 1}, 
            # This should select a specific department if needed, or be empty for all.
            # For SCU, the example used a specific department, let's make it more general or configurable
            # For now, an action to search/wait for table might be enough if no pre-selection needed.
            # {"click_button_id": "searchbtn", "wait_after_click_selector": "#datatabel tbody tr"} # Click and wait
            {"dropdown_id": "yxslist", "option_value": "304"}, # 选择 计算机学院（软件学院、智能科学与技术学院）
            {"dropdown_id": "Yearlist", "option_value": "2025"}, # 确保选择2025年
            {"click_button_id": "searchbtn", "wait_after_click_selector": "#datatabel tbody tr"}
        ]
        catalog_html = fetch_dynamic_page_with_selenium(
            url=major_catalog_url,
            school_name=school_name, 
            page_type_suffix="MajorCatalog_SCU_Selenium_scraper",
            selenium_actions=scu_selenium_actions
        ) 
        if catalog_html:
            print(f"    [{school_name}] SCU: 使用 BeautifulSoup 解析 Selenium 获取的专业目录源码...")
            catalog_soup = BeautifulSoup(catalog_html, 'html.parser')
            major_table = catalog_soup.find('table', id='datatabel')
            if major_table:
                tbody = major_table.find('tbody')
                if tbody:
                    major_rows = tbody.find_all('tr')
                    print(f"      [{school_name}] SCU: 在专业目录页找到 ID='datatabel' 的表格，共 {len(major_rows)} 行。开始解析...")
                    
                    current_dept_name = "未知院系" 
                    current_major_code = None
                    # current_major_name = None # Defined when major header found
                    # current_degree_type = None # Typically part of major, not direction
                    # current_study_type = None # Typically part of major, not direction
                    
                    for i, m_row in enumerate(major_rows):
                        m_cols = m_row.find_all('td')
                        num_cols = len(m_cols)

                        try:
                            if num_cols >= 1 and m_cols[0].find('h3'):
                                dept_name_raw = m_cols[0].find('h3').text.strip()
                                match = re.match(r'\d+\s+(.*)', dept_name_raw) 
                                current_dept_name = match.group(1) if match else dept_name_raw
                                print(f"        ---> SCU: Detected Department: '{current_dept_name}'")
                                current_major_code = None 
                                continue 

                            col0_h4 = m_cols[0].find('h4') if num_cols > 0 else None
                            is_major_header = num_cols == 5 and col0_h4 and re.match(r'^\d{6}\s+', col0_h4.text.strip())
                            
                            if is_major_header:
                                col0_text = col0_h4.text.strip()
                                major_code_match = re.match(r'^(\d{6})\s+(.*)', col0_text)
                                if major_code_match:
                                    current_major_code = major_code_match.group(1)
                                    current_major_name = major_code_match.group(2).strip()
                                    # Degree type and study type are usually inferred or found with major, not from SCU table directly here
                                    current_degree_type = "未知" # Placeholder
                                    current_study_type = "全日制" # Default assumption
                                    if current_major_code.startswith("0854"): # Common for professional
                                        current_degree_type = "专业学位"
                                    elif current_major_code.startswith("0812") or current_major_code.startswith("0835") or current_major_code.startswith("0839"):
                                        current_degree_type = "学术学位"


                                    if current_major_code in TARGET_MAJOR_CODES:
                                        print(f"          -> SCU: MATCHED TARGET MAJOR! Initializing entry: {current_major_code} {current_major_name}")
                                        if current_dept_name not in parsed_majors_by_dept:
                                            parsed_majors_by_dept[current_dept_name] = {}
                                        
                                        enrollment_raw = m_cols[2].text.strip()
                                        enrollment_match = re.search(r'\d+', enrollment_raw)
                                        enrollment = enrollment_match.group(0) if enrollment_match else enrollment_raw
                                        
                                        parsed_majors_by_dept[current_dept_name][current_major_code] = {
                                            "major_code": current_major_code,
                                            "major_name": current_major_name,
                                            "degree_type": current_degree_type, # From logic above
                                            "study_type": current_study_type, # Default or from logic
                                            "enrollment": {"2024": enrollment, "2023": "信息待补充", "2022": "信息待补充"},
                                            "exam_subjects": "信息待补充", 
                                            "remarks": "信息待补充",          
                                            "tuition_duration": "信息待补充",
                                            "research_directions": [],
                                            "score_lines": {}
                                        }
                                    else: 
                                        current_major_code = None 
                                else: 
                                    current_major_code = None 
                                continue 
                            
                            # Direction Row for a TARGET major
                            if num_cols == 5 and current_major_code and (parsed_majors_by_dept.get(current_dept_name, {}).get(current_major_code) is not None):
                                major_dict_to_update = parsed_majors_by_dept[current_dept_name][current_major_code]
                                direction_name = m_cols[0].text.strip()
                                advisors = m_cols[1].text.strip().replace('\n', ' ').strip()
                                
                                # Parse subjects if present in this direction's row (typically first direction row due to rowspan)
                                if 'display: none;' not in m_cols[3].get('style', '') and m_cols[3].text.strip():
                                    subjects_col_html_content = str(m_cols[3])
                                    parsed_subjects = parse_exam_subjects(subjects_col_html_content)
                                    if parsed_subjects != "信息待补充":
                                        major_dict_to_update['exam_subjects'] = parsed_subjects

                                # Parse remarks/tuition if present
                                if 'display: none;' not in m_cols[4].get('style', '') and m_cols[4].text.strip():
                                    remarks_col_html_content = str(m_cols[4])
                                    current_remarks_raw = BeautifulSoup(remarks_col_html_content, 'html.parser').get_text(separator=' ', strip=True)
                                    if current_remarks_raw:
                                        major_dict_to_update['remarks'] = current_remarks_raw
                                        tuition_match = re.search(r'学费：\s*(\d+元/生\.年)', current_remarks_raw)
                                        duration_match = re.search(r'学制：\s*(\d+\s*年)', current_remarks_raw)
                                        tuition = tuition_match.group(1) if tuition_match else ""
                                        duration = duration_match.group(1) if duration_match else ""
                                        current_tuition_duration = f"{tuition}, {duration}".strip(', ') if (tuition or duration) else ""
                                        if current_tuition_duration:
                                             major_dict_to_update['tuition_duration'] = current_tuition_duration
                                
                                if direction_name or advisors:
                                    major_dict_to_update['research_directions'].append({
                                        "direction_name": direction_name,
                                        "advisors": advisors
                                    })
                        except Exception as e:
                            print(f"        [SCU Row {i+1}] Exception during processing: {e}")
                else: 
                    print(f"    [{school_name}] SCU: 在专业目录页 ID='datatabel' 的表格中未找到 <tbody>。")
            else: 
                print(f"    [{school_name}] SCU: 未能在专业目录页找到 ID='datatabel' 的表格。")
            
            # Convert parsed_majors_by_dept to the list structure for school_update_data
            final_departments_list = []
            total_target_majors_found = 0
            for dept_key, majors_inner_dict in parsed_majors_by_dept.items():
                list_of_major_dicts = list(majors_inner_dict.values())
                if list_of_major_dicts:
                    final_departments_list.append({
                        "department_name": dept_key,
                        "majors": list_of_major_dicts
                    })
                    total_target_majors_found += len(list_of_major_dicts)
            print(f"      -> SCU Processed. Found {total_target_majors_found} target majors in {len(final_departments_list)} departments.")
            school_update_data['departments'] = final_departments_list
        else:
            print(f"  [{school_name}] SCU: Selenium 未能获取专业目录页面内容。")
           
    # 4. Parse Score Line Pages
    if score_line_urls:
        print(f"  [{school_name}] SCU: 开始解析分数线...")
        for year, url in score_line_urls.items():
            print(f"    [{school_name}] SCU: 尝试获取 {year} 分数线页面: {url}")
            score_html = fetch_page(url, school_name_for_log=school_name, page_type_for_log="ScoreLinePage_SCU_scraper", year_for_log=year)
            if score_html:
                score_soup = BeautifulSoup(score_html, 'html.parser')
                try:
                    score_table = score_soup.find('table', class_='Table')
                    if not score_table:
                        content_box_div = score_soup.find('div', class_='content-box')
                        if content_box_div:
                            score_table = content_box_div.find('table')

                    if score_table:
                        score_rows = score_table.find_all('tr')
                        is_academic_section = False
                        is_professional_section = False
                        for s_row in score_rows:
                            s_cols = s_row.find_all('td')
                            if not s_cols or len(s_cols) < 5:
                                header_text = s_row.get_text(strip=True)
                                if "学术学位" in header_text: is_academic_section = True; is_professional_section = False; continue
                                elif "专业学位" in header_text: is_academic_section = False; is_professional_section = True; continue
                                elif "专项计划" in header_text or "其他" in header_text: break
                                continue
                            try:
                                category_code_raw = s_cols[0].text.strip()
                                category_code_match = re.match(r"(\d+)", category_code_raw)
                                category_code = category_code_match.group(1) if category_code_match else category_code_raw
                                # category_name = s_cols[1].text.strip() # Not strictly needed for temp_score_data key
                                total_score_raw = s_cols[4].text.strip()
                                total_score_match = re.search(r'\d+', total_score_raw)
                                total_score = total_score_match.group(0) if total_score_match else total_score_raw
                                current_prefix_to_check = category_code[:4] if category_code.startswith("0854") else category_code[:2]
                                
                                if current_prefix_to_check in TARGET_CATEGORY_PREFIXES:
                                    score_type_detail = "学硕" if is_academic_section else ("专硕" if is_professional_section else "未知类型")
                                    # Ensure year key exists in temp_score_data
                                    if year not in temp_score_data: 
                                        temp_score_data[year] = {}
                                    temp_score_data[year][f"{current_prefix_to_check}_{score_type_detail}"] = total_score
                            except Exception as score_row_e:
                                print(f"      [SCU Score Row Error] {year}: {score_row_e}")
                    else:
                        print(f"  [{school_name}] SCU: {year} 分数线页未找到表格。")
                except Exception as score_e:
                    print(f"  [{school_name}] SCU: 解析 {year} 分数线页面出错: {score_e}")
            else:
                print(f"  [{school_name}] SCU: 无法获取 {year} 分数线页面。")
            time.sleep(1) # Be polite
    else:
         print(f"  [{school_name}] SCU: 未找到分数线链接，跳过解析。")

    # 5. Merge score data directly into school_update_data['departments']
    if temp_score_data and school_update_data.get('departments'):
        print(f"  [{school_name}] SCU: 开始将分数线数据合并到专业中...")
        majors_updated_with_scores = 0
        for dept in school_update_data['departments']:
            for major in dept.get('majors', []):
                major_code = major.get('major_code')
                if major_code:
                    score_key_prefix = ""
                    if major_code.startswith('0854'): score_key_prefix = '0854'
                    elif major_code.startswith('08'): score_key_prefix = '08'
                    
                    if score_key_prefix:
                        # Infer major_type from major data, not just a default
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
                        if updated_score_for_major:
                            majors_updated_with_scores += 1
        if majors_updated_with_scores > 0:
            print(f"    -> SCU: 分数线合并完成，共为 {majors_updated_with_scores} 个专业条目添加/更新了分数线信息。")
        else:
            print(f"    -> SCU: 未能将任何大类分数线合并到专业数据中或数据已是最新。")

    return school_update_data

if __name__ == '__main__':
    # Example for direct testing (requires scraper.py to be in parent and runnable)
    # This part needs to be adjusted based on how common utils are structured
    # from ..scraper import setup_logging # Assuming setup_logging is a common func
    # setup_logging() 
    print("Testing SCU scraper directly...")
    # Mock base_url and school_name for testing
    # scu_data = scrape_scu_data("https://yz.scu.edu.cn/", "四川大学")
    # if scu_data:
    #     import json
    #     print(json.dumps(scu_data, indent=4, ensure_ascii=False))
    # else:
    #     print("SCU scraper returned no data.")
    print("Direct test placeholder for scu_scraper.py") 