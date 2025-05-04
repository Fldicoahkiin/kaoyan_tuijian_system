from flask import Flask, jsonify, render_template, session, redirect, url_for, request, flash
from functools import wraps # 导入 wraps 用于装饰器
import json
import os
import datetime # 导入 datetime 模块
# 导入 Werkzeug 用于密码哈希 (比明文安全)
from werkzeug.security import generate_password_hash, check_password_hash
import re # 导入 re 用于解析分数线

app = Flask(__name__)
# 设置一个密钥用于 session 加密，请在实际部署中替换为更安全的随机值
app.config['SECRET_KEY'] = 'dev_secret_key_please_change'

# 定义数据文件路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHOOLS_DATA_PATH = os.path.join(BASE_DIR, "data", "schools.json")
NATIONAL_LINES_PATH = os.path.join(BASE_DIR, "data", "national_lines.json")
ANNOUNCEMENTS_PATH = os.path.join(BASE_DIR, "data", "announcements.json")
USERS_DIR = os.path.join(BASE_DIR, "data", "users")

# --- 装饰器：要求管理员权限 ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('请先登录管理员账户。', 'warning')
            return redirect(url_for('login', next=request.url))
        username = session['username']
        user_data = get_user_data(username)
        if not user_data or not user_data.get('is_admin', False):
            flash('您没有权限访问此页面。', 'error')
            return redirect(url_for('index')) # 或者重定向到用户首页
        return f(*args, **kwargs)
    return decorated_function

# --- 上下文处理器: 注入全局变量到模板 ---
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.datetime.now().year}

# --- 数据加载函数 ---
def load_json_data(file_path, default_value=[]):
    """通用 JSON 数据加载函数。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误：未找到数据文件 {file_path}")
        return default_value
    except json.JSONDecodeError:
        print(f"错误：解析数据文件 {file_path} 时出错")
        return default_value

# 加载所有核心数据
schools_data = load_json_data(SCHOOLS_DATA_PATH)
national_lines_data = load_json_data(NATIONAL_LINES_PATH, default_value={}) # 默认空字典
announcements_data = load_json_data(ANNOUNCEMENTS_PATH)

# --- 辅助函数：用户数据读写 ---
def get_user_data(username):
    """读取指定用户的 JSON 数据文件。"""
    user_file = os.path.join(USERS_DIR, f"{username}.json")
    return load_json_data(user_file, default_value=None) # 用户不存在返回 None

def save_user_data(username, data):
    """保存用户数据到 JSON 文件。"""
    os.makedirs(USERS_DIR, exist_ok=True) # 确保目录存在
    user_file = os.path.join(USERS_DIR, f"{username}.json")
    try:
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except IOError as e:
        print(f"错误：无法写入用户文件 {user_file}: {e}")
        return False

# --- 视图函数 / 路由 ---

@app.route('/')
def index():
    """渲染主页 (可视化大面板)。"""
    return render_template('index.html') # 传递登录状态等信息到模板

@app.route('/api/schools/list', methods=['GET'])
def get_schools_list():
    """返回用于滚动列表的学校基本信息。"""
    school_list_for_dashboard = []
    for school in schools_data:
        # 尝试从第一个系的第一个专业获取大致的招生人数和科目
        enrollment_24 = 'N/A'
        subjects = 'N/A'
        if school.get('departments') and school['departments'][0].get('majors'):
            first_major = school['departments'][0]['majors'][0]
            enrollment_24 = first_major.get('enrollment_24', 'N/A')
            subjects = first_major.get('exam_subjects', 'N/A')
            # 简化显示，只取第一行
            if isinstance(subjects, str):
                 subjects = subjects.split('\n')[0]

        school_list_for_dashboard.append({
            "name": school.get("name", "N/A"),
            "level": school.get("level", "N/A"),
            "computer_rank": school.get("computer_rank", "N/A"),
            "enrollment_24": enrollment_24,
            "subjects": subjects,
            "region": school.get("region", "N/A")
        })
    return jsonify(school_list_for_dashboard)

# --- API 端点 (使用加载的数据) ---

@app.route('/api/national-lines/total', methods=['GET'])
def get_national_line_total():
    """返回近三年计算机考研总分国家线。"""
    return jsonify(national_lines_data.get("total", {}))

@app.route('/api/national-lines/politics', methods=['GET'])
def get_national_line_politics():
    """返回近三年政治国家线。"""
    return jsonify(national_lines_data.get("politics", {}))

@app.route('/api/national-lines/others', methods=['GET'])
def get_national_line_others():
    """返回近三年英语、数学国家线。"""
    return jsonify(national_lines_data.get("others", {}))

@app.route('/api/stats/exam-type-ratio', methods=['GET'])
def get_exam_type_ratio():
    """计算并返回自命题与408统考的院校比例。"""
    self_proposed_count = 0
    unified_408_count = 0
    unknown_count = 0

    for school in schools_data:
        exam_type = school.get("self_vs_408")
        if exam_type == "自命题":
            self_proposed_count += 1
        elif exam_type == "408统考":
            unified_408_count += 1
        else:
            if exam_type:
                 unknown_count +=1
            pass

    total_valid = self_proposed_count + unified_408_count
    if total_valid == 0:
        ratio_data = [
            {"value": 0, "name": "自命题"},
            {"value": 0, "name": "408统考"}
        ]
    else:
         ratio_data = [
            {"value": self_proposed_count, "name": "自命题"},
            {"value": unified_408_count, "name": "408统考"}
        ]

    return jsonify(ratio_data)

@app.route('/api/announcements', methods=['GET'])
def get_announcements():
    """返回公告信息。"""
    return jsonify(announcements_data)

# --- 用户认证路由 ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session:
        return redirect(url_for('index')) # 如果已登录，重定向到首页
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not password or not confirm_password:
            flash('所有字段都是必填项！', 'error')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('两次输入的密码不一致！', 'error')
            return redirect(url_for('register'))

        if get_user_data(username) is not None:
            flash('用户名已存在！', 'error')
            return redirect(url_for('register'))

        # 创建用户数据结构
        hashed_password = generate_password_hash(password)
        user_data = {
            "username": username,
            "password_hash": hashed_password,
            "profile": { # 用户的基本信息和偏好
                "education_background": "",
                "major_area": "",
                "target_location": "",
                "target_level": "", # 985, 211, etc.
                "expected_score": None
            },
            "favorites": [] # 收藏的学校 ID 列表
        }

        if save_user_data(username, user_data):
            flash('注册成功！请登录。', 'success')
            return redirect(url_for('login'))
        else:
            flash('注册过程中发生错误，请稍后再试。', 'error')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('用户名和密码不能为空！', 'error')
            return redirect(url_for('login'))

        user_data = get_user_data(username)

        if user_data is None:
            flash('用户名不存在！', 'error')
            return redirect(url_for('login'))

        if check_password_hash(user_data.get('password_hash', ''), password):
            session['username'] = username # 登录成功，记录 session
            flash('登录成功！', 'success')
            return redirect(url_for('index'))
        else:
            flash('密码错误！', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None) # 移除 session 中的用户名
    flash('您已成功登出。', 'info')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        flash('请先登录以访问个人资料页面。', 'warning')
        return redirect(url_for('login'))

    username = session['username']
    user_data = get_user_data(username)

    if user_data is None:
        # 这种情况理论上不应发生，如果 session 有但文件没了
        flash('无法加载用户数据，请重新登录。', 'error')
        session.pop('username', None)
        return redirect(url_for('login'))

    if request.method == 'POST':
        # 更新个人资料逻辑
        user_data['profile']['education_background'] = request.form.get('education_background', '')
        user_data['profile']['major_area'] = request.form.get('major_area', '')
        user_data['profile']['target_location'] = request.form.get('target_location', '')
        user_data['profile']['target_level'] = request.form.get('target_level', '')
        try:
            expected_score_str = request.form.get('expected_score')
            user_data['profile']['expected_score'] = int(expected_score_str) if expected_score_str else None
        except (ValueError, TypeError):
             user_data['profile']['expected_score'] = None # 如果转换失败则设为 None

        if save_user_data(username, user_data):
            flash('个人资料更新成功！', 'success')
        else:
            flash('个人资料更新失败。', 'error')
        # 即使失败也重定向回 profile 页，避免表单重复提交
        return redirect(url_for('profile'))

    # GET 请求，显示个人资料表单
    return render_template('profile.html', user_profile=user_data.get('profile', {}))

# --- 其他功能路由 --- 
# (添加占位路由以使 base.html 中的链接有效)

@app.route('/school-list')
def school_list():
    # 获取查询参数
    query_province = request.args.get('province', '').strip()
    query_level = request.args.get('level', '')
    query_name = request.args.get('name', '').strip()
    query_rank = request.args.get('computer_rank', '')

    # --- 计算收藏数 --- (效率较低)
    favorite_counts = {}
    try:
        if os.path.exists(USERS_DIR):
             for filename in os.listdir(USERS_DIR):
                if filename.endswith(".json"):
                    username = filename[:-5] # 获取用户名
                    user_data = get_user_data(username)
                    if user_data and 'favorites' in user_data:
                        for fav_id in user_data['favorites']:
                            favorite_counts[fav_id] = favorite_counts.get(fav_id, 0) + 1
    except Exception as e:
        print(f"计算收藏数时出错: {e}")

    # 筛选学校
    filtered_schools = []
    for school in schools_data:
        match = True
        # 省份/地区匹配 (模糊匹配省份)
        if query_province and query_province.lower() not in school.get('province', '').lower():
            match = False
        # 等级匹配
        if query_level and school.get('level') != query_level:
            match = False
        # 名称匹配 (模糊匹配)
        if query_name and query_name.lower() not in school.get('name', '').lower():
            match = False
        # 计算机等级匹配
        if query_rank and school.get('computer_rank') != query_rank:
            match = False

        if match:
            # 复制学校数据以避免修改原始数据
            school_copy = school.copy()
            # 添加收藏数字段 (使用 id 或 name 作为 key)
            school_id = school_copy.get('id') or school_copy.get('name')
            school_copy['favorites_count'] = favorite_counts.get(school_id, 0)
            filtered_schools.append(school_copy)

    # 按收藏数排序 (降序)
    filtered_schools.sort(key=lambda s: s.get('favorites_count', 0), reverse=True)

    return render_template('school_list.html', schools=filtered_schools)

@app.route('/recommend', methods=['GET', 'POST'])
def recommend():
    if 'username' not in session:
        flash('请先登录以使用智能推荐功能。', 'warning')
        return redirect(url_for('login'))

    username = session['username']
    user_data = get_user_data(username)
    if not user_data or 'profile' not in user_data:
        flash('无法加载用户偏好，请先完善个人资料。', 'error')
        return redirect(url_for('profile'))

    user_profile = user_data['profile']
    recommendations = None # 初始化推荐结果
    target_level_from_form = None
    target_rank_from_form = None

    if request.method == 'POST':
        # --- 获取推荐条件 (优先表单，否则用 profile) ---\n        try:\n            target_score_str = request.form.get(\'target_score\')\n            target_score = int(target_score_str) if target_score_str else user_profile.get(\'expected_score\')\n        except (ValueError, TypeError):\n            target_score = user_profile.get(\'expected_score\')\n

        target_level_from_form = request.form.get('target_level')
        target_level = target_level_from_form if target_level_from_form else user_profile.get('target_level')

        target_rank_from_form = request.form.get('target_rank') # 计算机等级条件

        target_location_str = request.form.get('target_location')
        target_location = target_location_str.strip() if target_location_str else user_profile.get('target_location')
        target_location = target_location.replace('省', '').replace('市', '') if target_location else None # 简单清理省市后缀

        if target_score is None or not target_level or not target_location:
            flash('请确保目标分数、期望院校等级和目标地区都已设置（在个人中心或当前表单）。', 'warning')
        else:
            # --- 执行推荐计算 ---
            ranked_schools = calculate_recommendations(
                target_score, target_level, target_rank_from_form, target_location
            )
            recommendations = ranked_schools[:20] # 取前20名

    # 渲染页面，传递用户资料和推荐结果 (修正缩进，移出 POST 判断)
    return render_template('recommendation.html',
                           user_profile=user_profile,
                           recommendations=recommendations,
                           target_level=target_level_from_form, # 用于回显表单选项
                           target_rank=target_rank_from_form)

@app.route('/school/<path:school_id>') # 使用 path 转换器允许 school_id 包含斜杠 (虽然可能不需要)
def school_detail(school_id):
    # 通过 id 或 name 查找学校数据
    school = next((s for s in schools_data if s.get('id') == school_id or s.get('name') == school_id), None)

    if school:
        user_favorites = []
        if 'username' in session:
            user_data = get_user_data(session['username'])
            if user_data and 'favorites' in user_data:
                user_favorites = user_data['favorites']

        # 准备要传递给模板的数据
        template_data = school.copy()
        # 确保 school_id 是唯一的，优先使用 id
        template_data['id'] = template_data.get('id') or template_data.get('name')

        return render_template('school_detail.html', school=template_data, user_favorites=user_favorites)
    else:
        flash('未找到指定的学校。', 'error')
        return redirect(url_for('school_list')) # 重定向到院校库

# --- 新增：收藏 API ---
@app.route('/api/school/favorite/<path:school_id>', methods=['POST'])
def toggle_favorite(school_id):
    if 'username' not in session:
        return jsonify({"success": False, "message": "需要登录"}), 401 # Unauthorized

    username = session['username']
    user_data = get_user_data(username)

    if user_data is None:
        return jsonify({"success": False, "message": "无法加载用户数据"}), 500

    # 检查请求体，期望 { "favorite": true/false }
    req_data = request.get_json()
    if req_data is None or 'favorite' not in req_data:
         return jsonify({"success": False, "message": "无效的请求"}), 400

    should_favorite = req_data['favorite']

    # 初始化收藏列表（如果不存在）
    if 'favorites' not in user_data:
        user_data['favorites'] = []

    # 执行操作
    action_performed = False
    if should_favorite:
        # 添加收藏
        if school_id not in user_data['favorites']:
            user_data['favorites'].append(school_id)
            action_performed = True
    else:
        # 取消收藏
        if school_id in user_data['favorites']:
            user_data['favorites'].remove(school_id)
            action_performed = True

    if action_performed:
        if save_user_data(username, user_data):
            return jsonify({"success": True, "is_favorited": should_favorite, "message": "操作成功"})
        else:
            return jsonify({"success": False, "message": "保存用户数据失败"}), 500
    else:
        # 如果状态未改变（例如，重复添加已存在的收藏）
        return jsonify({"success": True, "is_favorited": school_id in user_data['favorites'], "message": "状态未改变"})

# --- 推荐算法核心逻辑 ---
def calculate_recommendations(target_score, target_level, target_rank, target_location):
    """根据用户目标计算学校推荐分数并排序。"""
    scored_schools = []

    # 等级分数字典
    level_scores = {"985": 60, "211": 40, "双一流": 20, "一般": 0}
    # 计算机等级分数字典
    rank_scores = {
        "A+": 100, "A": 80, "A-": 70,
        "B+": 60, "B": 50, "B-": 40,
        "C+": 30, "C": 20, "C-": 10,
        "无": 0
    }

    for school in schools_data:
        # 1. 计算分数相似度 (0.4 权重)
        school_score_proxy = 0 # 默认0分
        try:
            # 尝试从第一个专业的 2024 分数线提取总分
            if school.get('departments') and school['departments'][0].get('majors'):
                score_line_str = school['departments'][0]['majors'][0].get('score_lines', {}).get('2024', '')
                if score_line_str:
                    # 尝试多种正则匹配总分
                    match = re.search(r'总分[:：]?\s*(\d+)', score_line_str)
                    if match:
                        school_score_proxy = int(match.group(1))
                    else:
                        # 如果没有明确 总分 字样，尝试取最后一个数字作为总分（可能不准）
                         numbers = re.findall(r'\d+', score_line_str)
                         if numbers:
                             school_score_proxy = int(numbers[-1])

            if school_score_proxy > 0:
                score_diff = abs(target_score - school_score_proxy)
                score_similarity = max(0.0, 1.0 - score_diff / 100.0) # 差100分以上为0
            else:
                score_similarity = 0 # 没有分数线信息，相似度为0
        except Exception as e:
            # print(f"解析分数线出错 for {school.get('name')}: {e}")
            score_similarity = 0

        # 2. 计算院校等级分 (0.2 权重)
        school_level = school.get('level', '一般')
        level_score = level_scores.get(school_level, 0)

        # 3. 计算计算机等级分 (0.2 权重)
        school_rank = school.get('computer_rank', '无')
        rank_score_val = rank_scores.get(school_rank, 0)
        # 如果用户指定了目标等级，进行匹配
        if target_rank and school_rank != target_rank:
            rank_score_val = 0 # 如果指定了目标等级但不符，则此项不得分 (修正缩进)

        # 4. 计算地区匹配分 (0.2 权重)
        school_province = school.get('province', '').replace('省', '').replace('市', '')
        region_match_score = 100 if target_location and target_location == school_province else 0

        # 计算总推荐分
        total_score = (score_similarity * 0.4 * 100 + # 分数相似度转换为百分制再加权
                       level_score * 0.2 +
                       rank_score_val * 0.2 +
                       region_match_score * 0.2)

        # 存储学校及其分数
        school_copy = school.copy()
        school_copy['recommend_score'] = total_score
        scored_schools.append(school_copy)

    # 按推荐分数降序排序
    scored_schools.sort(key=lambda s: s['recommend_score'], reverse=True)
    return scored_schools

# --- 管理后台路由 ---
@app.route('/admin/')
@admin_required
def admin_dashboard():
    # 统计用户数量
    user_count = 0
    if os.path.exists(USERS_DIR):
        user_count = len([name for name in os.listdir(USERS_DIR) if name.endswith(".json")])
    # 统计公告数量
    announcement_count = len(load_json_data(ANNOUNCEMENTS_PATH, default_value=[]))

    return render_template('admin/dashboard.html',
                           user_count=user_count,
                           announcement_count=announcement_count)

@app.route('/admin/users')
@admin_required
def admin_users():
    users_list = [] # 改为列表存储用户字典
    if os.path.exists(USERS_DIR):
        for filename in os.listdir(USERS_DIR):
            if filename.endswith(".json"):
                username = filename[:-5]
                user_data = get_user_data(username)
                if user_data: # 确保成功读取数据
                    users_list.append({
                        'username': username,
                        'is_admin': user_data.get('is_admin', False)
                    })
    # 按用户名排序
    users_list.sort(key=lambda u: u['username'])
    return render_template('admin/users.html', users=users_list)

@app.route('/admin/user/create', methods=['POST'])
@admin_required
def admin_create_user():
    admin_username = session.get('username')
    username = request.form.get('username')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin') == 'true' # Checkbox value is 'true' or None

    if not username or not password:
        flash('新用户名和密码不能为空！', 'error')
        return redirect(url_for('admin_users'))

    if get_user_data(username) is not None:
        flash(f'用户名 "{username}" 已存在！', 'error')
        app.logger.warning(f"管理员 '{admin_username}' 尝试创建已存在的用户 '{username}'")
        return redirect(url_for('admin_users'))

    hashed_password = generate_password_hash(password)
    new_user_data = {
        "username": username,
        "password_hash": hashed_password,
        "is_admin": is_admin,
        "profile": { # 添加默认空的 profile
            "education_background": "",
            "major_area": "",
            "target_location": "",
            "target_level": "",
            "expected_score": None
        },
        "favorites": []
    }

    if save_user_data(username, new_user_data):
        flash(f'用户 "{username}" 创建成功！{' (管理员)' if is_admin else ''}', 'success')
        app.logger.info(f"管理员 '{admin_username}' 创建了新用户 '{username}' (管理员: {is_admin})")
    else:
        flash(f'创建用户 "{username}" 时出错。', 'error')
        app.logger.error(f"管理员 '{admin_username}' 创建用户 '{username}' 时保存文件失败。")

    return redirect(url_for('admin_users'))

@app.route('/admin/user/delete/<username>', methods=['POST'])
@admin_required
def delete_user(username):
    # 防止删除自己？可以加逻辑，但目前简单处理
    # if username == session['username']:
    #     flash('不能删除当前登录的管理员账户！', 'error')
    #     return redirect(url_for('admin_users'))

    user_file = os.path.join(USERS_DIR, f"{username}.json")
    if os.path.exists(user_file):
        try:
            os.remove(user_file)
            flash(f'用户 "{username}" 已成功删除。', 'success')
        except OSError as e:
            flash(f'删除用户 "{username}" 时出错: {e}', 'error')
    else:
        flash(f'未找到用户 "{username}"。', 'warning')
    return redirect(url_for('admin_users'))

@app.route('/admin/announcements', methods=['GET', 'POST'])
@admin_required
def admin_announcements():
    if request.method == 'POST':
        # 处理新增公告
        title = request.form.get('title')
        url = request.form.get('url', '#') # URL 可选，默认为 #

        if not title:
            flash('公告标题不能为空！', 'error')
        else:
            new_announcement = {"title": title, "url": url}
            current_announcements = load_json_data(ANNOUNCEMENTS_PATH, default_value=[])
            current_announcements.append(new_announcement)
            # 保存回文件
            try:
                with open(ANNOUNCEMENTS_PATH, 'w', encoding='utf-8') as f:
                    json.dump(current_announcements, f, ensure_ascii=False, indent=2)
                flash('新公告已添加。', 'success')
            except IOError as e:
                flash(f'保存公告时出错: {e}', 'error')
        # 重定向回 GET 请求，避免刷新重复提交
        return redirect(url_for('admin_announcements'))

    # GET 请求，显示列表和表单
    announcements = load_json_data(ANNOUNCEMENTS_PATH, default_value=[])
    return render_template('admin/announcements.html', announcements=announcements)

@app.route('/admin/announcement/delete/<int:index>', methods=['POST'])
@admin_required
def delete_announcement(index):
    current_announcements = load_json_data(ANNOUNCEMENTS_PATH, default_value=[])
    if 0 <= index < len(current_announcements):
        try:
            deleted_title = current_announcements.pop(index)['title']
            with open(ANNOUNCEMENTS_PATH, 'w', encoding='utf-8') as f:
                json.dump(current_announcements, f, ensure_ascii=False, indent=2)
            flash(f'公告 "{deleted_title}" 已删除。', 'success')
        except IndexError:
             flash('无效的公告索引。', 'error')
        except IOError as e:
            flash(f'删除公告时出错: {e}', 'error')
            # 可选：如果写入失败，尝试恢复数据？
    else:
        flash('无效的公告索引。', 'error')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/profile', methods=['GET', 'POST'])
@admin_required
def admin_profile():
    username = session['username']
    if request.method == 'POST':
        current_password = request.form.get('current_password') # 可选，增加安全性
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or not confirm_password:
            flash('新密码和确认密码不能为空！', 'error')
            return redirect(url_for('admin_profile'))

        if new_password != confirm_password:
            flash('两次输入的新密码不一致！', 'error')
            return redirect(url_for('admin_profile'))

        user_data = get_user_data(username)
        if not user_data:
             flash('无法加载当前用户信息。', 'error')
             return redirect(url_for('admin_dashboard'))

        # (可选) 验证当前密码
        if current_password and not check_password_hash(user_data.get('password_hash', ''), current_password):
            flash('当前密码错误！', 'error')
            return redirect(url_for('admin_profile'))

        # 更新密码哈希
        user_data['password_hash'] = generate_password_hash(new_password)
        if save_user_data(username, user_data):
            flash('密码修改成功！', 'success')
            app.logger.info(f"管理员 '{username}' 修改了自己的密码。")
            # 可以选择是否让用户重新登录
        else:
            flash('修改密码时发生错误。', 'error')
            app.logger.error(f"管理员 '{username}' 修改密码时保存文件失败。")
        return redirect(url_for('admin_profile'))

    return render_template('admin/admin_profile.html')

@app.route('/admin/user/detail/<username>')
@admin_required
def admin_user_detail(username):
    user_data = get_user_data(username)
    if user_data is None:
        flash(f'未找到用户 "{username}"。', 'warning')
        return redirect(url_for('admin_users'))

    # 为了安全，不直接传递 password_hash 到模板
    display_data = user_data.copy()
    display_data.pop('password_hash', None)

    return render_template('admin/user_detail.html', user=display_data)

@app.route('/admin/user/toggle_admin/<username>', methods=['POST'])
@admin_required
def toggle_admin_status(username):
    admin_username = session.get('username')
    if username == admin_username:
        flash('不能修改自己的管理员状态！', 'error')
        return redirect(url_for('admin_users'))

    user_data = get_user_data(username)
    if user_data is None:
        flash(f'未找到用户 "{username}"。', 'warning')
        return redirect(url_for('admin_users'))

    # 切换 is_admin 状态
    current_status = user_data.get('is_admin', False)
    user_data['is_admin'] = not current_status

    if save_user_data(username, user_data):
        new_status = "管理员" if not current_status else "普通用户"
        flash(f'已将用户 "{username}" 设置为 {new_status}。', 'success')
        app.logger.info(f"管理员 '{admin_username}' 将用户 '{username}' 设置为 {new_status}。")
    else:
        flash(f'修改用户 "{username}" 管理员状态时出错。', 'error')
        app.logger.error(f"管理员 '{admin_username}' 修改用户 '{username}' 管理员状态时保存失败。")

    # 可以重定向回用户列表或详情页
    return redirect(url_for('admin_users'))

# ... (其他管理路由)

if __name__ == '__main__':
    app.run(debug=True) 