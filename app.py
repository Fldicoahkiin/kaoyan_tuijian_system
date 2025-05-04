from flask import Flask, jsonify, render_template, session, redirect, url_for, request, flash
import json
import os
# 导入 Werkzeug 用于密码哈希 (比明文安全)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# 设置一个密钥用于 session 加密，请在实际部署中替换为更安全的随机值
app.config['SECRET_KEY'] = 'dev_secret_key_please_change'

# 定义数据文件路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHOOLS_DATA_PATH = os.path.join(BASE_DIR, "data", "schools.json")
NATIONAL_LINES_PATH = os.path.join(BASE_DIR, "data", "national_lines.json")
ANNOUNCEMENTS_PATH = os.path.join(BASE_DIR, "data", "announcements.json")
USERS_DIR = os.path.join(BASE_DIR, "data", "users")

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
    # TODO: 实现院校库查询逻辑
    return render_template('school_list.html')

@app.route('/recommend')
def recommend():
    # TODO: 实现推荐逻辑
    return render_template('recommendation.html')

@app.route('/school/<school_id>')
def school_detail(school_id):
    # TODO: 实现学校详情页逻辑
    # Find school data by school_id (which might be the 'name' or a generated ID)
    school = next((s for s in schools_data if s.get('id') == school_id or s.get('name') == school_id), None)
    if school:
        # Create a dummy detail template or pass data
        # return render_template('school_detail.html', school=school)
        return f"<h1>学校详情页: {school.get('name')}</h1><p>内容待实现...</p>" # 临时返回
    else:
        flash('未找到指定的学校。', 'error')
        return redirect(url_for('index')) # 或者重定向到院校库

if __name__ == '__main__':
    app.run(debug=True) 