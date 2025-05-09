# utils/school_scrapers/cdut_scraper.py
from ..scraper import fetch_page, TARGET_MAJOR_CODES, find_generic_link, parse_exam_subjects
from bs4 import BeautifulSoup # 如果进行HTML解析则需要
import re
import time
from urllib.parse import urljoin # Added import

# (如果学校爬虫需要Selenium，也可能需要导入)
from ..scraper import fetch_dynamic_page_with_selenium, webdriver, By, WebDriverWait, EC, TimeoutException, Service, Select

def scrape_cdut_data(base_url, school_name):
    """
    成都理工大学的爬虫函数。
    """
    print(f"  [{school_name}] 开始为成都理工大学抓取数据...")
    school_update_data = {
        "departments": [],
        "major_catalog_url": "", 
        "score_line_url": ""     
    }
    
    # 1. 获取主页内容 (使用 Selenium)
    print(f"    [{school_name}] 使用 Selenium 获取主页: {base_url}")
    main_page_html = fetch_dynamic_page_with_selenium(base_url, school_name, page_type_suffix="MainPage_Selenium")

    # DEBUG: Check the received main_page_html in cdut_scraper.py
    print(f"    [{school_name}] In cdut_scraper.py - main_page_html Type: {type(main_page_html)}, Length: {len(main_page_html) if main_page_html is not None else 'None'}")

    if not main_page_html:
        print(f"    [{school_name}] 无法获取主页内容 (Selenium)，跳过。")
        return None
    
    main_soup = BeautifulSoup(main_page_html, 'html.parser')
    # save_html_debug_log(main_page_html, school_name, "MainPage_Fetched", "initial") # 调用已删除

    # 2. 查找关键链接
    sszs_page_url = None
    
    # 尝试从导航栏精确找到 "硕士招生" 链接
    nav_div = main_soup.find('div', class_='nav') # pc nav
    if not nav_div:
        nav_div = main_soup.find('div', class_='m-nav') # mobile nav as fallback

    if nav_div:
        # Try to find "硕士招生" link specifically, usually 'zsgz/sszs.htm'
        # The structure is <li> -> <a><h3>招生工作</h3></a> -> <div class="sub"><a>硕士招生</a></div>
        h3_zsgz = nav_div.find('h3', string=lambda t: t and "招生工作" in t.strip())
        if h3_zsgz:
            parent_a_tag = h3_zsgz.find_parent('a')
            if parent_a_tag:
                li_parent = parent_a_tag.find_parent('li')
                if li_parent:
                    sub_div = li_parent.find('div', class_='sub')
                    if sub_div:
                        sszs_specific_link_tag = sub_div.find('a', href=True, string=lambda t: t and "硕士招生" in t.strip())
                        if sszs_specific_link_tag and sszs_specific_link_tag.get('href'):
                            href_val = sszs_specific_link_tag.get('href')
                            if not href_val.startswith(('http', 'javascript:', '#')) and '.htm' in href_val: # Basic check
                                sszs_page_url = urljoin(base_url, href_val)
                                print(f"    [{school_name}] (导航栏精确查找) 定位到硕士招生子菜单链接: {sszs_page_url}")
        
        # Fallback if the specific nested structure isn't found or if the main "招生工作" link itself is the target
        if not sszs_page_url:
            # Look for an 'a' tag that directly links to 'zsgz/sszs.htm' and contains "硕士招生" text or is under "招生工作"
            # The user-provided HTML structure suggests `href="zsgz/sszs.htm"` for "硕士招生"
            sszs_links = nav_div.find_all('a', href=re.compile(r'zsgz/sszs\.htm'))
            for link_tag in sszs_links:
                if "硕士招生" in link_tag.get_text(strip=True):
                    href_val = link_tag.get('href')
                    if not href_val.startswith(('http', 'javascript:', '#')):
                        sszs_page_url = urljoin(base_url, href_val)
                        print(f"    [{school_name}] (导航栏备用查找) 通过 href 'zsgz/sszs.htm' 和文本 '硕士招生' 定位到链接: {sszs_page_url}")
                        break
            if not sszs_page_url and sszs_links: # If any link matches href but not text, take the first one as a guess
                 href_val = sszs_links[0].get('href')
                 if not href_val.startswith(('http', 'javascript:', '#')):
                    sszs_page_url = urljoin(base_url, href_val)
                    print(f"    [{school_name}] (导航栏备用查找) 通过 href 'zsgz/sszs.htm' 定位到链接: {sszs_page_url}")


    catalog_keywords = ["硕士专业目录", "招生专业目录", "招生简章", "专业介绍", "硕士招生专业目录", "专业目录下载"]
    score_keywords = ["硕士复试分数线", "历年分数线", "复试分数", "录取分数线", "复试基本分数线", "初试合格分数线"]

    # Fetch and parse "硕士招生" page if URL found
    if sszs_page_url:
        print(f"    [{school_name}] 正在获取硕士招生页面: {sszs_page_url}")
        # Use Selenium for this page too, as it might have dynamic content or further navigation
        sszs_page_html = fetch_dynamic_page_with_selenium(sszs_page_url, school_name, page_type_suffix="MastersAdmissionsPage_Selenium")
        if sszs_page_html:
            sszs_soup = BeautifulSoup(sszs_page_html, 'html.parser')
            
            found_catalog_url_on_sszs = find_generic_link(sszs_soup, sszs_page_url, catalog_keywords)
            if found_catalog_url_on_sszs:
                school_update_data["major_catalog_url"] = found_catalog_url_on_sszs
                print(f"    [{school_name}] (硕士招生页查找) 找到专业目录链接: {found_catalog_url_on_sszs}")
            
            found_score_url_on_sszs = find_generic_link(sszs_soup, sszs_page_url, score_keywords)
            if found_score_url_on_sszs:
                school_update_data["score_line_url"] = found_score_url_on_sszs
                print(f"    [{school_name}] (硕士招生页查找) 找到分数线链接: {found_score_url_on_sszs}")
        else:
            print(f"    [{school_name}] 无法获取硕士招生页面内容: {sszs_page_url}")

    # Fallback: If major catalog URL not found yet, search on main page
    if not school_update_data["major_catalog_url"]:
        print(f"    [{school_name}] 专业目录链接未在硕士招生页找到，尝试在主页查找...")
        found_catalog_url_on_main = find_generic_link(main_soup, base_url, catalog_keywords)
        if found_catalog_url_on_main:
            school_update_data["major_catalog_url"] = found_catalog_url_on_main
            print(f"    [{school_name}] (主页通用查找) 找到疑似专业目录链接: {found_catalog_url_on_main}")
        else:
            print(f"    [{school_name}] (主页通用查找) 未找到专业目录链接。")
    
    # Fallback: If score line URL not found yet, search on main page's "通知公告" section and then general main page
    if not school_update_data["score_line_url"]:
        print(f"    [{school_name}] 分数线链接未在硕士招生页找到，尝试在主页通知公告区或主页查找...")
        tzgg_page_url = None
        s1_r_div = main_soup.find('div', class_='s1-r') # Right panel "通知公告"
        if s1_r_div:
            itit_div = s1_r_div.find('div', class_='itit')
            if itit_div:
                # Link with "Read More >>" typically points to the notice list page
                specific_tzgg_link_tag = itit_div.find('a', href=re.compile(r'(index/tzgg\.htm|list\.htm|news\.htm)')) # Common patterns
                if specific_tzgg_link_tag and specific_tzgg_link_tag.get('href'):
                    href_val = specific_tzgg_link_tag.get('href')
                    if not href_val.startswith(('http', 'javascript:', '#')):
                        tzgg_page_url = urljoin(base_url, href_val)
                        print(f"    [{school_name}] 定位到主页右侧通知公告页面链接: {tzgg_page_url}")
        
        if tzgg_page_url:
            print(f"    [{school_name}] 正在获取通知公告页面: {tzgg_page_url}")
            # Notices page might also be dynamic
            tzgg_page_html = fetch_dynamic_page_with_selenium(tzgg_page_url, school_name, page_type_suffix="NoticesPage_Selenium")
            if tzgg_page_html:
                tzgg_soup = BeautifulSoup(tzgg_page_html, 'html.parser')
                found_score_url_on_tzgg = find_generic_link(tzgg_soup, tzgg_page_url, score_keywords)
                if found_score_url_on_tzgg:
                    school_update_data["score_line_url"] = found_score_url_on_tzgg
                    print(f"    [{school_name}] (通知公告页查找) 找到分数线链接: {found_score_url_on_tzgg}")

        if not school_update_data["score_line_url"]: # If still not found, do a general search on main page
            found_score_url_on_main = find_generic_link(main_soup, base_url, score_keywords)
            if found_score_url_on_main:
                school_update_data["score_line_url"] = found_score_url_on_main
                print(f"    [{school_name}] (主页通用查找) 找到疑似分数线链接: {found_score_url_on_main}")
            else:
                print(f"    [{school_name}] (所有尝试后) 仍未找到分数线链接。")
    
    if not school_update_data["major_catalog_url"]:
         print(f"    [{school_name}] (所有尝试后) 仍未找到专业目录链接。")

    # TODO: 实现成都理工大学特定的专业目录页面解析逻辑
    # if school_update_data["major_catalog_url"]:
    #     # major_page_html = fetch_page(school_update_data["major_catalog_url"], ...) or fetch_dynamic_page_with_selenium
    #     # ... parse ... add to school_update_data["departments"]
    #     pass

    # TODO: 实现成都理工大学特定的分数线页面解析逻辑
    # if school_update_data["score_line_url"]:
    #     # score_page_html = fetch_page(school_update_data["score_line_url"], ...) or fetch_dynamic_page_with_selenium
    #     # ... parse ... and associate with majors in school_update_data["departments"]
    #     pass
            
    print(f"  [{school_name}] 成都理工大学链接抓取尝试完成。")
    
    # Departments are populated by specific parsing logic later.
    # If only placeholder message is needed when no departments found yet:
    if not school_update_data.get("departments"): 
         print(f"    [{school_name}] 院系和专业信息需在专业目录解析后填充。")

    if not school_update_data["major_catalog_url"] and not school_update_data["score_line_url"] and not school_update_data.get("departments"):
        print(f"    [{school_name}] 未找到关键链接（专业目录、分数线）且无部门信息，可能爬取失败或信息不在此处。返回 None。")
        return None
        
    return school_update_data 