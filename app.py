from flask import Flask, jsonify, render_template, session, redirect, url_for, request, flash, abort
from functools import wraps # 导入 wraps 用于装饰器
import json
import os
import datetime # 导入 datetime 模块
# 导入 Werkzeug 用于密码哈希 (比明文安全)
from werkzeug.security import generate_password_hash, check_password_hash
import re # 导入 re 用于解析分数线
from math import ceil # 用于分页计算
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, Optional, NumberRange

# --- 导入爬虫函数 ---
from utils.scraper import run_scraper 

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

# --- 新增：计算各学校收藏人数 ---
def get_favorites_count():
    """遍历所有用户文件，统计每个学校的收藏次数。"""
    favorites_count = {}
    if not os.path.exists(USERS_DIR):
        return favorites_count # 用户目录不存在，返回空字典

    for filename in os.listdir(USERS_DIR):
        if filename.endswith(".json"):
            username = filename[:-5] # 移除 .json 后缀
            user_data = get_user_data(username)
            if user_data and isinstance(user_data.get('favorites'), list):
                for school_id in user_data['favorites']:
                    favorites_count[school_id] = favorites_count.get(school_id, 0) + 1
    return favorites_count

# --- 表单类 ---
class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')

class RegistrationForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('密码', validators=[DataRequired(), Length(min=8, max=20)])
    confirm_password = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('注册')

class ProfileForm(FlaskForm):
    education_background = StringField('教育背景', validators=[Optional()])
    major_area = StringField('专业领域', validators=[Optional()])
    target_location = StringField('目标地区', validators=[Optional()])
    target_level = StringField('目标院校等级', validators=[Optional()])
    expected_score = IntegerField('预期分数', validators=[Optional()])
    submit = SubmitField('保存更改')

class AdminProfileForm(FlaskForm):
    current_password = PasswordField('当前密码', validators=[Optional()])
    new_password = PasswordField('新密码', validators=[Optional()])
    confirm_password = PasswordField('确认新密码', validators=[Optional(), EqualTo('new_password')])
    submit = SubmitField('修改密码')

class AnnouncementForm(FlaskForm):
    title = StringField('公告标题', validators=[DataRequired()])
    url = StringField('公告链接', validators=[Optional()])
    submit = SubmitField('发布公告')

class AdminUserForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    is_admin = BooleanField('是否为管理员')
    submit = SubmitField('保存更改')

# --- 新增：编辑学校信息表单 ---
class SchoolEditForm(FlaskForm):
    name = StringField('学校名称', validators=[DataRequired(), Length(max=100)])
    level = SelectField('院校等级', choices=[('985', '985'), ('211', '211'), ('双一流', '双一流'), ('一般', '一般'), ('', '未知')], validators=[Optional()])
    province = StringField('省份', validators=[Optional(), Length(max=50)])
    region = SelectField('区域', choices=[('A区', 'A区'), ('B区', 'B区'), ('未知地区', '未知地区')], validators=[Optional()])
    computer_rank = StringField('计算机等级', validators=[Optional(), Length(max=100)])
    intro = TextAreaField('简介', validators=[Optional()])
    submit = SubmitField('保存更改')

# --- 视图函数 / 路由 ---

@app.route('/')
def index():
    """渲染主页 (可视化大面板)。"""
    return render_template('index.html') # 传递登录状态等信息到模板

@app.route('/api/schools/list', methods=['GET'])
def get_schools_list():
    """返回用于滚动列表的学校基本信息。"""
    school_list_for_dashboard = []
    # 定义 A 区省份列表 (需要根据最新考研政策确认)
    a_region_provinces = [
        "北京", "天津", "河北", "山西", "辽宁", "吉林", "黑龙江", "上海", "江苏",
        "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东",
        "重庆", "四川", "陕西"
    ]
    for school in schools_data:
        # 修改：不再从单个专业获取，因为不准确。提供占位符。
        enrollment_24 = "见详情"
        subjects = "见详情"

        # 判断 A/B 区
        province = school.get("province")
        region_ab = "B区" if province and province not in a_region_provinces else "A区"

        school_list_for_dashboard.append({
            "name": school.get("name", "N/A"),
            "level": school.get("level", "N/A"),
            "computer_rank": school.get("computer_rank", "N/A"),
            "enrollment_24": enrollment_24,
            "subjects": subjects,
            "region_ab": region_ab # 返回 A/B 区
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
    # 获取查询参数和页码
    region = request.args.get('region')
    level = request.args.get('level')
    name = request.args.get('name')
    rank = request.args.get('rank')
    page = request.args.get('page', 1, type=int)
    per_page = 15 # 每页显示数量

    # 获取收藏计数
    favorites_counts = get_favorites_count()

    # 筛选学校数据
    filtered_schools = schools_data
    if region:
        filtered_schools = [s for s in filtered_schools if s.get('province') == region]
    if level:
        filtered_schools = [s for s in filtered_schools if s.get('level') == level]
    if name:
        # 使用模糊搜索 (大小写不敏感)
        filtered_schools = [s for s in filtered_schools if name.lower() in s.get('name', '').lower()]
    if rank:
        filtered_schools = [s for s in filtered_schools if s.get('computer_rank') == rank]

    # 添加收藏人数到筛选结果
    for school in filtered_schools:
        school_id = school.get('id', school.get('name')) # Use name as fallback ID
        school['favorites_count'] = favorites_counts.get(school_id, 0)

    # 按收藏人数排序 (默认降序)
    sort_by_favorites = request.args.get('sort') == 'favorites' # Example: ?sort=favorites
    if sort_by_favorites:
        filtered_schools.sort(key=lambda s: s.get('favorites_count', 0), reverse=True)

    # 分页处理
    total_schools = len(filtered_schools)
    total_pages = ceil(total_schools / per_page)
    start = (page - 1) * per_page
    end = start + per_page
    schools_paginated = filtered_schools[start:end]

    # 准备省份和等级列表用于下拉菜单
    provinces = sorted(list(set(s.get('province') for s in schools_data if s.get('province'))))
    levels = sorted(list(set(s.get('level') for s in schools_data if s.get('level'))), key=lambda x: ('985' not in x, '211' not in x, x)) # Custom sort
    ranks = sorted(list(set(s.get('computer_rank') for s in schools_data if s.get('computer_rank'))))

    return render_template(
        'school_list.html',
        schools=schools_paginated,
        provinces=provinces,
        levels=levels,
        ranks=ranks,
        current_page=page,
        total_pages=total_pages,
        # 传递查询参数以便分页链接和表单回显
        query_params={'region': region, 'level': level, 'name': name, 'rank': rank, 'sort': request.args.get('sort')}
    )

@app.route('/recommend', methods=['GET'])
def recommend():
    user_profile = {}
    if 'username' in session:
        user_data = get_user_data(session['username'])
        if user_data and 'profile' in user_data:
            user_profile = user_data['profile']

    # 从请求参数获取用户输入，如果未提供则尝试从 session profile 获取
    target_score_str = request.args.get('target_score')
    target_level = request.args.get('target_level') or user_profile.get('target_level')
    target_rank = request.args.get('target_rank') # 推荐时可能不直接用 rank?
    target_location = request.args.get('target_location') or user_profile.get('target_location')

    # 分数需要是数字
    target_score = None
    if target_score_str:
        try:
            target_score = int(target_score_str)
        except ValueError:
            flash('目标分数必须是有效的数字！', 'error')
            return redirect(url_for('index')) # 或留在推荐页面让用户重填
    elif user_profile.get('expected_score') is not None:
        target_score = user_profile.get('expected_score')

    # 如果缺少必要信息（至少分数和等级/地区之一），可以给提示或默认值
    if target_score is None or not (target_level or target_location):
        flash('请输入目标分数以及期望的院校等级或目标地区以获取推荐。', 'info')
        # 可以在这里决定是重定向还是显示空推荐页
        return render_template('recommendation.html', recommendations=[], user_profile=user_profile) # 传递 user_profile

    # 获取收藏计数
    favorites_counts = get_favorites_count()

    # 调用推荐算法
    recommended_schools = calculate_recommendations(
        target_score,
        target_level,
        target_rank, # 考虑是否需要这个参数
        target_location,
        favorites_counts # 传递收藏计数
    )

    return render_template('recommendation.html', recommendations=recommended_schools, user_profile=user_profile) # 传递 user_profile

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
        template_data['id'] = template_data.get('id') or template_data.get('name')

        # 尝试为四川院校提取近三年分数线数据用于图表
        sichuan_score_chart_data = None
        if template_data.get('province') == '四川省':
            # 假设分数线在第一个系的第一个专业里 (可能需要更复杂的逻辑)
            try:
                if template_data.get('departments') and template_data['departments'][0].get('majors'):
                     major_scores = template_data['departments'][0]['majors'][0].get('score_lines', {})
                     years = sorted([y for y in major_scores.keys() if y.isdigit() and int(y) >= 2022], reverse=True)[:3] # 取近三年
                     scores = []
                     valid_years = []
                     if len(years) >= 2: # 至少需要两年数据才能画线
                         for year in reversed(years): # 按年份升序
                            score_str = major_scores.get(year)
                            if score_str:
                                # 尝试提取总分
                                score_val = None
                                match = re.search(r'总分[:：]?\s*(\d+)', score_str)
                                if match:
                                    score_val = int(match.group(1))
                                else:
                                    numbers = re.findall(r'\d+', score_str)
                                    if numbers:
                                        score_val = int(numbers[-1]) # 取最后一个数字
                                if score_val is not None:
                                     scores.append(score_val)
                                     valid_years.append(year)
                         if len(scores) >= 2:
                             sichuan_score_chart_data = {'years': valid_years, 'scores': scores}
            except (AttributeError, IndexError, ValueError, TypeError) as e:
                 app.logger.warning(f"为四川院校 {template_data['name']} 提取分数线图表数据时出错: {e}")

        return render_template('school_detail.html', 
                               school=template_data, 
                               user_favorites=user_favorites,
                               sichuan_score_chart_data=sichuan_score_chart_data) # 传递图表数据
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
def calculate_recommendations(target_score, target_level, target_rank, target_location, favorites_counts):
    """根据用户偏好计算推荐院校列表。"""
    recommendations = []

    # 定义评分参数 (来自 README)
    level_scores = {"985": 60, "211": 40, "双一流": 20, "一般": 0}
    rank_scores = {"A+": 100, "A": 80, "A-": 70, "B+": 60, "B": 50, "B-": 40, "C+": 30, "C": 20, "C-": 10, "无": 0}
    weights = {"score": 0.4, "level": 0.2, "rank": 0.2, "location": 0.2}

    for school in schools_data:
        school_id = school.get('id', school.get('name'))
        score = 0

        # 1. 地区匹配分 (0.2)
        location_score = 0
        if target_location and school.get('province') == target_location:
            location_score = 100
        score += weights["location"] * location_score

        # 2. 院校等级分 (0.2)
        level_score = level_scores.get(school.get('level'), 0)
        score += weights["level"] * level_score

        # 3. 计算机等级分 (0.2)
        rank_score = rank_scores.get(school.get('computer_rank'), 0)
        score += weights["rank"] * rank_score

        # 4. 分数相似度分 (0.4)
        score_similarity = 0
        # --- 需要从 school 数据中找到历年分数线来计算相似度 --- 
        # 这是一个复杂点，需要确定用哪个专业的分数线，或者学校平均线？
        # 简化：暂时使用固定的相似度或基于等级给一个粗略值，待分数线数据完善后实现
        # 例如：如果等级匹配，给一些基础分
        if target_level and school.get('level') == target_level:
             score_similarity = 50 # 临时给个 50 分基础分
        # 更复杂的: 遍历专业，找平均分？
        avg_score_line = None
        relevant_scores = []
        if school.get('departments'):
            for dept in school['departments']:
                if dept.get('majors'):
                    for major in dept['majors']:
                        # 只考虑目标专业大类?
                        if major.get('major_code','').startswith('08') and major.get('score_lines'):
                             # 取最近一年的分数线?
                            latest_year = max(major['score_lines'].keys()) if major['score_lines'] else None
                            if latest_year and major['score_lines'][latest_year]:
                                try:
                                     relevant_scores.append(int(major['score_lines'][latest_year]))
                                except (ValueError, TypeError):
                                     pass
        if relevant_scores:
            avg_score_line = sum(relevant_scores) / len(relevant_scores)

        if avg_score_line and target_score:
             # 计算分数误差绝对值，假设最大误差为 100 分？
             error = abs(target_score - avg_score_line)
             # 归一化：误差越小，得分越高 (0-100)
             score_similarity = max(0, 100 - error) # 简单线性递减

        score += weights["score"] * score_similarity

        # 将计算出的总分和学校信息加入列表
        recommendations.append({
            "name": school.get("name"),
            "score": round(score, 2),
            "level": school.get("level"),
            "computer_rank": school.get("computer_rank"),
            "enrollment_24": "见详情", # 保持与列表页一致
            "favorites_count": favorites_counts.get(school_id, 0) # 添加收藏数
        })

    # 按总分降序排序
    recommendations.sort(key=lambda x: x['score'], reverse=True)

    # 返回 Top 20
    return recommendations[:20]

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

@app.route('/admin/schools')
@admin_required
def admin_schools():
    page = request.args.get('page', 1, type=int)
    per_page = 20 # 每页显示20条

    # 简单分页逻辑 (直接操作内存中的 schools_data)
    total_schools = len(schools_data)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    schools_on_page = schools_data[start_index:end_index]

    # 计算总页数
    total_pages = ceil(total_schools / per_page)

    # 简单的分页导航数据
    pagination = {
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'total_items': total_schools
    }

    return render_template('admin/schools.html',
                           schools=schools_on_page,
                           pagination=pagination)

@app.route('/admin/schools/trigger_crawler', methods=['POST'])
@admin_required
def trigger_crawler():
    # 这里是触发爬虫的地方
    admin_username = session.get('username')
    app.logger.info(f"管理员 '{admin_username}' 触发了爬虫任务...")
    try:
        # --- 直接调用爬虫函数 --- 
        # 注意：这会在请求期间运行，可能很慢！
        run_scraper() 
        flash('爬虫任务已尝试运行完成。请检查控制台输出或日志了解详情。', 'success')
        app.logger.info(f"爬虫任务由 '{admin_username}' 触发，已尝试运行。")
    except Exception as e:
        flash(f'运行爬虫时发生错误: {e}', 'error')
        app.logger.error(f"管理员 '{admin_username}' 触发爬虫时出错: {e}", exc_info=True) # 记录完整错误信息

    return redirect(url_for('admin_schools'))

@app.route('/admin/edit_school/<school_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_school(school_id):
    school_to_edit = next((s for s in schools_data if s.get('id') == school_id), None)
    if not school_to_edit:
        flash('未找到要编辑的学校', 'error')
        return redirect(url_for('admin_schools'))

    form = SchoolEditForm(obj=school_to_edit) # 使用 obj 填充表单初始值

    if form.validate_on_submit():
        # 更新 school_data 列表中的数据
        school_index = next((i for i, s in enumerate(schools_data) if s.get('id') == school_id), -1)
        if school_index != -1:
            schools_data[school_index]['name'] = form.name.data
            schools_data[school_index]['level'] = form.level.data
            schools_data[school_index]['province'] = form.province.data
            schools_data[school_index]['region'] = form.region.data # 可以考虑根据 province 重新计算 region
            schools_data[school_index]['computer_rank'] = form.computer_rank.data
            schools_data[school_index]['intro'] = form.intro.data
            schools_data[school_index]['id'] = form.name.data # 如果名称改变，ID 也需要同步

            if save_user_data(school_to_edit['username'], schools_data[school_index]):
                flash('学校信息更新成功!', 'success')
                # 更新后重定向到新的 school_id (如果名称变了)
                return redirect(url_for('admin_schools')) # 简化：直接回列表
            else:
                flash('保存学校信息时出错', 'error')
        else:
            flash('在数据列表中未找到学校进行更新', 'error')

    return render_template('admin/edit_school.html', form=form, school=school_to_edit)

def get_region(province):
    """根据省份判断 A/B 区。"""
    if not province or not isinstance(province, str):
        return "未知地区"

    # 直接处理特殊工作表名
    if province == "B区":
        return "B区"

    a_region_provinces = [
        "北京", "天津", "河北", "山西", "辽宁", "吉林", "黑龙江", "上海", "江苏",
        "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东",
        "重庆", "四川", "陕西"
    ]
    if province in a_region_provinces:
        return "A区"
    else:
        return "未知地区"

if __name__ == '__main__':
    app.run(debug=True, port=5001) 