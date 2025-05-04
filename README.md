# 计算机考研院校可视化推荐系统 - 开发文档

## 1. 项目概述

本项目旨在为计算机专业考研学生提供一个集院校信息查询、可视化分析和个性化推荐于一体的 Web 应用。系统核心功能包括：

* **可视化大面板:** 动态展示全国计算机考研相关的宏观数据，如国家线趋势、院校分布、考试类型比例等。前端使用 ECharts 绘制图表。
* **院校库查询:** 允许用户根据地区、院校层次、计算机学科评估等级、院校名称等多维度筛选院校，并按收藏热度排序。
* **院校详情:** 展示院校的详细信息，包括简介、院系专业、招生人数、复试线（暂无图表）、参考书目等。
* **个性化推荐:** 基于用户的个人情况（预期分数、目标地区、院校偏好等）和加权评分算法，推荐合适的院校（取 Top 20）。
* **用户管理 (前后台):**
  * 支持用户注册、登录、登出。
  * 用户可查看和编辑个人资料（学历、专业、目标等）。
  * 用户可收藏/取消收藏感兴趣的院校。
  * 管理员可在后台查看用户列表、创建新用户（可设为管理员）、删除用户、查看用户详情、切换用户管理员状态。
* **后台管理:** 提供管理员界面，用于管理用户、公告信息。
  * **管理员认证**: 通过在用户 JSON 文件中手动设置 `is_admin: true` 实现。
  * **公告管理**: 管理员可添加、删除公告信息。
  * **管理员设置**: 管理员可修改自己的登录密码。
* **系统日志**: 将关键操作记录到 `logs/app.log` 文件。

本项目的一个关键特点是**不依赖传统数据库**，所有数据（院校信息、国家线、公告、用户信息、收藏夹）均以 **JSON 文件** 形式存储在服务器的文件系统中 (`data/` 目录)。后端逻辑使用 Python 和 Flask 框架实现。

**重要提示:** 基于文件的用户数据存储和密码哈希（`werkzeug.security`）相比明文有改进，但**仍不适合生产环境**，存在安全风险和性能瓶颈。

## 2. 技术栈

* **后端:**
  * **框架:** Flask
  * **数据处理:** Pandas (用于初始数据处理), JSON (用于运行时数据读写)
  * **密码处理:** Werkzeug
  * **日志:** Python `logging` 模块
  * **数据存储:** JSON 文件
  * **Web 服务器 (开发):** Flask 内建服务器
* **前端:**
  * **基础:** HTML, CSS, JavaScript
  * **可视化库:** ECharts
  * **UI 辅助:** Bootstrap 5 (部分页面), Font Awesome (图标)
* **开发工具:**
  * Python 3.x
  * pip (包管理)
  * Git (版本控制)

## 3. 项目结构

```text
computer_recommendation_system/
├── app.py             # Flask 后端主应用文件
├── data/              # 存放所有数据文件的文件夹
│   ├── schools.json     # 全国院校数据
│   ├── national_lines.json # 国家线数据
│   ├── announcements.json # 公告通知数据
│   └── users/           # 存储用户信息的文件夹 (每个用户一个 JSON)
│       └── example_user.json
├── logs/              # 存放日志文件
│   └── app.log
├── static/            # 存放前端静态文件
│   ├── css/           # (style.css, navbar.css, forms.css)
│   └── js/            # (main.js)
├── templates/         # 存放 HTML 模板文件
│   ├── admin/           # 管理后台模板
│   │   ├── base_admin.html
│   │   ├── dashboard.html
│   │   ├── users.html
│   │   ├── user_detail.html
│   │   ├── announcements.html
│   │   └── admin_profile.html
│   ├── base.html        # 前台基础模板
│   ├── index.html       # 可视化大面板/首页
│   ├── school_list.html # 院校库查询结果页
│   ├── school_detail.html # 院校详情页
│   ├── recommendation.html # 推荐结果页
│   ├── login.html
│   ├── register.html
│   └── profile.html     # 用户个人中心
├── utils/             # 存放工具函数 (如 data_processor.py)
├── requirements.txt   # Python 依赖库
├── README.md          # 项目说明和开发文档
└── 择校文档.xlsx    # 原始数据文件 (示例)
```

## 4. 数据结构

核心数据存储在 `data/` 目录下的 JSON 文件中。

### `schools.json`

(结构同之前定义，包含 `id`, `name`, `level`, `region`, `province`, `intro`, `computer_rank`, `self_vs_408`, `departments` [内含 `majors` {内含 `major_code`, `major_name`, `exam_subjects`, `reference_books`, `retrial_subjects`, `enrollment_24`, `tuition_duration`, `score_lines`, `admission_info_23`, `admission_info_24`}], `favorites_count` (此字段在运行时计算，不存储在文件))。

### `national_lines.json`

存储各科国家线数据。

```json
{
  "total": { "years": [...], "scores": {"A区": [...], "B区": [...]}},
  "politics": { "years": [...], "scores": {"A区": [...], "B区": [...]}},
  "others": { "years": [...], "scores": {"英语一 (A区)": [...], ...}}
}
```

### `announcements.json`

存储公告信息列表。

```json
[
  {"title": "公告标题", "url": "公告链接 (可选)"},
  ...
]
```

### `data/users/username.json`

存储单个用户的信息。

```json
{
  "username": "string",        // 用户名 (与文件名一致)
  "password_hash": "string",   // Werkzeug 生成的密码哈希
  "is_admin": boolean,       // 是否为管理员 (默认为 false)
  "profile": {               // 用户个人资料和偏好
    "education_background": "string",
    "major_area": "string",
    "target_location": "string", // 省份
    "target_level": "string",    // 985, 211, etc.
    "expected_score": number | null
  },
  "favorites": ["string", ...] // 收藏的学校 ID (通常是学校名称) 列表
}
```

## 5. 已实现功能

* **核心展示**: 可视化面板（各类图表、院校滚动列表）、院校库（查询、排序）、院校详情页。
* **用户系统**: 注册、登录、登出、个人资料查看与修改、院校收藏与取消收藏。
* **推荐系统**: 基于用户偏好和加权算法的 Top 20 院校推荐。
* **管理后台**: 管理员登录、仪表盘、用户管理（列表、创建、删除、详情、切换管理员）、公告管理（列表、添加、删除）、管理员密码修改。
* **日志记录**: 关键操作记录到文件。

## 6. 运行说明

1. **安装依赖**: 确保已安装 Python 3.x 和 pip。在项目根目录下运行：

    ```bash
    pip install -r requirements.txt
    ```

2. **准备数据**: 确保 `data/schools.json`, `data/national_lines.json`, `data/announcements.json` 文件存在且格式正确。
3. **设置管理员**: 首次运行时，需要先注册一个用户，然后**手动修改**对应的 `data/users/用户名.json` 文件，在顶层添加 `"is_admin": true,`。
4. **运行应用**: 在项目根目录下运行：

    ```bash
    python app.py
    ```

5. **访问应用**: 打开浏览器访问 `http://127.0.0.1:5000/`。
6. **访问后台**: 使用管理员账户登录后，访问 `http://127.0.0.1:5000/admin/`。

## 7. 待办与未来方向 (示例)

* **院校数据管理**: 实现后台更新/管理 `schools.json` 的功能（可能通过上传文件或集成爬虫）。
* **爬虫功能**: 实现 `utils/scraper.py` 用于爬取四川院校近三年数据或其他院校的最新信息。
* **分数线图表**: 在院校详情页为四川院校添加近三年复试线图表。
* **推荐算法优化**: 使用更精确的数据（如平均录取分）优化分数相似度计算。
* **分页**: 为院校库和推荐结果添加分页功能。
* **UI/UX 改进**: 优化页面布局和用户体验。
* **安全性增强**: 替换文件存储为数据库，使用更安全的认证机制。
