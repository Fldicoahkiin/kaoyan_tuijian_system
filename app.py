from flask import Flask, jsonify, render_template, session, redirect, url_for, request, flash, abort
from functools import wraps # 导入 wraps 用于装饰器
import json
import os
import datetime # 导入 datetime 模块
# 导入 Werkzeug 用于密码哈希 (比明文安全)
# from werkzeug.security import generate_password_hash, check_password_hash # 移除 Werkzeug security
import re # 导入 re 用于解析分数线
from math import ceil # 用于分页计算
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, Optional, NumberRange
import logging # 导入 logging
from flask_wtf.csrf import CSRFProtect # 导入 CSRFProtect
import portalocker # 导入 portalocker
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
FAVORITES_COUNT_PATH = os.path.join(BASE_DIR, "data", "favorites_count.json")
HOMEPAGE_CONFIG_PATH = os.path.join(BASE_DIR, "data", "homepage_config.json") # 新增配置文件路径

# --- 默认配置 (新增) ---
DEFAULT_HOMEPAGE_CONFIG = {
    "national_line_total_title": "近三年总分国家线趋势",
    "national_line_politics_title": "近三年政治/英语单科线",
    "national_line_others_title": "近三年数学/专业课单科线",
    "exam_type_ratio_title": "自命题 vs 408 比例"
}

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
def load_json_data(file_path, default_value={}):
    """通用 JSON 数据加载函数，带共享文件锁。优先使用 portalocker，失败则回退到 fcntl。"""
    try:
        # 主路径：尝试使用 portalocker
        # import portalocker # 已在顶部导入
        # app.logger.debug(f"Attempting to read {file_path} using portalocker")
        with open(file_path, 'r', encoding='utf-8') as f:
            portalocker.lock(f, portalocker.LOCK_SH) # 获取共享锁
            try:
                content = f.read()
                if not content:
                    app.logger.warning(f"数据文件 {file_path} 为空 (portalocker path)，返回默认值: {default_value}")
                    return default_value
                data = json.loads(content)
                # app.logger.debug(f"Successfully read {file_path} using portalocker")
            finally:
                portalocker.unlock(f)
            return data
    except ImportError: # portalocker 未安装或找不到
        app.logger.warning("portalocker 模块未找到，回退到 fcntl 进行文件读取锁定 (如果可用)。")
        # 后备路径：尝试使用 fcntl
        if platform.system() != "Windows":
            try:
                import fcntl # fcntl 主要用于 POSIX 系统
                # app.logger.debug(f"Attempting to read {file_path} using fcntl")
                with open(file_path, 'r', encoding='utf-8') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH) # 获取共享锁
                    try:
                        content = f.read()
                        if not content:
                            app.logger.warning(f"数据文件 {file_path} 为空 (fcntl path)，返回默认值: {default_value}")
                            return default_value
                        data = json.loads(content)
                        # app.logger.debug(f"Successfully read {file_path} using fcntl")
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN) # 确保释放锁
                    return data
            except ImportError: # fcntl 模块也未找到 (例如在非 POSIX 系统如 Windows)
                app.logger.warning(f"fcntl 模块在非Windows系统上也未找到。将尝试在不加锁的情况下读取文件 {file_path} (非线程安全)。")
                # Fall through to no-lock read
            except Exception as e_fcntl: # fcntl 路径下的其他错误 (例如 IOError, json.JSONDecodeError)
                app.logger.error(f"使用 fcntl 加载 JSON 数据 {file_path} 时发生错误: {e_fcntl}", exc_info=True) # Corrected typo
                return default_value
        else:
            app.logger.warning(f"当前为Windows系统且portalocker不可用，fcntl不适用。将尝试在不加锁的情况下读取文件 {file_path} (非线程安全)。")
        
        # 最后手段：在不加锁的情况下读取 (注意：非线程安全) - 适用于 portalocker/fcntl 均失败或 Windows下portalocker失败
        try:
            # app.logger.debug(f"Attempting to read {file_path} without locking")
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content:
                    app.logger.warning(f"数据文件 {file_path} 为空 (no-lock path)，返回默认值: {default_value}")
                    return default_value
                data = json.loads(content)
                # app.logger.debug(f"Successfully read {file_path} without locking")
            return data
        except Exception as e_nolock:
            app.logger.error(f"在没有锁的情况下读取文件 {file_path} 也失败了: {e_nolock}", exc_info=True)
            return default_value
            
    except FileNotFoundError:
        # 文件未找到是常见情况，可能不是一个error，而是逻辑的一部分（例如，首次运行时）
        app.logger.info(f"数据文件未找到: {file_path}。这可能是正常的，将返回默认值: {default_value}")
        return default_value
    except json.JSONDecodeError as e_json:
        app.logger.error(f"解析 JSON 数据文件 {file_path} 时出错: {e_json}", exc_info=True)
        return default_value
    except IOError as e_io: # portalocker 路径下的 IO 错误 (例如权限问题)
        app.logger.error(f"读取文件 {file_path} 时发生 IO 错误 (portalocker path): {e_io}", exc_info=True)
        return default_value
    except Exception as e_main: # portalocker 路径下的其他未知错误
        app.logger.error(f"加载 JSON 数据 {file_path} 时发生未知错误 (portalocker path): {e_main}", exc_info=True)
        return default_value

# --- 新增：加载首页配置函数 ---
def load_homepage_config():
    """加载首页配置文件，如果文件不存在或无效，则返回默认配置。"""
    config_data = load_json_data(HOMEPAGE_CONFIG_PATH, default_value=DEFAULT_HOMEPAGE_CONFIG)
    # 确保返回的字典包含所有默认键
    final_config = DEFAULT_HOMEPAGE_CONFIG.copy()
    final_config.update(config_data) # 用加载的数据覆盖默认值
    return final_config

# --- 新增：保存首页配置函数 ---
def save_homepage_config(config_data):
    """将首页配置数据保存到 JSON 文件，带文件锁。"""
    try:
        os.makedirs(os.path.dirname(HOMEPAGE_CONFIG_PATH), exist_ok=True)
        with open(HOMEPAGE_CONFIG_PATH, 'w', encoding='utf-8') as f:
            portalocker.lock(f, portalocker.LOCK_EX)
            try:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
                app.logger.info(f"首页配置已成功写入 {HOMEPAGE_CONFIG_PATH}")
                return True
            finally:
                portalocker.unlock(f)
    except ImportError:
        app.logger.warning("portalocker not found, attempting fcntl for saving homepage config.")
        try:
            os.makedirs(os.path.dirname(HOMEPAGE_CONFIG_PATH), exist_ok=True)
            with open(HOMEPAGE_CONFIG_PATH, 'w', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX) 
                try:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                    app.logger.info(f"首页配置已成功写入 {HOMEPAGE_CONFIG_PATH} (using fcntl)")
                    return True
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception as e_fcntl_save:
            app.logger.error(f"使用fcntl保存首页配置文件 {HOMEPAGE_CONFIG_PATH} 时发生错误: {e_fcntl_save}", exc_info=True)
            return False 
    except IOError as e_io:
        app.logger.error(f"保存首页配置文件 {HOMEPAGE_CONFIG_PATH} 时发生IO错误: {e_io}", exc_info=True)
        return False
    except Exception as e:
        app.logger.error(f"保存首页配置文件时发生意外错误: {e}", exc_info=True)
        return False

# --- 数据保存函数 (新增) ---
def save_schools_data(data):
    """将学校数据（列表）保存到 JSON 文件，带文件锁。优先 portalocker, 回退 fcntl。"""
    try:
        # 主路径：尝试使用 portalocker
        import portalocker
        os.makedirs(os.path.dirname(SCHOOLS_DATA_PATH), exist_ok=True)
        with open(SCHOOLS_DATA_PATH, 'w', encoding='utf-8') as f:
            portalocker.lock(f, portalocker.LOCK_EX)
            try:
                cleaned_data = replace_nan_with_none(data)
                json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
                app.logger.info(f"学校数据已成功写入 {SCHOOLS_DATA_PATH} (portalocker)")
                # 写入成功后，在 finally 解锁前返回 True
            except Exception as e_write_portalocker:
                app.logger.error(f"使用 portalocker 写入学校数据时出错: {e_write_portalocker}", exc_info=True)
                return False # 写入失败，在 finally 解锁后会返回此 False
            finally:
                portalocker.unlock(f)
            return True # 如果 try 块成功执行完毕（没有异常），则在此返回 True

    except ImportError:
        app.logger.warning("portalocker 模块未找到，回退到 fcntl 进行文件写入锁定 (如果可用)。")
        # 后备路径：尝试使用 fcntl
        try:
            import fcntl # fcntl 主要用于 POSIX 系统
            os.makedirs(os.path.dirname(SCHOOLS_DATA_PATH), exist_ok=True)
            with open(SCHOOLS_DATA_PATH, 'w', encoding='utf-8') as f_fcntl: # Renamed to avoid conflict
                fcntl.flock(f_fcntl.fileno(), fcntl.LOCK_EX)
                try:
                    cleaned_data = replace_nan_with_none(data)
                    json.dump(cleaned_data, f_fcntl, ensure_ascii=False, indent=2)
                    f_fcntl.flush()
                    os.fsync(f_fcntl.fileno())
                    app.logger.info(f"学校数据已成功写入 {SCHOOLS_DATA_PATH} (using fcntl)")
                    # 写入成功后，在 finally 解锁前返回 True
                except Exception as e_write_fcntl:
                    app.logger.error(f"使用 fcntl 写入学校数据时出错: {e_write_fcntl}", exc_info=True)
                    return False # 写入失败，在 finally 解锁后会返回此 False
                finally:
                    fcntl.flock(f_fcntl.fileno(), fcntl.LOCK_UN)
                return True # 如果 try 块成功执行完毕（没有异常），则在此返回 True

        except ImportError: # fcntl 模块也未找到
            app.logger.error(f"fcntl 模块也未找到。无法为写入操作锁定文件 {SCHOOLS_DATA_PATH}。")
            app.logger.warning(f"警告：将尝试在不加锁的情况下保存学校数据到 {SCHOOLS_DATA_PATH} (非线程安全)。")
            try:
                os.makedirs(os.path.dirname(SCHOOLS_DATA_PATH), exist_ok=True)
                with open(SCHOOLS_DATA_PATH, 'w', encoding='utf-8') as f_nolock:
                    cleaned_data = replace_nan_with_none(data)
                    json.dump(cleaned_data, f_nolock, ensure_ascii=False, indent=2)
                    f_nolock.flush()
                    os.fsync(f_nolock.fileno())
                app.logger.info(f"学校数据已在不加锁的情况下写入 {SCHOOLS_DATA_PATH}。")
                return True
            except Exception as e_nolock_save:
                app.logger.error(f"在不加锁的情况下保存学校数据 {SCHOOLS_DATA_PATH} 也失败了: {e_nolock_save}", exc_info=True)
                return False
        except Exception as e_fcntl_setup: # fcntl 路径下的其他设置错误 (例如makedirs, open 失败)
            app.logger.error(f"Fcntl 后备路径中设置保存学校数据 {SCHOOLS_DATA_PATH} 时失败: {e_fcntl_setup}", exc_info=True)
            return False
            
    except IOError as e_io_portalocker_setup: # Catches IOError for portalocker path (e.g. os.makedirs, open before lock)
        app.logger.error(f"保存学校数据 {SCHOOLS_DATA_PATH} 时发生IO错误 (portalocker setup): {e_io_portalocker_setup}", exc_info=True)
        return False
    except Exception as e_main_portalocker: # Other errors in portalocker path (e.g. initial open or makedirs failed)
        app.logger.error(f"保存学校数据 {SCHOOLS_DATA_PATH} 时发生未知错误 (portalocker path): {e_main_portalocker}", exc_info=True)
        return False

# --- 需要确保 replace_nan_with_none 函数存在于 app.py 中 --- 
# 如果它只在 data_processor.py 中，需要移过来或导入
def replace_nan_with_none(obj):
    if isinstance(obj, list):
        return [replace_nan_with_none(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: replace_nan_with_none(value) for key, value in obj.items()}
    elif isinstance(obj, float) and pd.isna(obj): # 需要导入 pandas as pd
        import math 
        if math.isnan(obj):
           return None
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
    target_level = SelectField('目标院校等级', 
                             choices=[('', '-- 请选择 --'), ('985', '985'), ('211', '211'), ('双一流', '双一流'), ('普通院校', '普通院校')], 
                             validators=[Optional()])
    target_rank = SelectField('偏好计算机等级', choices=[], validators=[Optional()])
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
    level = SelectField('院校等级', choices=[('', '未知'), ('985', '985'), ('211', '211'), ('双一流', '双一流'), ('普通院校', '普通院校')], validators=[Optional()], default='')
    province = StringField('省份', validators=[Optional(), Length(max=50)])
    computer_rank = StringField('计算机等级', validators=[Optional(), Length(max=100)])
    intro = TextAreaField('简介', validators=[Optional()])
    enrollment_24_school_total = StringField('24年总招生人数', validators=[Optional()])
    submit = SubmitField('保存更改')

# --- 新增：首页配置表单 ---
class HomepageConfigForm(FlaskForm):
    national_line_total_title = StringField('总分国家线图表标题', validators=[DataRequired()])
    national_line_politics_title = StringField('政治/英语线图表标题', validators=[DataRequired()])
    national_line_others_title = StringField('数学/专业课线图表标题', validators=[DataRequired()])
    exam_type_ratio_title = StringField('自命题vs408比例图表标题', validators=[DataRequired()])
    submit = SubmitField('保存更改')

# --- 视图函数 / 路由 ---

@app.route('/')
def index():
    """渲染主页 (可视化大面板)。"""
    homepage_config = load_homepage_config() # 加载首页配置
    return render_template('index.html', homepage_config=homepage_config) # 传递配置到模板

@app.route('/api/schools/list')
def api_schools_list():
    """API: 返回用于首页滚动列表的简化学校信息"""
    try:
        data = load_json_data(SCHOOLS_DATA_PATH)
        if data is None: data = [] # Ensure data is an empty list if file not found or empty
    except Exception as e:
        print(f"Error loading school data for API: {e}")
        data = []

    simplified_schools = []
    for school in data:
        simplified_schools.append({
            'id': school.get('id'),
            'name': school.get('name'),
            'province': school.get('province'),
            'level': school.get('level'),
            'region': school.get('region'),
            'computer_rank': school.get('computer_rank'),
            'enrollment_24_school_total': school.get('enrollment_24_school_total', '未知'), # Make sure this key exists or provide default
            'exam_subjects': school.get('exam_subjects_summary', "见各专业详情") # Use the new summary field
        })
    
    # print(f"API /api/schools/list returning {len(simplified_schools)} schools.") # Optional: for debugging
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
    # This old endpoint might still be used by something, or can be deprecated.
    # The new requirement is for a 3-year bar chart, served by /api/national-lines/politics-recent
    if not lines_data or 'politics' not in lines_data or 'years' not in lines_data['politics'] or 'scores' not in lines_data['politics']:
        return jsonify({"error": "Politics data (full history) not found or incomplete"}), 404

    politics_data = lines_data['politics']
    years = politics_data.get('years', [])
    scores_raw = politics_data.get('scores', {})
    
    # Make legend names more specific to politics
    processed_scores = {}
    if "A区" in scores_raw:
        processed_scores["A区政治"] = scores_raw["A区"]
    if "B区" in scores_raw:
        processed_scores["B区政治"] = scores_raw["B区"]
    
    # Fallback if "A区", "B区" are not the exact keys, use what's there but prefix with "政治"
    if not processed_scores and scores_raw:
        for key, value in scores_raw.items():
            processed_scores[f"{key} 政治"] = value

    # Ensure score lists match year list length
    final_scores = {}
    for name, data_list in processed_scores.items():
        if isinstance(data_list, list) and len(data_list) == len(years):
            final_scores[name] = data_list
        else:
            app.logger.warning(f"Legacy API /politics: Score list length mismatch for '{name}'. Padding with None.")
            final_scores[name] = ([None] * len(years))


    echarts_data = {
        "years": years,
        "legend": list(final_scores.keys()),
        "series": [
            {"name": name, "data": data, "type": "bar", "barMaxWidth": 30}
            for name, data in final_scores.items()
        ],
         "yAxis": {"min": "dataMin"}
    }
    return jsonify(echarts_data)

@app.route('/api/national-lines/others')
def get_national_line_others():
    lines_data = load_json_data(NATIONAL_LINES_PATH)
    # This endpoint is likely to be deprecated or significantly changed
    # given the new, more specific subject endpoints.
    if not lines_data or 'others' not in lines_data or 'years' not in lines_data['others'] or 'scores' not in lines_data['others']:
        return jsonify({"error": "Legacy 'others' data not found or incomplete"}), 404

    others_data = lines_data['others']
    years = others_data.get('years', [])
    scores_raw = others_data.get('scores', {})

    # Attempt to provide something meaningful, e.g. "数学一" data if it exists,
    # to maintain some backward compatibility if this API is still hit.
    # This is a placeholder for what used to be complex logic.
    # The frontend should ideally migrate to new APIs.
    
    series_list = []
    legend_list = []

    # Example: try to find "数学一 (A区)" and "数学一 (B区)"
    math_one_a_key = "数学一 (A区)"
    math_one_b_key = "数学一 (B区)"

    if math_one_a_key in scores_raw and isinstance(scores_raw[math_one_a_key], list) and len(scores_raw[math_one_a_key]) == len(years):
        series_list.append({
            "name": "A类数学/专业课 (示例)", # Generic legend
            "data": scores_raw[math_one_a_key],
            "type": "line", "smooth": True
        })
        legend_list.append("A类数学/专业课 (示例)")

    if math_one_b_key in scores_raw and isinstance(scores_raw[math_one_b_key], list) and len(scores_raw[math_one_b_key]) == len(years):
        series_list.append({
            "name": "B类数学/专业课 (示例)", # Generic legend
            "data": scores_raw[math_one_b_key],
            "type": "line", "smooth": True
        })
        legend_list.append("B类数学/专业课 (示例)")

    if not series_list and scores_raw: # Fallback: take the first few items from 'others'
        app.logger.info("Legacy API /others: Falling back to generic series from 'others' data.")
        count = 0
        for name, data in scores_raw.items():
            if isinstance(data, list) and len(data) == len(years):
                series_list.append({"name": name, "data": data, "type": "line", "smooth": True})
                legend_list.append(name)
                count += 1
                if count >= 2: # Limit to a few example series
                    break
    
    echarts_data = {
        "years": years,
        "legend": legend_list,
        "series": series_list,
        "yAxis": {"min": "dataMin"}
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
    lock_acquired = False
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
            # 尝试 portalocker
            try:
                # import portalocker # 已在顶部导入
                portalocker.lock(f, portalocker.LOCK_SH)
                lock_acquired = True
                app.logger.debug(f"portalocker shared lock acquired for {announcements_file_path}")
            except ImportError:
                 # 尝试 fcntl (非Windows)
                if platform.system() != "Windows":
                    try:
                        import fcntl
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH) # 获取共享锁
                        lock_acquired = True
                        app.logger.debug(f"fcntl shared lock acquired for {announcements_file_path}")
                    except ImportError:
                        app.logger.warning(f"portalocker and fcntl not available for reading {announcements_file_path}. Proceeding without lock.")
                else:
                    app.logger.warning(f"portalocker not available on Windows for reading {announcements_file_path}. fcntl not applicable. Proceeding without lock.")
            except Exception as e_lock:
                app.logger.error(f"Error acquiring lock for {announcements_file_path}: {e_lock}")
                # 继续尝试无锁读取

            # 读取文件内容
            try:
                content = f.read()
                if not content: # 文件为空
                    app.logger.warning(f"公告文件 {announcements_file_path} 为空，返回空列表。")
                    announcements = []
                else:
                    announcements = json.loads(content)
            except json.JSONDecodeError as e_decode:
                app.logger.error(f"在 get_announcements 中解析公告文件 {announcements_file_path} 时出错: {e_decode}")
                return jsonify([]) 
            finally:
                if lock_acquired:
                    try:
                        # import portalocker # 已在顶部导入
                        portalocker.unlock(f)
                        app.logger.debug(f"portalocker lock released for {announcements_file_path}")
                    except (ImportError, NameError, AttributeError): # NameError/AttributeError if portalocker was not successfully used
                        if platform.system() != "Windows":
                            try:
                                import fcntl
                                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                                app.logger.debug(f"fcntl lock released for {announcements_file_path}")
                            except (ImportError, NameError):
                                pass # No lock to release
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
    
    form = RegistrationForm() # 实例化表单
    if form.validate_on_submit(): # POST 请求，且数据有效
        username = form.username.data
        password = form.password.data
        # confirm_password 的校验由 EqualTo validator 在 form.validate_on_submit() 中处理

        if get_user_data(username) is not None:
            flash('用户名已存在！', 'error')
            # 当验证失败或逻辑错误时，重新渲染表单，并传递form对象
            return render_template('register.html', form=form)

        # hashed_password = generate_password_hash(password) # 移除哈希
        user_data = {
            "username": username,
            # "password_hash": hashed_password, # 修改为明文密码
            "password": password, # 直接存储明文密码
            "profile": { 
                "education_background": "",
                "major_area": "",
                "target_location": "",
                "target_level": "", 
                "target_rank": "", #确保新用户也有此字段
                "expected_score": None
            },
            "favorites": []
        }

        if save_user_data(username, user_data):
            flash('注册成功！请登录。', 'success')
            return redirect(url_for('login'))
        else:
            flash('注册过程中发生错误，请稍后再试。', 'error')
            # 保存失败也应重新渲染表单
            return render_template('register.html', form=form)

    # GET 请求或 POST 数据无效时
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('index'))
    
    form = LoginForm() # 实例化表单
    if form.validate_on_submit(): # POST 请求且数据有效
        username = form.username.data
        password = form.password.data

        user_data = get_user_data(username)

        if user_data is None:
            flash('用户名不存在！', 'error')
        # elif check_password_hash(user_data.get('password_hash', ''), password): # 修改为明文比较
        elif user_data.get('password') == password:
            session['username'] = username
            flash('登录成功！', 'success')
            return redirect(request.args.get('next') or url_for('index')) # 跳转到 next 或首页
        else:
            flash('密码错误！', 'error')
        
        # 如果登录失败（用户名不存在或密码错误），重新渲染登录表单并传递form对象
        return render_template('login.html', form=form)

    # GET 请求或 POST 数据无效时
    return render_template('login.html', form=form)

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
        flash('无法加载用户数据，请重新登录。', 'error')
        session.pop('username', None)
        return redirect(url_for('login'))

    # 从 user_data 初始化表单，如果profile不存在则使用空字典
    form = ProfileForm(data=user_data.get('profile', {}))

    # 动态填充 target_rank 的选项
    all_schools_data = load_json_data(SCHOOLS_DATA_PATH)
    if all_schools_data: # 确保数据已加载
        all_ranks_for_form = sorted(list(set(s.get('computer_rank', '') for s in all_schools_data if s.get('computer_rank'))))
        form.target_rank.choices = [('', '任何等级')] + [(r, r) for r in all_ranks_for_form]
    else:
        form.target_rank.choices = [('', '任何等级')]

    if form.validate_on_submit(): # POST 请求
        user_profile = user_data.get('profile', {}) # 获取或初始化 profile 字典
        user_profile['education_background'] = form.education_background.data
        user_profile['major_area'] = form.major_area.data
        user_profile['target_location'] = form.target_location.data
        user_profile['target_level'] = form.target_level.data
        user_profile['target_rank'] = form.target_rank.data # 新增保存
        try:
            expected_score_str = form.expected_score.data # 从 form 对象获取数据
            user_profile['expected_score'] = int(expected_score_str) if expected_score_str is not None else None
        except (ValueError, TypeError):
            user_profile['expected_score'] = None

        user_data['profile'] = user_profile #确保profile字典被存回user_data
        if save_user_data(username, user_data):
            flash('个人资料更新成功！', 'success')
        else:
            flash('个人资料更新失败。', 'error')
        return redirect(url_for('profile'))

    # GET 请求，确保表单字段能正确显示已保存的值
    # 如果 form 是通过 data=user_data.get('profile', {}) 初始化的，
    # 并且 ProfileForm 中的字段名与 profile 字典中的键名匹配，
    # WTForms 会自动处理值的填充。
    # 如果 target_rank 的值在 choices 中，它会被选中。
    # 我们需要确保在GET请求时，如果user_data['profile']中有target_rank，form能正确显示
    if request.method == 'GET' and user_data.get('profile'):
        form.target_rank.data = user_data.get('profile', {}).get('target_rank')

    return render_template('profile.html', form=form)

# --- 其他功能路由 --- 
# (添加占位路由以使 base.html 中的链接有效)

@app.route('/school-list')
def school_list():
    # 获取查询参数和页码
    search_query = request.args.get('q', '')
    province_filter = request.args.get('province', '')
    level_filter = request.args.get('level', '')
    rank_filter = request.args.get('rank', '')
    region_filter = request.args.get('region_filter', '')
    sort_by = request.args.get('sort', 'favorites') # 修正这里的默认值为 'favorites'
    page = request.args.get('page', 1, type=int)
    per_page = 20 # 每页显示数量

    all_schools = load_json_data(SCHOOLS_DATA_PATH)
    if not all_schools:
        flash('无法加载学校数据。', 'warning')
        all_schools = []

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
        filtered_schools = [s for s in filtered_schools if s.get('computer_rank') == rank_filter]
    if region_filter:
        filtered_schools = [s for s in filtered_schools if s.get('region') == region_filter]
        
    # 加载收藏数
    favorites_counts = load_favorites_count() # 确保 get_favorites_count() 正确工作

    # 为每个学校添加收藏数字段，以便后续排序和显示
    for school in filtered_schools:
        school_id = school.get('id', school.get('name')) # 获取学校ID
        # 确保使用字符串ID进行查找，因为JSON键可能是字符串
        school['favorites_count'] = favorites_counts.get(str(school_id), 0) 

    # --- 修正排序逻辑的默认值 ---
    # 获取排序参数，确保默认按收藏数排序
    sort_by = request.args.get('sort', 'favorites') # 修正这里的默认值为 'favorites'

    if sort_by == 'default':
        # 按默认的区域、省份、名称排序
        filtered_schools.sort(key=lambda x: (
            x.get('region') or '', 
            x.get('province') or '', 
            x.get('name') or ''
        ))
        app.logger.debug("Sorting schools by default (region, province, name).")
    else: # 默认情况 (sort_by is 'favorites' or not provided)
        # 按 'favorites_count' 降序排序
        filtered_schools.sort(key=lambda x: x.get('favorites_count', 0), reverse=True)
        app.logger.debug("Sorting schools by favorites count (descending) as default or requested.")
    # --- 结束修改 ---

    total_schools = len(filtered_schools)
    total_pages = ceil(total_schools / per_page)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    paginated_schools = filtered_schools[start_index:end_index]

    all_provinces = sorted(list(set(s.get('province', '未知省份') for s in all_schools if s.get('province'))))
    all_levels = sorted(list(set(s.get('level', '普通院校') for s in all_schools if s.get('level'))), key=lambda x: (x != '985', x != '211', x != '双一流', x))
    all_ranks = sorted(list(set(s.get('computer_rank', '') for s in all_schools if s.get('computer_rank'))))
    all_regions = sorted(list(set(s.get('region', '') for s in all_schools if s.get('region'))))

    current_user_favorites = []
    if 'username' in session:
        user_data = get_user_data(session['username'])
        if user_data and 'favorites' in user_data:
            current_user_favorites = user_data['favorites']
    
    # # Debugging logs moved or removed for clarity, favorite count is already added above
    # app.logger.debug(f"[school_list] Loaded favorites counts: {favorites_counts}")
    # app.logger.debug("--- [school_list] Assigning favorite status and counts to paginated schools ---") # DEBUG
    for school in paginated_schools:
        school_id = school.get('id')
        school['is_favorite'] = school_id in current_user_favorites
        # Favorites count is already added above
        # school['favorites_count'] = favorites_counts.get(str(school_id), 0)
    # app.logger.debug("--- [school_list] Finished assigning --- ") # DEBUG

    return render_template('school_list.html',
                           schools=paginated_schools,
                           page=page,
                           total_pages=total_pages,
                           total_schools=total_schools,
                           all_provinces=all_provinces,
                           all_levels=all_levels,
                           all_ranks=all_ranks,
                           all_regions=all_regions,
                           current_province=province_filter,
                           current_level=level_filter,
                           current_rank=rank_filter,
                           current_region=region_filter,
                           current_sort=sort_by, # 传递当前的排序方式
                           search_query=search_query,
                           current_user_favorites=current_user_favorites)

@app.route('/recommend', methods=['GET'])
def recommend():
    user_profile = {}
    run_recommendation = False
    recommendations_on_page = []
    pagination_data = None

    if 'username' in session:
        user_data = get_user_data(session['username'])
        if user_data and 'profile' in user_data:
            user_profile = user_data['profile']

    target_score_str = request.args.get('target_score')
    target_level = request.args.get('target_level') or user_profile.get('target_level')
    target_rank = request.args.get('target_rank') or user_profile.get('target_rank') # 修改这里以从profile获取
    target_location = request.args.get('target_location') or user_profile.get('target_location')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    target_score = None
    if target_score_str:
        try:
            target_score = int(target_score_str)
            run_recommendation = True
        except ValueError:
            flash('目标分数必须是有效的数字！', 'error')
    elif user_profile.get('expected_score') is not None:
        target_score = user_profile.get('expected_score')
        if request.args.get('target_level') or request.args.get('target_location') or request.args.get('target_rank'):
            run_recommendation = True
    
    if request.method == 'GET' and any(k in request.args for k in ['target_score', 'target_level', 'target_location', 'target_rank']):
        run_recommendation = True

    if run_recommendation:
        if target_score is None:
            flash('请输入目标分数以获取推荐 (或在个人中心设置)。', 'warning')
        elif not (target_level or target_location):
            flash('请输入期望的院校等级或目标地区以获取推荐 (或在个人中心设置)。', 'warning')
        else:
            favorites_counts = get_favorites_count()
            all_recommended_schools = calculate_recommendations(
                target_score,
                target_level,
                target_rank,
                target_location,
                favorites_counts
            )
            
            total_items = len(all_recommended_schools)
            total_pages = ceil(total_items / per_page)
            start_index = (page - 1) * per_page
            end_index = start_index + per_page
            recommendations_on_page = all_recommended_schools[start_index:end_index]

            pagination_args = request.args.copy()
            if 'page' in pagination_args:
                pagination_args.pop('page')

            pagination_data = {
                'page': page,
                'per_page': per_page,
                'total_items': total_items,
                'total_pages': total_pages,
                'args': pagination_args
            }
    else:
        if 'username' in session and not any(k in request.args for k in ['target_score', 'target_level', 'target_location', 'target_rank']):
            if user_profile.get('expected_score') and (user_profile.get('target_level') or user_profile.get('target_location')):
                flash('您的个人偏好已加载。点击 "获取/刷新推荐" 查看结果。', 'info')
            else:
                flash('请设置推荐条件或在个人中心完善偏好后，点击获取推荐。', 'info')

    return render_template('recommendation.html', 
                           recommendations=recommendations_on_page, 
                           user_profile=user_profile,
                           run_recommendation=run_recommendation,
                           pagination=pagination_data)

@app.route('/school/<path:school_id>')
def school_detail(school_id):
    schools_data_list = load_json_data(SCHOOLS_DATA_PATH)
    if not schools_data_list:
        abort(404, description="无法加载学校数据")
    
    school = next((s for s in schools_data_list if s.get('id') == school_id), None)
    if school is None:
        school = next((s for s in schools_data_list if s.get('name') == school_id), None)

    if school is None:
        app.logger.warning(f"尝试访问不存在的学校: {school_id}")
        abort(404, description=f"未找到ID或名称为 {school_id} 的学校")
        
    user_favorites = []
    if 'username' in session:
        user_data = get_user_data(session['username'])
        if user_data and 'favorites' in user_data:
            user_favorites = user_data['favorites']
            
    score_chart_options = None

    return render_template('school_detail.html', 
                           school=school, 
                           user_favorites=user_favorites,
                           score_chart_options=score_chart_options)

@app.route('/api/school/favorite/<path:school_id>', methods=['POST', 'DELETE'])
def toggle_favorite(school_id):
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': '请先登录', 'redirect': url_for('login', next=request.referrer)}), 401

    username = session['username']
    user_data = get_user_data(username)
    # --- 增加用户数据有效性检查 ---
    if not user_data or not isinstance(user_data, dict):
        app.logger.error(f"加载用户 '{username}' 的数据失败或数据格式不正确，无法处理收藏请求。")
        return jsonify({'status': 'error', 'message': '无法加载有效的用户信息，请稍后重试或联系管理员。'}), 500
    # --- 结束检查 ---

    # 加载学校数据用于验证
    schools_data_list = load_json_data(SCHOOLS_DATA_PATH)
    if not schools_data_list:
        app.logger.error("无法加载学校数据，无法验证 school_id。")
        # 返回错误，因为无法确认学校是否存在
        return jsonify({'status': 'error', 'message': '无法加载学校数据'}), 500

    # 检查学校是否存在 (同时检查 ID 和 Name 以应对可能的复合ID)
    school_exists_by_id = any(s.get('id') == school_id for s in schools_data_list)
    school_exists_by_name = any(s.get('name') == school_id for s in schools_data_list)

    if not school_exists_by_id and not school_exists_by_name:
         app.logger.warning(f"尝试收藏/取消收藏不存在的学校ID或名称: {school_id}")
         return jsonify({'status': 'error', 'message': '无效的学校ID或名称。'}), 404
    # --- 结束学校存在性检查 ---

    favorites = user_data.get('favorites', [])
    # --- 确保 favorites 是列表 ---
    if not isinstance(favorites, list):
        app.logger.error(f"用户 '{username}' 的收藏夹数据不是列表格式。已重置为空列表。")
        favorites = []
    # --- 结束列表检查 ---

    action = ''
    count_changed = False
    new_total_count = 0 # 初始化

    # 加载当前的全局收藏数
    current_counts = load_favorites_count()
    # 使用真实的 school ID 来更新计数 (如果通过 name 匹配)
    actual_school_id = school_id # 默认使用传入的
    if not school_exists_by_id and school_exists_by_name:
        # 如果是通过 name 匹配到的，理论上应该找到对应的 ID，但这里简化处理，仍用 name 作为 key
        # 更优方案是在找到 name 后获取其 ID
        pass 
    school_current_count = current_counts.get(actual_school_id, 0)

    if request.method == 'POST':
        if actual_school_id not in favorites:
            favorites.append(actual_school_id)
            action = 'favorited'
            new_total_count = school_current_count + 1
            count_changed = True
        else:
            action = 'already_favorited'
            new_total_count = school_current_count # 数量不变
    elif request.method == 'DELETE':
        if actual_school_id in favorites:
            favorites.remove(actual_school_id)
            action = 'unfavorited'
            new_total_count = max(0, school_current_count - 1) # 确保不小于0
            count_changed = True
        else:
            action = 'not_favorited'
            new_total_count = school_current_count # 数量不变
        
    # 保存用户数据
    user_data['favorites'] = favorites
    if not save_user_data(username, user_data):
        # 保存用户数据失败是严重问题，需要回滚或明确告知失败
        app.logger.error(f"保存用户 '{username}' 的收藏夹时出错！")
        return jsonify({'status': 'error', 'message': '保存用户收藏夹时出错'}), 500

    # 如果收藏状态实际改变了，则更新并保存全局收藏数
    if count_changed:
        current_counts[actual_school_id] = new_total_count
        if not save_favorites_count(current_counts):
            # 警告：用户数据已更新，但全局计数更新失败
            app.logger.error(f"更新全局收藏数文件失败，但用户 {username} 的收藏夹已更新！可能导致计数不一致。")
            # 即使计数文件保存失败，用户操作已成功，仍返回成功和预期的计数
            pass # 继续执行，返回成功和预期的 new_total_count

    message = ''
    if action == 'favorited': message = '收藏成功！'
    elif action == 'unfavorited': message = '已取消收藏。'
    # 返回包含新计数的成功响应
    return jsonify({'status': 'success', 'action': action, 'school_id': actual_school_id, 'message': message, 'new_count': new_total_count})

def calculate_recommendations(target_score, target_level, target_rank_pref, target_location, favorites_counts):
    """根据用户偏好计算推荐结果"""
    schools = load_json_data(SCHOOLS_DATA_PATH)
    if not schools:
        app.logger.error("计算推荐时无法加载学校数据！")
        return [] 
    
    try:
        target_score = int(target_score) if target_score is not None else None
    except (ValueError, TypeError):
        target_score = None

    recommendations = []
    level_scores = {"985": 100, "211": 80, "双一流": 60, "普通院校": 30, None: 0, "":0}
    rank_map = {"A+": 100, "A": 90, "A-": 85, "B+": 75, "B": 70, "B-": 65, "C+": 55, "C": 50, "C-": 45, "无": 20, None: 20, "":20}
    weights = {"score_similarity": 0.35, "level": 0.20, "rank": 0.15, "location": 0.20, "popularity": 0.10}

    for school in schools:
        school_id = school.get('id', school.get('name'))
        recommend_score = 0

        location_match_score = 0
        if target_location and school.get('province') == target_location:
            location_match_score = 100
        elif target_location and school.get('region') == target_location:
            location_match_score = 50
        recommend_score += weights["location"] * location_match_score
        
        school_level_val = school.get('level')
        level_match_score = level_scores.get(school_level_val, 0)
        if target_level and school_level_val == target_level:
            level_match_score = 100
        elif target_level:
            level_match_score *= 0.7
        recommend_score += weights["level"] * level_match_score

        school_rank_val = school.get('computer_rank')
        rank_match_score = rank_map.get(school_rank_val, 20)
        if target_rank_pref and school_rank_val == target_rank_pref:
            rank_match_score = rank_map.get(target_rank_pref, rank_match_score)
        elif target_rank_pref:
            if rank_map.get(school_rank_val, 0) < rank_map.get(target_rank_pref, 100):
                 rank_match_score *= 0.8 
        recommend_score += weights["rank"] * rank_match_score
        
        score_similarity_points = 0
        if target_score is not None:
            avg_major_score = None
            relevant_major_scores = []
            if school.get('departments'):
                for dept in school.get('departments', []):
                    for major in dept.get('majors', []):
                        score_24_str = major.get('score_lines', {}).get('2024')
                        score_23_str = major.get('score_lines', {}).get('2023')
                        
                        current_major_scores = []
                        for s_str in [score_24_str, score_23_str]:
                            if s_str and isinstance(s_str, str):
                                match = re.search(r'总分(\d+)', s_str)
                                if not match:
                                     match = re.search(r'(\d{3})', s_str)
                                if match:
                                    try:
                                        current_major_scores.append(int(match.group(1)))
                                    except ValueError:
                                        pass
                        if current_major_scores:
                            relevant_major_scores.append(max(current_major_scores))
            
            if relevant_major_scores:
                avg_major_score = sum(relevant_major_scores) / len(relevant_major_scores)

            if avg_major_score is not None and target_score is not None:
                diff = abs(target_score - avg_major_score)
                score_similarity_points = max(0, 100 - (diff * 2))
            elif target_level and school.get('level') == target_level:
                 score_similarity_points = 30
            else:
                score_similarity_points = 10

        recommend_score += weights["score_similarity"] * score_similarity_points
        
        fav_count = favorites_counts.get(school_id, 0)
        popularity_score = min(100, (fav_count / 50) * 100) if fav_count > 0 else 0
        recommend_score += weights["popularity"] * popularity_score

        recommendations.append({
            "id": school_id,
            "name": school.get("name"),
            "level": school.get("level"),
            "province": school.get("province"),
            "region": school.get("region"),
            "computer_rank": school.get("computer_rank"),
            "enrollment_24_school_total": school.get("enrollment_24_school_total", "未知"),
            "favorites_count": fav_count,
            "recommend_score": round(recommend_score, 2),
        })

    recommendations.sort(key=lambda x: x['recommend_score'], reverse=True)
    return recommendations

@app.route('/admin/')
@admin_required
def admin_dashboard():
    user_count = 0
    if os.path.exists(USERS_DIR):
        user_count = len([name for name in os.listdir(USERS_DIR) if name.endswith(".json")])
    announcement_count = len(load_json_data(ANNOUNCEMENTS_PATH, default_value=[]))
    # Load school data and count
    schools_data = load_json_data(SCHOOLS_DATA_PATH, default_value=[])
    school_count = len(schools_data)

    return render_template('admin/dashboard.html',
                           user_count=user_count,
                           announcement_count=announcement_count,
                           school_count=school_count) # Pass school_count to template

@app.route('/admin/users')
@admin_required
def admin_users():
    users_list = []
    if os.path.exists(USERS_DIR):
        for filename in os.listdir(USERS_DIR):
            if filename.endswith(".json"):
                username = filename[:-5]
                user_data = get_user_data(username)
                if user_data:
                    users_list.append({
                        'username': username,
                        'is_admin': user_data.get('is_admin', False)
                    })
    users_list.sort(key=lambda u: u['username'])
    return render_template('admin/users.html', users=users_list)

@app.route('/admin/user/create', methods=['POST'])
@admin_required
def admin_create_user():
    admin_username = session.get('username')
    username = request.form.get('username')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin') == 'true'

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
        "password": password, # 直接存储明文密码
        "is_admin": is_admin,
        "profile": {
            "education_background": "",
            "major_area": "",
            "target_location": "",
            "target_level": "",
            "expected_score": None
        },
        "favorites": []
    }

    if save_user_data(username, new_user_data):
        flash(f'用户 "{username}" 创建成功！{" (管理员)" if is_admin else ""}', 'success')
        app.logger.info(f"管理员 '{admin_username}' 创建了新用户 '{username}' (管理员: {is_admin})")
    else:
        flash(f'创建用户 "{username}" 时出错。', 'error')
        app.logger.error(f"管理员 '{admin_username}' 创建用户 '{username}' 时保存文件失败。")

    return redirect(url_for('admin_users'))

@app.route('/admin/user/delete/<username>', methods=['POST'])
@admin_required
def delete_user(username):
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
        title = request.form.get('title')
        url = request.form.get('url', '#')

        if not title:
            flash('公告标题不能为空！', 'error')
        else:
            new_announcement = {"title": title, "url": url}
            announcements_file_path = ANNOUNCEMENTS_PATH # Use defined path
            current_announcements = load_json_data(announcements_file_path, default_value=[]) # Use robust loader
            current_announcements.append(new_announcement)
            
            lock_acquired = False
            try:
                with open(announcements_file_path, 'w', encoding='utf-8') as f:
                    # 尝试 portalocker
                    try:
                        # import portalocker # 已在顶部导入
                        portalocker.lock(f, portalocker.LOCK_EX)
                        lock_acquired = True
                    except ImportError:
                        if platform.system() != "Windows":
                            try:
                                import fcntl
                                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                                lock_acquired = True
                            except ImportError:
                                app.logger.warning(f"portalocker and fcntl not available for writing {announcements_file_path}. Proceeding without lock.")
                        else:
                             app.logger.warning(f"portalocker not available on Windows for writing {announcements_file_path}. fcntl not applicable. Proceeding without lock.")
                    except Exception as e_lock:
                        app.logger.error(f"Error acquiring exclusive lock for {announcements_file_path}: {e_lock}")

                    # 写入文件
                    try:
                        json.dump(current_announcements, f, ensure_ascii=False, indent=2)
                        f.flush()
                        os.fsync(f.fileno()) # 确保写入磁盘
                        flash('新公告已添加。', 'success')
                    except Exception as e_write:
                        flash(f'保存公告时出错: {e_write}', 'error')
                        app.logger.error(f"写入公告到 {announcements_file_path} 时出错: {e_write}", exc_info=True)
                    finally:
                        if lock_acquired:
                            try:
                                # import portalocker # 已在顶部导入
                                portalocker.unlock(f)
                            except (ImportError, NameError, AttributeError):
                                if platform.system() != "Windows":
                                    try:
                                        import fcntl
                                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                                    except (ImportError, NameError):
                                        pass
            except IOError as e:
                flash(f'打开或写入公告文件时出错: {e}', 'error')
                app.logger.error(f"IOError for {announcements_file_path} in admin_announcements: {e}", exc_info=True)
            except Exception as e_outer:
                flash(f'保存公告时发生未知错误: {e_outer}', 'error')
                app.logger.error(f"未知错误 for {announcements_file_path} in admin_announcements: {e_outer}", exc_info=True)

        return redirect(url_for('admin_announcements'))

    announcements = load_json_data(ANNOUNCEMENTS_PATH, default_value=[])
    return render_template('admin/announcements.html', announcements=announcements)

@app.route('/admin/announcements/reorder', methods=['POST'])
@admin_required
def admin_reorder_announcements():
    announcements_file_path = ANNOUNCEMENTS_PATH # Use defined path
    lock_acquired = False
    try:
        new_order_data = request.get_json()
        if not new_order_data or 'order' not in new_order_data:
            app.logger.error("无效的排序请求数据")
            return jsonify({'status': 'error', 'message': '无效的请求数据'}), 400

        ordered_titles = new_order_data['order']
        app.logger.debug(f"接收到的新公告顺序 (titles): {ordered_titles}")

        with open(announcements_file_path, 'r+', encoding='utf-8') as f:
            portalocker.lock(f, portalocker.LOCK_EX)
            try:
                content = f.read()
                if not content:
                    current_announcements = []
                else:
                    current_announcements = json.loads(content)
            except json.JSONDecodeError as e_decode:
                app.logger.error(f"在 admin_reorder_announcements 中解析公告文件时出错: {e_decode}")
                if lock_acquired: # Release lock if acquired before error
                    try: portalocker.unlock(f)
                    except: 
                        if platform.system() != "Windows":
                            try: import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                            except: pass
                return jsonify({'status': 'error', 'message': f'解析公告数据时出错: {e_decode}'}), 500

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

            app.logger.debug(f"即将写入公告文件的内容:\n{json.dumps(reordered_announcements, indent=2, ensure_ascii=False)}")
            
            f.seek(0)
            f.truncate()
            json.dump(reordered_announcements, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
            app.logger.debug(f"公告文件 {announcements_file_path} 保存后的内容:\n{json.dumps(reordered_announcements, indent=2, ensure_ascii=False)}")
            
            if lock_acquired:
                try: 
                    # import portalocker # 已在顶部导入
                    portalocker.unlock(f)
                except (ImportError, NameError, AttributeError):
                    if platform.system() != "Windows":
                        try: 
                            import fcntl
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        except (ImportError, NameError):
                            pass
            return jsonify({'status': 'success', 'message': '公告顺序已更新'})

    except IOError as e_io:
        app.logger.error(f"读写或锁定公告文件时发生IO错误: {e_io}", exc_info=True)
        return jsonify({'status': 'error', 'message': '文件操作失败'}), 500
    except json.JSONDecodeError as e_json: # For request.get_json()
        app.logger.error(f"解析请求数据时出错: {e_json}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'请求数据格式错误: {e_json}'}), 400
    except Exception as e:
        app.logger.error(f"处理公告排序请求时发生意外错误: {e}", exc_info=True)
        if lock_acquired: # Ensure lock release on unexpected error
            try: portalocker.unlock(f) # Assuming f is still in scope
            except: 
                if platform.system() != "Windows":
                    try: import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except: pass
        return jsonify({'status': 'error', 'message': f'处理请求时发生内部错误: {e}'}), 500

@app.route('/admin/profile', methods=['GET', 'POST'])
@admin_required
def admin_profile():
    username = session['username']
    if request.method == 'POST':
        current_password = request.form.get('current_password')
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

        # if current_password and not check_password_hash(user_data.get('password_hash', ''), current_password): # 修改为明文比较
        if current_password and user_data.get('password') != current_password:
            flash('当前密码错误！', 'error')
            return redirect(url_for('admin_profile'))

        # user_data['password_hash'] = generate_password_hash(new_password) # 修改为明文存储
        user_data['password'] = new_password # 直接存储明文新密码
        if save_user_data(username, user_data):
            flash('密码修改成功！', 'success')
            app.logger.info(f"管理员 '{username}' 修改了自己的密码。")
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

    current_status = user_data.get('is_admin', False)
    user_data['is_admin'] = not current_status

    if save_user_data(username, user_data):
        new_status = "管理员" if not current_status else "普通用户"
        flash(f'已将用户 "{username}" 设置为 {new_status}。', 'success')
        app.logger.info(f"管理员 '{admin_username}' 将用户 '{username}' 设置为 {new_status}。")
    else:
        flash(f'修改用户 "{username}" 管理员状态时出错。', 'error')
        app.logger.error(f"管理员 '{admin_username}' 修改用户 '{username}' 管理员状态时保存失败。")

    return redirect(url_for('admin_users'))

@app.route('/admin/schools')
@admin_required
def admin_schools():
    schools_data_list_full = load_json_data(SCHOOLS_DATA_PATH)
    if schools_data_list_full is None:
        flash('无法加载学校数据文件！', 'danger')
        schools_data_list_full = []

    search_query = request.args.get('q', '').strip()
    
    filtered_schools = schools_data_list_full
    if search_query:
        query_lower = search_query.lower()
        filtered_schools = [
            school for school in schools_data_list_full 
            if (school.get('name') and isinstance(school.get('name'), str) and query_lower in school.get('name').lower()) or \
               (school.get('id') and query_lower in str(school.get('id')).lower()) or
               (school.get('province') and isinstance(school.get('province'), str) and query_lower in school.get('province').lower()) or \
               (school.get('computer_rank') and isinstance(school.get('computer_rank'), str) and query_lower in school.get('computer_rank').lower())
        ]

    total_schools = len(filtered_schools)
    page = request.args.get('page', 1, type=int)
    per_page = 20 # 改为和院校库一致的每页20条，方便对比
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated_schools = filtered_schools[start:end]
    
    total_pages = ceil(total_schools / per_page) if total_schools > 0 else 1

    # 为每个学校计算院系和专业数量
    for school_item in paginated_schools: # 使用 school_item 避免与外层 school 变量冲突 (如果存在)
        departments = school_item.get('departments', [])
        school_item['department_count'] = len(departments)
        school_item['major_count'] = sum(len(dept.get('majors', [])) for dept in departments)

    return render_template('admin/schools.html',
                           schools=paginated_schools,
                           page=page,
                           total_pages=total_pages,
                           total_schools=total_schools,
                           search_query=search_query)

@app.route('/admin/schools/trigger_crawler', methods=['POST'])
@admin_required
def trigger_crawler():
    admin_username = session.get('username')
    app.logger.info(f"管理员 '{admin_username}' 触发了爬虫任务...")
    try:
        run_scraper() 
        flash('爬虫任务已尝试运行完成。请检查控制台输出或日志了解详情。', 'success')
        app.logger.info(f"爬虫任务由 '{admin_username}' 触发，已尝试运行。")
    except Exception as e:
        flash(f'运行爬虫时发生错误: {e}', 'error')
        app.logger.error(f"管理员 '{admin_username}' 触发爬虫时出错: {e}", exc_info=True)

    return redirect(url_for('admin_schools'))

@app.route('/admin/edit_school/<school_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_school(school_id):
    schools_data_current = load_json_data(SCHOOLS_DATA_PATH)
    if not schools_data_current:
        flash('无法加载学校数据文件！', 'danger')
        return redirect(url_for('admin_schools'))

    school_to_edit = next((s for s in schools_data_current if s.get('id') == school_id), None)
    
    if not school_to_edit:
        flash(f'未找到该院校。 ({school_id})', 'danger')
        return redirect(url_for('admin_schools'))

    # 使用 school_to_edit 初始化 form 对象 (避免直接用 data= 覆盖)
    form = SchoolEditForm()

    if form.validate_on_submit(): # POST 请求
        try:
            school_index = -1
            for i, school_iter in enumerate(schools_data_current):
                if school_iter.get('id') == school_id:
                    school_index = i
                    break
            
            if school_index == -1:
                flash('保存时未能找到学校索引，更新失败。', 'danger')
                # 在POST失败时，也需要传递 departments_json_str 以便重新渲染模板
                departments_json_str_for_template = json.dumps(school_to_edit.get('departments', []), ensure_ascii=False, indent=2)
                return render_template('admin/edit_school.html', form=form, school=school_to_edit, departments_json_str=departments_json_str_for_template)

            # 手动更新表单中的字段到 schools_data_current[school_index]
            target_school_in_list = schools_data_current[school_index]
            target_school_in_list['name'] = form.name.data
            target_school_in_list['level'] = form.level.data
            target_school_in_list['province'] = form.province.data
            target_school_in_list['computer_rank'] = form.computer_rank.data
            target_school_in_list['intro'] = form.intro.data
            target_school_in_list['enrollment_24_school_total'] = form.enrollment_24_school_total.data
            # 注意：'region' 是只读的，不应在此更新。
            # 注意：'id' 也不应在此更改。

            # 处理 departments JSON
            departments_json_input = request.form.get('departments_json_str')
            json_updated = False # 标记 JSON 是否被尝试更新
            if departments_json_input is not None: # 检查字段是否存在
                json_updated = True
                try:
                    original_departments_data = target_school_in_list.get('departments', [])
                    new_departments_data = json.loads(departments_json_input)
                    if isinstance(new_departments_data, list):
                        target_school_in_list['departments'] = new_departments_data
                        # 只有当 JSON 真的改变时才 flash info
                        if json.dumps(original_departments_data, sort_keys=True) != json.dumps(new_departments_data, sort_keys=True):
                             flash('院系专业信息 (通过JSON) 已更新。请注意检查其内部数据准确性。', 'info')
                    else:
                        flash('JSON 编辑器中的院系数据格式不正确（应为列表），未更新院系信息。', 'warning')
                        # 如果 JSON 格式错误，保留原来的数据
                        target_school_in_list['departments'] = original_departments_data 
                except json.JSONDecodeError:
                    flash('JSON 编辑器中的院系数据格式无效，未更新院系信息。请检查 JSON 语法。', 'danger')
                    # 如果 JSON 格式错误，保留原来的数据
                    target_school_in_list['departments'] = original_departments_data 
            
            if save_schools_data(schools_data_current):
                flash('院校信息更新成功!' + (' (院系JSON未更改或未提交)' if not json_updated else ''), 'success')
            else:
                 flash('院校信息已在内存中更新，但写入文件失败！', 'danger')

            return redirect(url_for('admin_schools'))
        except Exception as e:
             app.logger.error(f"更新学校 {school_id} 时出错: {e}", exc_info=True)
             flash(f'更新院校信息时发生内部错误: {e}', 'danger')
    
    # GET 请求
    # 准备在模板中显示的 departments JSON 字符串
    departments_json_str_for_template = json.dumps(school_to_edit.get('departments', []), ensure_ascii=False, indent=2)
    
    # 在GET请求时，用 school_to_edit 的数据填充表单
    form.process(obj=type('SchoolObject', (object,), school_to_edit)()) # 使用 process 填充

    return render_template('admin/edit_school.html', form=form, school=school_to_edit, departments_json_str=departments_json_str_for_template)

@app.route('/admin/edit-exam-ratios', methods=['GET'])
@admin_required
def admin_edit_exam_ratios():
    exam_ratios_data = load_json_data(EXAM_TYPE_RATIOS_PATH, default_value=[])
    return render_template('admin/edit_exam_ratios.html', exam_ratios_data=exam_ratios_data)

@app.route('/admin/save-exam-ratios', methods=['POST'])
@admin_required
def admin_save_exam_ratios():
    lock_acquired = False
    try:
        ratios_form = request.form.to_dict(flat=False)
        
        updated_ratios = []
        
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
                i += 1
            else:
                break

        if not updated_ratios:
            flash('没有提交有效的比例数据。', 'warning')
            return redirect(url_for('admin_edit_exam_ratios'))

        with open(EXAM_TYPE_RATIOS_PATH, 'w', encoding='utf-8') as f:
            # 尝试 portalocker
            try:
                # import portalocker # 已在顶部导入
                portalocker.lock(f, portalocker.LOCK_EX)
                lock_acquired = True
            except ImportError:
                if platform.system() != "Windows":
                    try:
                        import fcntl
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        lock_acquired = True
                    except ImportError:
                        app.logger.warning(f"portalocker and fcntl not available for saving exam ratios. Proceeding without lock.")
                else:
                    app.logger.warning(f"portalocker not available on Windows for saving exam ratios. fcntl not applicable. Proceeding without lock.")
            except Exception as e_lock:
                 app.logger.error(f"Error acquiring lock for exam ratios: {e_lock}")
            
            # 写入文件
            try:
                json.dump(updated_ratios, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
                flash('考试类型比例已成功更新。', 'success')
            except Exception as e_write:
                app.logger.error(f"保存考试类型比例时写入文件出错: {e_write}", exc_info=True)
                flash(f'保存考试类型比例时写入文件发生错误: {e_write}', 'danger')
            finally:
                if lock_acquired:
                    try:
                        # import portalocker # 已在顶部导入
                        portalocker.unlock(f)
                    except (ImportError, NameError, AttributeError):
                        if platform.system() != "Windows":
                            try:
                                import fcntl
                                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                            except (ImportError, NameError):
                                pass
    except Exception as e:
        app.logger.error(f"保存考试类型比例时发生主错误: {e}", exc_info=True)
        flash(f'保存考试类型比例时发生错误: {e}', 'danger')
    return redirect(url_for('admin_edit_exam_ratios'))

@app.route('/admin/edit-national-lines', methods=['GET'])
@admin_required
def admin_edit_national_lines():
    national_lines_data = load_json_data(NATIONAL_LINES_PATH)
    fixed_years = ['2023', '2024', '2025'] # Define fixed years

    # Ensure all expected categories for the form are present and structured for fixed years.
    expected_categories = [
        'computer_science_total', 'politics', 
        'english_one', 'english_two', 'math_one', 'math_two'
    ]
    areas_to_edit = ['A区', 'B区']
    
    processed_data_for_template = {}

    for cat_key in expected_categories:
        original_category_data = national_lines_data.get(cat_key, {})
        original_years = original_category_data.get('years', [])
        original_scores = original_category_data.get('scores', {})
        
        # Create a mapping from year to scores for faster lookup
        original_scores_map_a = {}
        original_scores_map_b = {}
        if 'A区' in original_scores and len(original_years) == len(original_scores['A区']):
             original_scores_map_a = dict(zip(original_years, original_scores['A区']))
        if 'B区' in original_scores and len(original_years) == len(original_scores['B区']):
             original_scores_map_b = dict(zip(original_years, original_scores['B区']))

        # Build the structure for the template using fixed years
        template_scores = {'A区': [], 'B区': []}
        for year in fixed_years:
            template_scores['A区'].append(original_scores_map_a.get(year)) # Get score for fixed year, None if not found
            template_scores['B区'].append(original_scores_map_b.get(year)) # Get score for fixed year, None if not found

        processed_data_for_template[cat_key] = {
            'years': fixed_years, # Always pass fixed years to template
            'scores': template_scores
        }

    return render_template('admin/edit_national_lines.html', national_lines_data=processed_data_for_template)

@app.route('/admin/save-national-lines', methods=['POST'])
@admin_required
def admin_save_national_lines():
    if request.method == 'POST':
        try:
            new_national_lines_data = {}
            fixed_years = ["2023", "2024", "2025"] # Use fixed years

            categories_config = {
                'computer_science_total': {'name_cn': '计算机总分', 'areas': ['A区', 'B区']},
                'politics': {'name_cn': '政治', 'areas': ['A区', 'B区']},
                'english_one': {'name_cn': '英语一', 'areas': ['A区', 'B区']},
                'english_two': {'name_cn': '英语二', 'areas': ['A区', 'B区']},
                'math_one': {'name_cn': '数学一', 'areas': ['A区', 'B区']},
                'math_two': {'name_cn': '数学二', 'areas': ['A区', 'B区']},
            }

            for category_key, config in categories_config.items():
                # Years are now fixed, no need to read from form
                category_data = {'years': fixed_years, 'scores': {}}
                all_scores_valid_for_category = True # Flag to track if any score was entered for the category

                for area_name in config['areas']: 
                    scores_for_area = []
                    area_has_scores = False # Flag for this specific area
                    for year in fixed_years:
                        # Read score using the new name format: category_key_scores_AreaKey_Year
                        score_form_name = f'{category_key}_scores_{area_name}_{year}'
                        score_str = request.form.get(score_form_name, '').strip()
                        
                        if score_str:
                            try:
                                scores_for_area.append(float(score_str))
                                area_has_scores = True # Mark that this area received at least one score
                            except ValueError:
                                scores_for_area.append(None) 
                                app.logger.warning(f"Invalid score value '{score_str}' for {score_form_name}. Storing as None.")
                        else:
                            scores_for_area.append(None) # Store empty strings as None
                    
                    category_data['scores'][area_name] = scores_for_area
                    if area_has_scores:
                         all_scores_valid_for_category = True # If any area has scores, keep the category
                
                # Only add the category to the final data if it had any valid scores entered
                # This prevents saving empty categories if the user clears all fields
                # However, the requirement might be to always save the structure for fixed years?
                # Let's adjust: always save the structure for the fixed years, even if scores are all None.
                new_national_lines_data[category_key] = category_data
            
            # Save the new data (potentially overwriting existing file)
            # Load existing data first IF we want to preserve other keys not managed by this form?
            # Current logic replaces the whole file content with only the edited categories.
            # This seems correct based on the intent to manage these specific lines.
            
            os.makedirs(os.path.dirname(NATIONAL_LINES_PATH), exist_ok=True)
            try:
                with open(NATIONAL_LINES_PATH, 'w', encoding='utf-8') as f:
                    portalocker.lock(f, portalocker.LOCK_EX)
                    try:
                        # Load old data to merge potentially unmanaged keys (e.g., 'total', 'others')
                        # Or decide to ONLY save the managed keys.
                        # Let's stick to saving only the managed keys for simplicity and clarity.
                        # To preserve other keys: 
                        # old_data = load_json_data(NATIONAL_LINES_PATH) 
                        # old_data.update(new_national_lines_data) # Merge changes
                        # json.dump(old_data, f, ensure_ascii=False, indent=2)
                        
                        # Simpler: Overwrite with only the edited/fixed-year data
                        json.dump(new_national_lines_data, f, ensure_ascii=False, indent=2)
                        f.flush(); os.fsync(f.fileno())
                    finally:
                        portalocker.unlock(f)
                flash('国家线数据已成功更新 (固定年份: 2023-2025)。', 'success')
            except Exception as e_save_lock: 
                app.logger.error(f"保存国家线数据时在锁定或写入阶段出错: {e_save_lock}", exc_info=True)
                flash(f'保存国家线数据时发生内部错误: {str(e_save_lock)}', 'danger')

        except Exception as e_main: 
            app.logger.error(f"保存国家线数据时发生主处理错误: {e_main}", exc_info=True)
            flash(f'保存国家线数据时发生严重错误: {str(e_main)}', 'danger')
        
        return redirect(url_for('admin_edit_national_lines'))

    # If not POST, redirect back
    return redirect(url_for('admin_edit_national_lines'))

@app.route('/admin/announcements/update', methods=['POST'])
@admin_required
def admin_update_announcement():
    lock_acquired = False
    try:
        data = request.get_json()
        original_title = data.get('original_title')
        new_title = data.get('new_title')
        new_url = data.get('new_url')

        if not original_title or not new_title:
            return jsonify({'status': 'error', 'message': '缺少必要的公告信息。'}), 400

        announcements_file_path = ANNOUNCEMENTS_PATH # Use defined path
        updated = False

        with open(announcements_file_path, 'r+', encoding='utf-8') as f:
            # 尝试 portalocker
            try:
                # import portalocker # 已在顶部导入
                portalocker.lock(f, portalocker.LOCK_EX)
                lock_acquired = True
            except ImportError:
                if platform.system() != "Windows":
                    try:
                        import fcntl
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        lock_acquired = True
                    except ImportError:
                        app.logger.warning(f"portalocker and fcntl not available for updating announcement. Proceeding without lock.")
                else:
                    app.logger.warning(f"portalocker not available on Windows for updating announcement. fcntl not applicable. Proceeding without lock.")
            except Exception as e_lock:
                app.logger.error(f"Error acquiring lock for updating announcement: {e_lock}")

            # 文件操作
            try:
                content = f.read()
                if not content:
                    announcements = []
                else:
                    announcements = json.loads(content)
            except json.JSONDecodeError as e_decode:
                app.logger.error(f"在 admin_update_announcement 中解析公告文件时出错: {e_decode}")
                if lock_acquired: # Release lock if acquired before error
                    try: portalocker.unlock(f)
                    except: 
                        if platform.system() != "Windows":
                            try: import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                            except: pass
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
                f.flush(); os.fsync(f.fileno())
                app.logger.info(f"公告 '{original_title}' 已更新为 '{new_title}'")
                if lock_acquired:
                    try: portalocker.unlock(f) 
                    except (ImportError, NameError, AttributeError):
                        if platform.system() != "Windows":
                            try: import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                            except (ImportError, NameError): pass
                return jsonify({'status': 'success', 'message': '公告已成功更新。'})
            else:
                if lock_acquired: # Not found, but release lock
                    try: portalocker.unlock(f)
                    except (ImportError, NameError, AttributeError):
                         if platform.system() != "Windows":
                            try: import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                            except (ImportError, NameError): pass
                return jsonify({'status': 'error', 'message': '未找到要更新的公告。'}), 404
        
    except IOError as e_io:
        app.logger.error(f"读写或锁定公告文件时发生IO错误 (update): {e_io}", exc_info=True)
        return jsonify({'status': 'error', 'message': '文件操作失败'}), 500
    except json.JSONDecodeError as e_json: # for request.get_json()
        app.logger.error(f"解析更新公告的请求数据时出错: {e_json}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'请求数据格式错误: {e_json}'}), 400
    except Exception as e:
        app.logger.error(f"更新公告时发生意外错误: {e}", exc_info=True)
        if lock_acquired: # Ensure lock release on unexpected error
            try: portalocker.unlock(f)
            except: 
                if platform.system() != "Windows":
                    try: import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except: pass
        return jsonify({'status': 'error', 'message': f'更新公告时发生内部错误: {e}'}), 500

@app.route('/admin/announcement/delete', methods=['POST'])
@admin_required
def delete_announcement():
    lock_acquired = False
    try:
        data = request.get_json()
        title_to_delete = data.get('title')

        if not title_to_delete:
            return jsonify({'status': 'error', 'message': '缺少要删除的公告标题。'}), 400

        announcements_file_path = ANNOUNCEMENTS_PATH # Use defined path
        deleted = False

        with open(announcements_file_path, 'r+', encoding='utf-8') as f:
            # 尝试 portalocker
            try:
                # import portalocker # 已在顶部导入
                portalocker.lock(f, portalocker.LOCK_EX)
                lock_acquired = True
            except ImportError:
                if platform.system() != "Windows":
                    try:
                        import fcntl
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        lock_acquired = True
                    except ImportError:
                        app.logger.warning(f"portalocker and fcntl not available for deleting announcement. Proceeding without lock.")
                else:
                    app.logger.warning(f"portalocker not available on Windows for deleting announcement. fcntl not applicable. Proceeding without lock.")
            except Exception as e_lock:
                app.logger.error(f"Error acquiring lock for deleting announcement: {e_lock}")

            # 文件操作
            try:
                content = f.read()
                if not content:
                    announcements = []
                else:
                    announcements = json.loads(content)
            except json.JSONDecodeError as e_decode:
                app.logger.error(f"在 delete_announcement 中解析公告文件时出错: {e_decode}")
                if lock_acquired: # Release lock if acquired before error
                    try: portalocker.unlock(f)
                    except: 
                        if platform.system() != "Windows":
                            try: import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                            except: pass
                return jsonify({'status': 'error', 'message': f'解析公告数据时出错: {e_decode}'}), 500

            original_count = len(announcements)
            announcements = [ann for ann in announcements if ann['title'] != title_to_delete]
            
            if len(announcements) < original_count:
                deleted = True
                f.seek(0)
                f.truncate()
                json.dump(announcements, f, ensure_ascii=False, indent=2)
                f.flush(); os.fsync(f.fileno())
                app.logger.info(f"公告 '{title_to_delete}' 已被删除。")
                if lock_acquired:
                    try: portalocker.unlock(f)
                    except (ImportError, NameError, AttributeError): 
                        if platform.system() != "Windows":
                            try: import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                            except(ImportError, NameError): pass
                return jsonify({'status': 'success', 'message': '公告已成功删除。'})
            else:
                app.logger.warning(f"尝试删除公告 '{title_to_delete}' 但未找到。")
                if lock_acquired: # Not found, but release lock
                     try: portalocker.unlock(f)
                     except (ImportError, NameError, AttributeError):
                        if platform.system() != "Windows":
                            try: import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                            except (ImportError, NameError): pass
                return jsonify({'status': 'error', 'message': '未找到要删除的公告。'}), 404

    except IOError as e_io:
        app.logger.error(f"读写或锁定公告文件时发生IO错误 (delete): {e_io}", exc_info=True)
        return jsonify({'status': 'error', 'message': '文件操作失败'}), 500
    except json.JSONDecodeError as e_json: # for request.get_json()
        app.logger.error(f"解析删除公告的请求数据时出错: {e_json}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'请求数据格式错误: {e_json}'}), 400
    except Exception as e:
        app.logger.error(f"删除公告时发生意外错误: {e}", exc_info=True)
        if lock_acquired: # Ensure lock release on unexpected error
            try: portalocker.unlock(f)
            except: 
                if platform.system() != "Windows":
                    try: import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except: pass
        return jsonify({'status': 'error', 'message': f'删除公告时发生内部错误: {e}'}), 500

# --- 新增：收藏数文件读写函数 ---
def load_favorites_count(): # Renamed from load_favorites_count to match usage
    """安全地加载收藏数 JSON 文件。"""
    if not os.path.exists(FAVORITES_COUNT_PATH):
        app.logger.warning(f"收藏数文件 {FAVORITES_COUNT_PATH} 不存在，返回空字典。")
        return {}
    
    lock_acquired = False
    try:
        with open(FAVORITES_COUNT_PATH, 'r', encoding='utf-8') as f:
            portalocker.lock(f, portalocker.LOCK_SH) # 共享锁
            try:
                counts = json.load(f)
            except json.JSONDecodeError as e_json_decode:
                 app.logger.error(f"解析收藏数文件 {FAVORITES_COUNT_PATH} 时出错: {e_json_decode}", exc_info=True)
                 counts = {} # Return empty on error
            finally:
                portalocker.unlock(f)
            return counts if isinstance(counts, dict) else {}
    except (IOError) as e: # Removed json.JSONDecodeError here as it's handled inside
        app.logger.error(f"加载收藏数文件 {FAVORITES_COUNT_PATH} 时发生IO错误: {e}", exc_info=True)
        return {} # 出错时返回空字典
    except Exception as e_main_fav: # Catch any other unexpected errors
        app.logger.error(f"加载收藏数文件 {FAVORITES_COUNT_PATH} 时发生未知错误: {e_main_fav}", exc_info=True)
        return {}

def save_favorites_count(counts_dict):
    """安全地保存收藏数 JSON 文件。"""
    try:
        os.makedirs(os.path.dirname(FAVORITES_COUNT_PATH), exist_ok=True)
        with open(FAVORITES_COUNT_PATH, 'w', encoding='utf-8') as f:
            portalocker.lock(f, portalocker.LOCK_EX)
            try:
                json.dump(counts_dict, f, ensure_ascii=False, indent=2)
                f.flush(); os.fsync(f.fileno())
            finally:
                portalocker.unlock(f)
            return True
    except Exception as e: # Catch general errors like IOError from open() if portalocker path fails before import error
        app.logger.error(f"保存收藏统计时发生错误: {e}", exc_info=True)
        return False

# --- 新增：编辑首页配置路由 ---
@app.route('/admin/edit-homepage', methods=['GET', 'POST'])
@admin_required
def admin_edit_homepage():
    current_config = load_homepage_config()
    form = HomepageConfigForm(data=current_config)

    if form.validate_on_submit():
        new_config = {
            "national_line_total_title": form.national_line_total_title.data,
            "national_line_politics_title": form.national_line_politics_title.data,
            "national_line_others_title": form.national_line_others_title.data,
            "exam_type_ratio_title": form.exam_type_ratio_title.data
        }
        if save_homepage_config(new_config):
            flash('首页配置已成功更新。', 'success')
        else:
            flash('保存首页配置时出错！', 'danger')
        return redirect(url_for('admin_edit_homepage')) # 重定向回当前页面

    return render_template('admin/edit_homepage.html', form=form)

# --- 新增API端点 ---
@app.route('/api/national-lines/computer-science-total')
def get_national_line_computer_science_total():
    lines_data = load_json_data(NATIONAL_LINES_PATH)
    cs_total_data = lines_data.get('computer_science_total')

    if not cs_total_data:
        app.logger.warning("API: /api/national-lines/computer-science-total - Computer Science total data not found in JSON.")
        return jsonify({"error": "Computer Science total data not found"}), 404

    years, scores, legend_keys_from_data = get_recent_n_years_data(cs_total_data, n=3)

    if years is None:
         app.logger.warning("API: /api/national-lines/computer-science-total - Insufficient data or format error from get_recent_n_years_data.")
         return jsonify({"error": "Insufficient data or data format error for Computer Science total"}), 404

    series_data = []
    legend_display = []
    area_map = {"A区": "A区计算机总分", "B区": "B区计算机总分"}
    
    for area_key, display_name in area_map.items():
        if area_key in scores:
            series_data.append({
                "name": display_name,
                "data": scores[area_key], 
                "type": "line",
                "smooth": True
            })
            legend_display.append(display_name)
    
    if not series_data and legend_keys_from_data:
        app.logger.info("API: /computer-science-total - A区/B区 not found in scores, using other keys from data.")
        for key in legend_keys_from_data:
            display_name = f"{key}计算机总分"
            series_data.append({
                "name": display_name,
                "data": scores.get(key, [None] * len(years)),
                "type": "line",
                "smooth": True
            })
            legend_display.append(display_name)
    
    if not series_data:
        app.logger.warning("API: /computer-science-total - No series data could be constructed.")

    # 计算 Y 轴范围
    y_axis_config = calculate_y_axis_range(series_data)

    echarts_data = {
        "years": years,
        "legend": legend_display,
        "series": series_data,
        "yAxis": y_axis_config # 使用计算出的范围
    }
    return jsonify(echarts_data)

@app.route('/api/national-lines/politics-recent')
def get_national_line_politics_recent():
    lines_data = load_json_data(NATIONAL_LINES_PATH)
    politics_data = lines_data.get('politics')

    if not politics_data:
        app.logger.warning("API: /politics-recent - Politics data not found in JSON.")
        return jsonify({"error": "Politics data not found"}), 404

    years, scores, legend_keys_from_data = get_recent_n_years_data(politics_data, n=3)

    if years is None:
        app.logger.warning("API: /politics-recent - Insufficient data or format error from get_recent_n_years_data for Politics.")
        return jsonify({"error": "Insufficient data or data format error for Politics"}), 404

    series_data = []
    legend_display = []
    area_map = {"A区": "A区政治", "B区": "B区政治"}

    for area_key, display_name in area_map.items():
        if area_key in scores:
            series_data.append({
                "name": display_name,
                "data": scores[area_key],
                "type": "bar",
                "barMaxWidth": 30
            })
            legend_display.append(display_name)

    if not series_data and legend_keys_from_data: # Fallback
        app.logger.info("API: /politics-recent - A区/B区 not found in scores, using other keys from data for Politics.")
        for key in legend_keys_from_data:
            display_name = f"{key}政治"
            series_data.append({
                "name": display_name,
                "data": scores.get(key, [None] * len(years)),
                "type": "bar",
                "barMaxWidth": 30
            })
            legend_display.append(display_name)
    
    if not series_data:
        app.logger.warning("API: /politics-recent - No series data could be constructed for Politics.")

    # 计算 Y 轴范围
    y_axis_config = calculate_y_axis_range(series_data)

    echarts_data = {
        "years": years,
        "legend": legend_display,
        "series": series_data,
        "yAxis": y_axis_config # 使用计算出的范围
    }
    return jsonify(echarts_data)

@app.route('/api/national-lines/english-math-subjects')
def get_national_line_english_math_subjects():
    lines_data = load_json_data(NATIONAL_LINES_PATH)
    
    subjects_config = {
        "english_one": "英语一",
        "english_two": "英语二",
        "math_one": "数学一",
        "math_two": "数学二"
    }
    
    all_years_set = set()
    subject_data_map = {} 

    for key, display_name_prefix in subjects_config.items():
        data = lines_data.get(key)
        if data and isinstance(data.get('years'), list) and isinstance(data.get('scores'), dict):
            subject_data_map[key] = data
            all_years_set.update(data['years']) 
        else:
            app.logger.warning(f"API: /english-math-subjects - Data for subject key '{key}' is missing, incomplete, or malformed.")
    
    if not subject_data_map:
        app.logger.warning("API: /english-math-subjects - No valid English or Math subject data found.")
        return jsonify({"error": "English or Math subject data not found or is malformed"}), 404

    if not all_years_set:
        app.logger.warning("API: /english-math-subjects - No years found across any English/Math subjects.")
        return jsonify({"error": "No year data available for English/Math subjects"}), 404
        
    final_years = sorted(list(all_years_set))

    series_data = []
    legend_data = []

    for key, display_name_prefix in subjects_config.items():
        subject_entry = subject_data_map.get(key)
        if subject_entry:
            scores_a_区_original = subject_entry.get('scores', {}).get('A区')
            subject_years_original = subject_entry.get('years')

            if isinstance(scores_a_区_original, list) and isinstance(subject_years_original, list) and len(scores_a_区_original) == len(subject_years_original):
                aligned_scores = [None] * len(final_years)
                temp_score_map = dict(zip(subject_years_original, scores_a_区_original))
                
                for i, year_val in enumerate(final_years):
                    aligned_scores[i] = temp_score_map.get(year_val)
                
                series_name = f"{display_name_prefix} (A区)"
                series_data.append({
                    "name": series_name,
                    "data": aligned_scores,
                    "type": "line",
                    "smooth": True
                })
                legend_data.append(series_name)
            else:
                app.logger.warning(f"API: /english-math-subjects - Scores for '{key}' (A区) are missing, malformed, or year mismatch. Skipping this series.")

    if not series_data:
         app.logger.warning("API: /english-math-subjects - No series data could be generated after processing all subjects.")
         return jsonify({"error": "No series data could be generated for English/Math subjects"}), 404

    # 计算 Y 轴范围
    y_axis_config = calculate_y_axis_range(series_data)

    echarts_data = {
        "years": final_years,
        "legend": legend_data,
        "series": series_data,
        "yAxis": y_axis_config # 使用计算出的范围
    }
    return jsonify(echarts_data)

# --- 辅助函数：获取最近N年的数据 ---
# MOVED HERE - Correct Placement
def get_recent_n_years_data(data_category, n=3):
    if not data_category or 'years' not in data_category or 'scores' not in data_category:
        app.logger.debug(f"get_recent_n_years_data: Initial data check failed. Category: {data_category}")
        return None, None, None

    years = data_category['years']
    scores_dict = data_category['scores']

    if not isinstance(years, list) or not isinstance(scores_dict, dict):
        app.logger.warning(f"get_recent_n_years_data: Invalid data types. Years is {type(years)}, scores_dict is {type(scores_dict)}")
        return None, None, None
        
    if len(years) == 0: 
        app.logger.debug("get_recent_n_years_data: Empty years list.")
        return [], {}, [] # Return empty structures if no years

    if len(years) <= n:
        final_years = years
        final_scores = {}
        for key, score_list in scores_dict.items():
            if isinstance(score_list, list) and len(score_list) == len(final_years):
                final_scores[key] = score_list
            else:
                app.logger.warning(f"get_recent_n_years_data: Score list length mismatch for '{key}' (len {len(score_list) if isinstance(score_list, list) else 'N/A'}) vs years (len {len(final_years)}) when len(years) <= n. Padding with Nones.")
                final_scores[key] = [None] * len(final_years)
        return final_years, final_scores, list(final_scores.keys())

    recent_years = years[-n:]
    recent_scores = {}
    
    for key, score_list in scores_dict.items():
        if isinstance(score_list, list) and len(score_list) == len(years): 
            recent_scores[key] = score_list[-n:]
        else:
            app.logger.warning(f"get_recent_n_years_data: Score list '{key}' (len {len(score_list) if isinstance(score_list, list) else 'N/A'}) full length mismatch vs total years (len {len(years)}). Padding recent_scores with Nones.")
            recent_scores[key] = [None] * n 
            
    return recent_years, recent_scores, list(scores_dict.keys())

# --- 辅助函数：计算 ECharts Y 轴范围（带缓冲）---
def calculate_y_axis_range(series_data, min_buffer_value=5, buffer_percentage=0.1):
    """根据 series 数据计算 Y 轴的 min 和 max，并添加缓冲。增加默认最小缓冲值。"""
    all_values = []
    if not series_data:
        return {'min': 0, 'max': 100} # 默认范围

    for series in series_data:
        if isinstance(series.get('data'), list):
            for value in series['data']:
                if value is not None and isinstance(value, (int, float)):
                    all_values.append(value)

    if not all_values:
        return {'min': 0, 'max': 100} # 没有有效数据点

    data_min = min(all_values)
    data_max = max(all_values)
    data_range = data_max - data_min

    if data_range == 0: # 如果所有值都相同
        buffer = max(min_buffer_value, abs(data_min * buffer_percentage)) # 基于值的百分比或最小缓冲
    else:
        buffer = max(data_range * buffer_percentage, min_buffer_value) # 使用范围百分比或最小缓冲中较大的一个
        
    # 计算最终范围，确保 min 不小于 0 （对于分数线等场景）
    y_min = max(0, data_min - buffer)
    y_max = data_max + buffer

    # 可选：进行取整或其他美化处理，这里暂时不加
    # y_min = math.floor(y_min)
    # y_max = math.ceil(y_max)
    
    # 对于非常小的负数 y_min (如果允许负数且 data_min 接近0)，可能需要特殊处理
    # 但这里我们用了 max(0, ...)，所以 y_min 不会是负数

    return {'min': y_min, 'max': y_max}

# --- 启动应用 ---
if __name__ == '__main__':
    # --- 日志配置 ---
    log_dir = os.path.join(BASE_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, 'app.log')

    log_format = '%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
    formatter = logging.Formatter(log_format)

    # Rotating File Handler
    # Rotate logs at 5MB, keep 5 backup logs
    file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO) # Log INFO and above to file

    # Console Handler (for development/debugging)
    # console_handler = logging.StreamHandler()
    # console_handler.setFormatter(formatter)
    # console_handler.setLevel(logging.DEBUG) # Log DEBUG and above to console

    # 获取 Flask 的默认 logger (app.logger) 并添加 handler
    # app.logger is already a logger instance. We can add handlers to it.
    # Or, get the root logger if preferred: logging.getLogger()
    
    # Clear existing handlers from app.logger if any were added by Flask/extensions by default
    # to avoid duplicate logs if this script is re-run or in certain environments.
    # However, this might also remove Flask's default handler. Be cautious.
    # For this setup, we're adding our custom handlers.
    
    # app.logger.handlers.clear() # Optional: if you want only your handlers

    # Add handlers to Flask's app.logger
    app.logger.addHandler(file_handler)
    # app.logger.addHandler(console_handler) # Uncomment for console output
    
    # Set the level for app.logger itself.
    # If set to DEBUG, and handlers are set to INFO, handlers will still only log INFO.
    # If set to WARNING, handlers set to INFO will only see WARNING and above.
    app.logger.setLevel(logging.INFO) # Set root level for app.logger

    # Also configure the root logger if other libraries are to use this setup (optional)
    # logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
    
    app.logger.info("Flask应用启动，日志已配置。")
    # 移除旧的 fcntl 引用，因为它已被 portalocker 替代或作为后备方案
    # del fcntl 

    app.run(debug=True, host='127.0.0.1', port=5001)