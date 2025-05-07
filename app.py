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
import logging # 导入 logging
from flask_wtf.csrf import CSRFProtect # 导入 CSRFProtect
# import fcntl # 移除 fcntl
import portalocker # 导入 portalocker
import fcntl # 添加导入
import time # 添加导入
from logging.handlers import RotatingFileHandler
import pandas as pd # 导入 pandas 用于 replace_nan_with_none 函数

# --- 导入爬虫函数 ---
from utils.scraper import run_scraper 

app = Flask(__name__)
# 设置一个密钥用于 session 加密，请在实际部署中替换为更安全的随机值
app.config['SECRET_KEY'] = 'dev_secret_key_please_change'
csrf = CSRFProtect(app) # 初始化 CSRFProtect

# 定义数据文件路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHOOLS_DATA_PATH = os.path.join(BASE_DIR, "data", "schools.json")
NATIONAL_LINES_PATH = os.path.join(BASE_DIR, "data", "national_lines.json")
ANNOUNCEMENTS_PATH = os.path.join(BASE_DIR, "data", "announcements.json")
EXAM_TYPE_RATIOS_PATH = os.path.join(BASE_DIR, "data", "exam_type_ratios.json")
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
    """通用 JSON 数据加载函数，带共享文件锁。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # 获取共享锁
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN) # 确保在任何情况下都释放锁
            return data
    except FileNotFoundError:
        # 使用 app.logger 记录错误
        app.logger.error(f"数据文件未找到: {file_path}")
        return default_value
    except json.JSONDecodeError:
        app.logger.error(f"解析数据文件时出错: {file_path}")
        return default_value
    except IOError as e_io:
        app.logger.error(f"读取或锁定文件 {file_path} 时发生IO错误: {e_io}", exc_info=True)
        return default_value # 或者根据情况决定是否抛出异常
    except Exception as e:
        app.logger.error(f"加载 JSON 数据 {file_path} 时发生意外错误: {e}", exc_info=True)
        return default_value

# --- 数据保存函数 (新增) ---
def save_schools_data(data):
    """将学校数据（列表）保存到 JSON 文件，带文件锁。"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(SCHOOLS_DATA_PATH), exist_ok=True)
        
        # --- 文件锁开始 ---
        with open(SCHOOLS_DATA_PATH, 'w', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX) # 获取排他锁
            try:
                # 确保数据是干净的（没有 NaN 等 JSON 不支持的类型）
                cleaned_data = replace_nan_with_none(data) # 假设 replace_nan_with_none 已定义
                json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno()) # 确保写入磁盘
                app.logger.info(f"学校数据已成功写入 {SCHOOLS_DATA_PATH}")
                # fcntl.flock(f.fileno(), fcntl.LOCK_UN) # with 语句会自动解锁
                return True
            except Exception as e_write:
                app.logger.error(f"在持有锁的情况下写入学校数据时出错: {e_write}", exc_info=True)
                # 锁会自动释放
                return False
        # --- 文件锁结束 ---
        
    except IOError as e_io:
        app.logger.error(f"打开或锁定学校数据文件 {SCHOOLS_DATA_PATH} 时发生IO错误: {e_io}", exc_info=True)
        return False
    except Exception as e:
        app.logger.error(f"保存学校数据到 {SCHOOLS_DATA_PATH} 时发生意外错误: {e}", exc_info=True)
        return False

# --- 需要确保 replace_nan_with_none 函数存在于 app.py 中 --- 
# 如果它只在 data_processor.py 中，需要移过来或导入
def replace_nan_with_none(obj):
    if isinstance(obj, list):
        return [replace_nan_with_none(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: replace_nan_with_none(value) for key, value in obj.items()}
    elif isinstance(obj, float) and pd.isna(obj): # 需要导入 pandas as pd
        # 如果不想依赖 pandas，可以检查 math.isnan(obj)
        import math 
        if math.isnan(obj):
           return None
    # 可以添加对其他 NaN 类型（如 numpy.nan）的处理
    return obj

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
        app.logger.error(f"错误：无法写入用户文件 {user_file}: {e}")
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

class SchoolEditForm(FlaskForm):
    name = StringField('学校名称', validators=[DataRequired(), Length(max=100)])
    level = SelectField('院校等级', choices=[('', '未知'), ('985', '985'), ('211', '211'), ('双一流', '双一流'), ('一般', '一般')], validators=[Optional()], default='')
    province = StringField('省份', validators=[Optional(), Length(max=50)])
    computer_rank = StringField('计算机等级', validators=[Optional(), Length(max=100)])
    intro = TextAreaField('简介', validators=[Optional()])
    submit = SubmitField('保存更改')

# --- 视图函数 / 路由 ---

@app.route('/')
def index():
    """渲染主页 (可视化大面板)。"""
    return render_template('index.html') # 传递登录状态等信息到模板

@app.route('/api/schools/list')
def api_schools_list():
    """API: 返回用于首页滚动列表的简化学校信息"""
    schools = load_json_data(SCHOOLS_DATA_PATH)
    simplified_schools = []
    for school in schools:
        simplified_schools.append({
            'id': school.get('id'),
            'name': school.get('name'),
            'level': school.get('level'),
            'province': school.get('province', '未知省份'),
            'computer_rank': school.get('computer_rank', '暂无评级'),
            'enrollment_24': "见详情",
            'exam_subjects': "见详情"
        })
    return jsonify(simplified_schools)

# --- API 端点 (使用加载的数据) ---

@app.route('/api/national-lines/total')
def get_national_line_total():
    lines_data = load_json_data(NATIONAL_LINES_PATH)
    if not lines_data or 'total' not in lines_data or 'years' not in lines_data['total'] or 'scores' not in lines_data['total']:
        return jsonify({"error": "Total data not found or incomplete"}), 404
    
    total_data = lines_data['total']
    years = total_data['years']
    scores = {
        "A类考生总分": total_data['scores'].get("A区", [None] * len(years)),
        "B类考生总分": total_data['scores'].get("B区", [None] * len(years))
    }
    echarts_data = {
        "years": years,
        "legend": list(scores.keys()),
        "series": [
            {
                "name": name,
                "data": data,
                "type": "line",
                "smooth": True
            }
            for name, data in scores.items()
        ],
        "yAxis": {
            "min": "dataMin"
        }
    }
    return jsonify(echarts_data)

@app.route('/api/national-lines/politics')
def get_national_line_politics():
    lines_data = load_json_data(NATIONAL_LINES_PATH)
    if not lines_data or 'politics' not in lines_data or 'years' not in lines_data['politics'] or 'scores' not in lines_data['politics']:
        return jsonify({"error": "Politics data not found or incomplete"}), 404

    politics_data = lines_data['politics']
    years = politics_data['years']
    # The legend in HTML was "A类政治/英语"
    scores = {
        "A类政治/英语": politics_data['scores'].get("A区", [None] * len(years)),
        "B类政治/英语": politics_data['scores'].get("B区", [None] * len(years))
    }
    echarts_data = {
        "years": years,
        "legend": list(scores.keys()),
        "series": [
            {
                "name": name,
                "data": data,
                "type": "bar", 
                "barMaxWidth": 30
            }
            for name, data in scores.items()
        ],
         "yAxis": {
             "min": "dataMin"
         }
    }
    return jsonify(echarts_data)

@app.route('/api/national-lines/others')
def get_national_line_others():
    lines_data = load_json_data(NATIONAL_LINES_PATH)
    if not lines_data or 'others' not in lines_data or 'years' not in lines_data['others'] or 'scores' not in lines_data['others']:
        return jsonify({"error": "Others data not found or incomplete"}), 404

    others_data = lines_data['others']
    years = others_data['years']
    # The legend in HTML was "A类数学/专业课". We'll try to pick relevant A/B区 data.
    # This part is tricky given the current JSON structure for 'others'.
    # Let's assume we want "数学一" for A区 and B区 as a proxy for "数学/专业课".
    # A more robust solution would be to restructure national_lines.json for this specific view.
    
    a_scores = others_data['scores'].get("数学一 (A区)", [])
    b_scores = others_data['scores'].get("数学一 (B区)", [])

    # Ensure data length matches years length, padding with None if necessary
    a_scores_padded = (a_scores + [None] * len(years))[:len(years)]
    b_scores_padded = (b_scores + [None] * len(years))[:len(years)]

    scores = {
        "A类数学/专业课": a_scores_padded,
        "B类数学/专业课": b_scores_padded
    }
    echarts_data = {
        "years": years,
        "legend": list(scores.keys()),
        "series": [
            {
                "name": name,
                "data": data,
                "type": "line",
                "smooth": True
            }
            for name, data in scores.items() if any(d is not None for d in data) # Only add series if it has some data
        ],
         "yAxis": {
             "min": "dataMin"
         }
    }
    return jsonify(echarts_data)

@app.route('/api/stats/exam-type-ratio', methods=['GET'])
def get_exam_type_ratio():
    """API: 返回存储的考试类型比例数据。"""
    # 从新的JSON文件加载数据
    ratio_data = load_json_data(EXAM_TYPE_RATIOS_PATH, default_value=[
        {"value": 0, "name": "自命题"},
        {"value": 0, "name": "408统考"}
    ])
    return jsonify(ratio_data)

@app.route('/api/announcements')
def get_announcements():
    """API 端点，用于获取公告信息"""
    announcements_file_path = os.path.join(app.root_path, 'data', 'announcements.json')
    try:
        # 确保数据目录存在
        data_dir = os.path.dirname(announcements_file_path)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            app.logger.info(f"创建数据目录: {data_dir}")

        # 如果文件不存在，创建一个空的JSON数组文件
        if not os.path.exists(announcements_file_path):
            with open(announcements_file_path, 'w', encoding='utf-8') as f_create:
                json.dump([], f_create)
            app.logger.info(f"创建空的公告文件: {announcements_file_path}")

        with open(announcements_file_path, 'r', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH) # 获取共享锁
            try:
                content = f.read()
                if not content: # 文件为空
                    app.logger.warning(f"公告文件 {announcements_file_path} 为空，返回空列表。")
                    announcements = []
                else:
                    announcements = json.loads(content)
            except json.JSONDecodeError as e_decode:
                app.logger.error(f"在 get_announcements 中解析公告文件 {announcements_file_path} 时出错: {e_decode}")
                # 对于API端点，返回错误JSON可能比抛出500更好，或者返回空数据
                return jsonify([]) # 或 jsonify({'error': 'Failed to parse announcements data'}), 500
            # fcntl.flock(f.fileno(), fcntl.LOCK_UN) # 锁会在文件关闭时自动释放
            return jsonify(announcements)
        
    except IOError as e_io:
        app.logger.error(f"读取或锁定公告文件时发生IO错误 (get_announcements): {e_io}", exc_info=True)
        return jsonify([]) # 出错时返回空列表
    except Exception as e:
        app.logger.error(f"获取公告时发生意外错误: {e}", exc_info=True)
        return jsonify([]) # 出错时返回空列表

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
    search_query = request.args.get('q', '')
    province_filter = request.args.get('province', '')
    level_filter = request.args.get('level', '')
    rank_filter = request.args.get('rank', '') # 新增：计算机等级筛选
    sort_by = request.args.get('sort', 'default') # 新增：排序参数
    page = request.args.get('page', 1, type=int)
    per_page = 20 # 每页显示数量

    # --- 加载最新数据 ---
    all_schools = load_json_data(SCHOOLS_DATA_PATH)
    if not all_schools:
        flash('无法加载学校数据。', 'warning')
        all_schools = []
    # --- 加载结束 ---

    # 过滤学校
    filtered_schools = all_schools
    if search_query:
        filtered_schools = [
            s for s in filtered_schools
            if search_query.lower() in s.get('name', '').lower()
        ]
    if province_filter:
        filtered_schools = [s for s in filtered_schools if s.get('province') == province_filter]
    if level_filter:
        filtered_schools = [s for s in filtered_schools if s.get('level') == level_filter]
    if rank_filter:
        # 对 computer_rank 进行过滤，可能需要更复杂的逻辑来处理 A+/A/A- 等
        filtered_schools = [s for s in filtered_schools if s.get('computer_rank') and s.get('computer_rank').startswith(rank_filter)]
        
    # --- 排序逻辑 ---
    if sort_by == 'favorites':
        # 获取收藏数 (这可能需要优化，如果学校数量很大)
        favorites_counts = get_favorites_count()
        # print(f"DEBUG: Favorites Counts: {favorites_counts}") # 调试
        # 添加 favorites_count 字段到学校数据，如果不存在则为 0
        for school in filtered_schools:
            school['temp_favorites_count'] = favorites_counts.get(school['id'], 0)
        # 按收藏数降序排序
        filtered_schools.sort(key=lambda x: x.get('temp_favorites_count', 0), reverse=True)
        # print(f"DEBUG: Sorted by favorites: {[s['name'] for s in filtered_schools[:5]]}") # 调试
    #elif sort_by == 'rank':
        # 排序逻辑：根据 computer_rank (可能需要自定义排序函数处理 A+, A, A-)
        # ... 实现 rank 排序 ...
    # 默认排序 (可以按名称)
    elif sort_by == 'default' or True:
        filtered_schools.sort(key=lambda x: x.get('name', ''))

    # 分页处理
    total_schools = len(filtered_schools)
    total_pages = ceil(total_schools / per_page)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    paginated_schools = filtered_schools[start_index:end_index]

    # 获取所有省份和等级用于筛选下拉菜单
    all_provinces = sorted(list(set(s.get('province', '未知省份') for s in all_schools if s.get('province'))))
    all_levels = sorted(list(set(s.get('level', '一般') for s in all_schools)), key=lambda x: (x != '985', x != '211', x != '双一流', x)) # 自定义排序
    all_ranks = sorted(list(set(s.get('computer_rank', '') for s in all_schools if s.get('computer_rank')))) # 收集所有计算机等级

    return render_template('school_list.html',
                           schools=paginated_schools,
                           page=page,
                           total_pages=total_pages,
                           total_schools=total_schools,
                           all_provinces=all_provinces,
                           all_levels=all_levels,
                           all_ranks=all_ranks, # 传递等级列表
                           current_province=province_filter,
                           current_level=level_filter,
                           current_rank=rank_filter, # 传递当前等级
                           current_sort=sort_by,
                           search_query=search_query)

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
    # --- 加载最新数据 ---
    schools_data_list = load_json_data(SCHOOLS_DATA_PATH)
    if not schools_data_list:
        abort(404, description="无法加载学校数据") # 或显示错误页面
    # --- 加载结束 ---
    
    school = next((s for s in schools_data_list if s.get('id') == school_id), None)

    if school is None:
        # 如果按ID找不到，尝试按名称匹配 (不精确，可能需要改进)
        school = next((s for s in schools_data_list if s.get('name') == school_id), None)

    if school is None:
        app.logger.warning(f"尝试访问不存在的学校: {school_id}")
        abort(404, description=f"未找到ID或名称为 {school_id} 的学校")
        
    is_favorite = False
    if 'username' in session:
        user_data = get_user_data(session['username'])
        if user_data and school.get('id') in user_data.get('favorites', []):
            is_favorite = True

    return render_template('school_detail.html', school=school, is_favorite=is_favorite)

# --- 新增：收藏 API ---
@app.route('/api/school/favorite/<path:school_id>', methods=['POST'])
def toggle_favorite(school_id):
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': '请先登录'}), 401

    username = session['username']
    user_data = get_user_data(username)
    if not user_data:
        return jsonify({'status': 'error', 'message': '无法加载用户信息'}), 500

    # --- 加载最新数据 ---
    schools_data_list = load_json_data(SCHOOLS_DATA_PATH)
    if not schools_data_list:
        return jsonify({'status': 'error', 'message': '无法加载学校数据'}), 500
    # --- 加载结束 ---
    
    # 验证 school_id 是否有效
    school_exists = any(s.get('id') == school_id for s in schools_data_list)
    if not school_exists:
        return jsonify({'status': 'error', 'message': '无效的学校ID'}), 404

    favorites = user_data.get('favorites', [])
    action = 'added' # 默认动作
    if school_id in favorites:
        favorites.remove(school_id)
        action = 'removed'
    else:
        favorites.append(school_id)
        action = 'added'
        
    user_data['favorites'] = favorites
    if save_user_data(username, user_data):
        return jsonify({'status': 'success', 'action': action, 'school_id': school_id})
    else:
        return jsonify({'status': 'error', 'message': '保存收藏夹时出错'}), 500

# --- 推荐算法核心逻辑 ---
def calculate_recommendations(target_score, target_level, target_rank, target_location, favorites_counts):
    """根据用户偏好计算推荐结果"""
    # --- 加载最新数据 ---
    schools = load_json_data(SCHOOLS_DATA_PATH)
    if not schools:
        app.logger.error("计算推荐时无法加载学校数据！")
        return [], [], []
    # --- 加载结束 ---

    target_score = int(target_score) if target_score else 0
    # ... (其余代码不变)

    recommendations = []

    # 定义评分参数 (来自 README)
    level_scores = {"985": 60, "211": 40, "双一流": 20, "一般": 0}
    rank_scores = {"A+": 100, "A": 80, "A-": 70, "B+": 60, "B": 50, "B-": 40, "C+": 30, "C": 20, "C-": 10, "无": 0}
    weights = {"score": 0.4, "level": 0.2, "rank": 0.2, "location": 0.2}

    for school in schools:
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

@app.route('/admin/announcements/reorder', methods=['POST'])
@admin_required
def admin_reorder_announcements():
    """处理公告拖拽排序后保存的请求"""
    announcements_file_path = os.path.join(app.root_path, 'data', 'announcements.json')
    try:
        new_order_data = request.get_json()
        if not new_order_data or 'order' not in new_order_data:
            app.logger.error("无效的排序请求数据")
            return jsonify({'status': 'error', 'message': '无效的请求数据'}), 400

        ordered_titles = new_order_data['order']
        app.logger.debug(f"接收到的新公告顺序 (titles): {ordered_titles}")

        with open(announcements_file_path, 'r+', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 获取排他锁
            try:
                content = f.read()
                if not content:
                    current_announcements = []
                else:
                    current_announcements = json.loads(content)
            except json.JSONDecodeError as e_decode:
                app.logger.error(f"在 admin_reorder_announcements 中解析公告文件时出错: {e_decode}")
                return jsonify({'status': 'error', 'message': f'解析公告数据时出错: {e_decode}'}), 500 # 内部服务器错误更合适

            announcement_map = {ann['title']: ann for ann in current_announcements}
            reordered_announcements = []
            processed_titles = set()
            missing_titles = []

            for title in ordered_titles:
                if title in announcement_map and title not in processed_titles:
                    reordered_announcements.append(announcement_map[title])
                    processed_titles.add(title)
                else:
                    if title not in announcement_map:
                        missing_titles.append(title)
                    app.logger.warning(f"排序请求中的公告标题 '{title}' 在当前数据中不存在或已处理，将被忽略。")

            original_titles = set(ann['title'] for ann in current_announcements)
            if processed_titles != original_titles:
                lost_titles = original_titles - processed_titles
                if lost_titles:
                    app.logger.warning(f"以下公告在排序后丢失: {lost_titles}。将追加到列表末尾。")
                    for lost_title in lost_titles:
                        if lost_title in announcement_map:
                            reordered_announcements.append(announcement_map[lost_title])
            
            if missing_titles:
                app.logger.warning(f"前端发送了以下不存在的公告标题: {missing_titles}")

            app.logger.debug(f"即将写入公告文件的内容:\\n{json.dumps(reordered_announcements, indent=2, ensure_ascii=False)}")
            
            f.seek(0)
            f.truncate()
            json.dump(reordered_announcements, f, ensure_ascii=False, indent=2)
            f.flush() #确保写入磁盘
            os.fsync(f.fileno()) #确保写入磁盘

            app.logger.debug(f"公告文件 {announcements_file_path} 保存后的内容:\\n{json.dumps(reordered_announcements, indent=2, ensure_ascii=False)}")
            # fcntl.flock(f.fileno(), fcntl.LOCK_UN) # 锁会在文件关闭时自动释放
            return jsonify({'status': 'success', 'message': '公告顺序已更新'})

    except IOError as e_io:
        app.logger.error(f"读写或锁定公告文件时发生IO错误: {e_io}", exc_info=True)
        return jsonify({'status': 'error', 'message': '文件操作失败'}), 500
    except json.JSONDecodeError as e_json: # 主要捕获请求数据的JSON解析错误
        app.logger.error(f"解析请求数据时出错: {e_json}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'请求数据格式错误: {e_json}'}), 400
    except Exception as e:
        app.logger.error(f"处理公告排序请求时发生意外错误: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'处理请求时发生内部错误: {e}'}), 500

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
    # 每次请求时加载最新数据
    schools_data_list_full = load_json_data(SCHOOLS_DATA_PATH)
    if schools_data_list_full is None:
        flash('无法加载学校数据文件！', 'danger')
        schools_data_list_full = [] # 使用空列表继续，避免后续错误

    # 获取搜索查询
    search_query = request.args.get('q', '').strip()
    
    filtered_schools = schools_data_list_full
    if search_query:
        query_lower = search_query.lower()
        filtered_schools = [
            school for school in schools_data_list_full 
            if (school.get('name') and isinstance(school.get('name'), str) and query_lower in school.get('name').lower()) or \
               (school.get('id') and query_lower in str(school.get('id')).lower()) or # ID might not always be string, convert safely
               (school.get('province') and isinstance(school.get('province'), str) and query_lower in school.get('province').lower()) or \
               (school.get('computer_rank') and isinstance(school.get('computer_rank'), str) and query_lower in school.get('computer_rank').lower())
        ]

    total_schools = len(filtered_schools)
    page = request.args.get('page', 1, type=int)
    per_page = 50 # 每页显示数量
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated_schools = filtered_schools[start:end]
    
    total_pages = ceil(total_schools / per_page) if total_schools > 0 else 1

    return render_template('admin/schools.html',
                           schools=paginated_schools,
                           page=page,
                           total_pages=total_pages,
                           total_schools=total_schools,
                           search_query=search_query) # 将 search_query 传给模板

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
    """后台：编辑院校顶层信息"""
    # --- Start: Load current data --- 
    schools_data_current = load_json_data(SCHOOLS_DATA_PATH)
    if not schools_data_current:
        flash('无法加载学校数据文件！', 'danger')
        return redirect(url_for('admin_schools'))
    # --- End: Load current data ---

    # 在当前加载的数据中查找学校
    school_to_edit = next((s for s in schools_data_current if s.get('id') == school_id), None)
    app.logger.debug(f"[admin_edit_school] Found school_to_edit for ID '{school_id}': {school_to_edit}") # 调试日志

    if not school_to_edit:
        flash(f'未找到该院校。 ({school_id})', 'danger')
        return redirect(url_for('admin_schools'))

    # 使用加载到的数据填充表单
    form = SchoolEditForm(data=school_to_edit)
    app.logger.debug(f"[admin_edit_school] Form data after init with data: name={form.name.data}, level={form.level.data}, province={form.province.data}") # 调试日志

    if form.validate_on_submit(): # 处理 POST 请求
        try:
            # --- Start: Find index in current data --- 
            school_index = -1
            for i, school in enumerate(schools_data_current):
                if school.get('id') == school_id:
                    school_index = i
                    break
            # --- End: Find index in current data ---

            if school_index == -1:
                # Should not happen if school_to_edit was found earlier, but defensive check
                flash('保存时未能找到学校索引，更新失败。', 'danger')
                return render_template('admin/edit_school.html', form=form, school=school_to_edit)

            # 更新找到的对象 (它仍然是 schools_data_current 列表中的引用)
            form.populate_obj(schools_data_current[school_index]) 

            # 保存更新后的整个列表到文件
            if save_schools_data(schools_data_current):
                flash('院校信息更新成功!', 'success')
            else:
                 flash('院校信息已在内存中更新，但写入文件失败！', 'danger')

            return redirect(url_for('admin_schools'))
        except Exception as e:
             app.logger.error(f"更新学校 {school_id} 时出错: {e}", exc_info=True)
             flash(f'更新院校信息时发生内部错误，请查看服务器日志。({e})', 'danger')

    # GET 请求渲染模板
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
        # 对于不在列表中的省份（如广西、内蒙等B区省份），应返回B区
        b_region_provinces = ["内蒙古", "广西", "海南", "贵州", "云南", "西藏", "甘肃", "青海", "宁夏", "新疆"]
        if province in b_region_provinces:
            return "B区"
        else:
            return "未知地区" # 如果省份名称无效或不属于A/B区

@app.route('/admin/edit-exam-ratios', methods=['GET']) # 保持GET，保存由save路由处理
@admin_required
def admin_edit_exam_ratios():
    exam_ratios_data = load_json_data(EXAM_TYPE_RATIOS_PATH, default_value=[])
    return render_template('admin/edit_exam_ratios.html', exam_ratios_data=exam_ratios_data)

@app.route('/admin/save-exam-ratios', methods=['POST'])
@admin_required
def admin_save_exam_ratios():
    try:
        ratios_form = request.form.to_dict(flat=False) # 获取表单数据，包含列表
        #  ratios_form will look something like:
        # {'ratios[0][value]': ['150'], 'ratios[0][name]': ['自命题'], 
        #  'ratios[1][value]': ['250'], 'ratios[1][name]': ['408统考']}
        # Or, if not using flat=False for such names, you might need to iterate through form keys.
        # A more robust way is to expect specific field names or structure.
        
        updated_ratios = []
        # Assuming the form sends data indexed (e.g., ratios[0][name], ratios[0][value], ratios[1][name]...)
        # This part needs careful parsing based on how edit_exam_ratios.html names its fields.
        # The template uses: name="ratios[{{ loop.index0 }}][value]" and name="ratios[{{ loop.index0 }}][name]"
        
        i = 0
        while True:
            name_key = f'ratios[{i}][name]'
            value_key = f'ratios[{i}][value]'
            if name_key in request.form and value_key in request.form:
                name = request.form[name_key]
                try:
                    value = int(request.form[value_key])
                    updated_ratios.append({"name": name, "value": value})
                except ValueError:
                    flash(f'项目 "{name}" 的值为无效数字，已忽略。 ', 'warning')
                    # Optionally, load the original value or skip
                i += 1
            else:
                break

        if not updated_ratios:
            flash('没有提交有效的比例数据。', 'warning')
            return redirect(url_for('admin_edit_exam_ratios'))

        with open(EXAM_TYPE_RATIOS_PATH, 'w', encoding='utf-8') as f:
            json.dump(updated_ratios, f, ensure_ascii=False, indent=2)
        flash('考试类型比例已成功更新。', 'success')
    except Exception as e:
        app.logger.error(f"保存考试类型比例时出错: {e}", exc_info=True)
        flash(f'保存考试类型比例时发生错误: {e}', 'danger')
    return redirect(url_for('admin_edit_exam_ratios'))

@app.route('/admin/edit-national-lines', methods=['GET'])
@admin_required
def admin_edit_national_lines():
    national_lines_data = load_json_data(NATIONAL_LINES_PATH, default_value={})
    return render_template('admin/edit_national_lines.html', national_lines_data=national_lines_data)

@app.route('/admin/save-national-lines', methods=['POST'])
@admin_required
def admin_save_national_lines():
    try:
        form_data = request.form
        updated_national_lines = {}
        
        # Determine categories present in the form (e.g., from year inputs)
        # Example: form_data might have 'total_years[]', 'politics_years[]', etc.
        categories_in_form = set()
        for key in form_data.keys():
            if key.endswith('_years[]'):
                categories_in_form.add(key.split('_years[]')[0])
        
        for category in categories_in_form:
            updated_national_lines[category] = {"years": [], "scores": {}}
            
            year_values = request.form.getlist(f'{category}_years[]')
            # Filter out empty year strings that might be submitted by empty new fields
            valid_years = [year for year in year_values if year.strip()]
            updated_national_lines[category]["years"] = valid_years
            
            # Find score keys for this category, e.g., total_scores_A区[]
            score_keys_for_category = [key for key in form_data.keys() if key.startswith(f'{category}_scores_') and key.endswith('[]')]
            
            area_names = set()
            for skey in score_keys_for_category:
                # Extract area name: category_scores_AREANAME[]
                area_name_part = skey.replace(f'{category}_scores_', '').replace('[]', '')
                area_names.add(area_name_part)
                
            for area in area_names:
                score_values_str = request.form.getlist(f'{category}_scores_{area}[]')
                # Convert scores to int/float, handling potential errors and empty strings
                valid_scores = []
                for s_val_str in score_values_str:
                    if s_val_str.strip(): # Only process non-empty strings
                        try:
                            # National lines can be integers or have .5
                            if '.' in s_val_str:
                                valid_scores.append(float(s_val_str))
                            else:
                                valid_scores.append(int(s_val_str))
                        except ValueError:
                            app.logger.warning(f"Invalid score value '{s_val_str}' for {category} - {area}, skipping.")
                            valid_scores.append(None) # Or skip, or use a default
                    else:
                        valid_scores.append(None) # Represent empty input as None or skip
                
                # Ensure scores list matches the length of valid_years for this category
                updated_national_lines[category]["scores"][area] = (valid_scores + [None] * len(valid_years))[:len(valid_years)]

        with open(NATIONAL_LINES_PATH, 'w', encoding='utf-8') as f:
            json.dump(updated_national_lines, f, ensure_ascii=False, indent=2)
        flash('国家线数据已成功更新。', 'success')
    except Exception as e:
        app.logger.error(f"保存国家线数据时出错: {e}", exc_info=True)
        flash(f'保存国家线数据时发生错误: {e}', 'danger')
    return redirect(url_for('admin_edit_national_lines'))

@app.route('/admin/announcements/update', methods=['POST'])
@admin_required
def admin_update_announcement():
    """处理更新单个公告的请求"""
    try:
        data = request.get_json()
        original_title = data.get('original_title')
        new_title = data.get('new_title')
        new_url = data.get('new_url')

        if not original_title or not new_title:
            return jsonify({'status': 'error', 'message': '缺少必要的公告信息。'}), 400

        announcements_file_path = os.path.join(app.root_path, 'data', 'announcements.json')
        updated = False

        with open(announcements_file_path, 'r+', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX) # 获取排他锁
            try:
                content = f.read()
                if not content:
                    announcements = []
                else:
                    announcements = json.loads(content)
            except json.JSONDecodeError as e_decode:
                app.logger.error(f"在 admin_update_announcement 中解析公告文件时出错: {e_decode}")
                return jsonify({'status': 'error', 'message': f'解析公告数据时出错: {e_decode}'}), 500

            for ann in announcements:
                if ann['title'] == original_title:
                    ann['title'] = new_title
                    ann['url'] = new_url
                    updated = True
                    break
            
            if updated:
                f.seek(0)
                f.truncate()
                json.dump(announcements, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
                app.logger.info(f"公告 '{original_title}' 已更新为 '{new_title}'")
                return jsonify({'status': 'success', 'message': '公告已成功更新。'})
            else:
                return jsonify({'status': 'error', 'message': '未找到要更新的公告。'}), 404
        
    except IOError as e_io:
        app.logger.error(f"读写或锁定公告文件时发生IO错误 (update): {e_io}", exc_info=True)
        return jsonify({'status': 'error', 'message': '文件操作失败'}), 500
    except json.JSONDecodeError as e_json: # 主要捕获请求数据的JSON解析错误
        app.logger.error(f"解析更新公告的请求数据时出错: {e_json}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'请求数据格式错误: {e_json}'}), 400
    except Exception as e:
        app.logger.error(f"更新公告时发生意外错误: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'更新公告时发生内部错误: {e}'}), 500

@app.route('/admin/announcement/delete', methods=['POST']) # 修改路由以接收JSON
@admin_required
def delete_announcement(): # 修改函数签名，不再需要 index
    """处理删除公告的请求（通过标题）"""
    try:
        data = request.get_json()
        title_to_delete = data.get('title')

        if not title_to_delete:
            return jsonify({'status': 'error', 'message': '缺少要删除的公告标题。'}), 400

        announcements_file_path = os.path.join(app.root_path, 'data', 'announcements.json')
        deleted = False

        with open(announcements_file_path, 'r+', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX) # 获取排他锁
            try:
                content = f.read()
                if not content:
                    announcements = []
                else:
                    announcements = json.loads(content)
            except json.JSONDecodeError as e_decode:
                app.logger.error(f"在 delete_announcement 中解析公告文件时出错: {e_decode}")
                return jsonify({'status': 'error', 'message': f'解析公告数据时出错: {e_decode}'}), 500

            original_count = len(announcements)
            announcements = [ann for ann in announcements if ann['title'] != title_to_delete]
            
            if len(announcements) < original_count:
                deleted = True
                f.seek(0)
                f.truncate()
                json.dump(announcements, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
                app.logger.info(f"公告 '{title_to_delete}' 已被删除。")
                return jsonify({'status': 'success', 'message': '公告已成功删除。'})
            else:
                app.logger.warning(f"尝试删除公告 '{title_to_delete}' 但未找到。")
                return jsonify({'status': 'error', 'message': '未找到要删除的公告。'}), 404

    except IOError as e_io:
        app.logger.error(f"读写或锁定公告文件时发生IO错误 (delete): {e_io}", exc_info=True)
        return jsonify({'status': 'error', 'message': '文件操作失败'}), 500
    except json.JSONDecodeError as e_json: # 主要捕获请求数据的JSON解析错误
        app.logger.error(f"解析删除公告的请求数据时出错: {e_json}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'请求数据格式错误: {e_json}'}), 400
    except Exception as e:
        app.logger.error(f"删除公告时发生意外错误: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'删除公告时发生内部错误: {e}'}), 500

if __name__ == '__main__':
    # 配置日志
    log_dir = os.path.join(BASE_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'app.log')

    # 使用 RotatingFileHandler
    file_handler = RotatingFileHandler(log_file, maxBytes=1024*1024*5, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'))
    
    # 设置日志级别为 DEBUG
    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(file_handler)

    app.logger.info("Flask 应用启动")
    app.run(debug=True, port=5001) 