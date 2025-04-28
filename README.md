# 计算机考研院校推荐系统后端

这是一个基于 Django 和 Django REST Framework 构建的后端系统，旨在为计算机考研学生提供院校信息查询、可视化展示和个性化推荐功能。

## 主要功能

* **用户管理:** 注册、登录、个人信息（含考研意向）管理、修改密码、收藏院校。
* **院校信息:** 提供院校库查询（按地区、等级、计算机学科评估等级、名称等筛选）、院校详情（含院系、专业、初试科目、招生人数、复试线）、收藏功能。
* **数据可视化:** 提供首页大屏所需的数据接口，包括：
  * 院校滚动列表
  * 近三年计算机考研总分国家线（A/B区）折线图
  * 近三年政治国家线（A/B区）柱状图
  * 近三年英语（一/二）、数学（一/二）国家线折线图
  * 计算机专业课自命题/统考比例饼状图
  * 最新公告通知
* **院校推荐:** 根据用户输入的目标分数、院校等级、计算机等级、目标地区，使用加权算法推荐合适的院校。
* **公告通知:** 后台可发布和管理考研相关公告信息。
* **数据爬虫:** 提供管理命令用于爬取特定地区（如四川）的院校数据（需自行实现具体解析逻辑）。
* **后台管理:** 基于 Django Admin，提供对用户、院校、专业、分数线、公告等的管理界面。

## 技术栈

* **后端框架:** Django, Django REST Framework
* **数据库:** MySQL
* **数据处理:** Pandas (用于未来可能的数据导入/处理)
* **爬虫库:** Requests, BeautifulSoup4
* **API 文档:** DRF自带文档 (访问 `/api/docs/`)

## 项目结构

```text
kaoyan_recommendation_system/
├── manage.py                     # Django 项目管理工具
├── config/                       # 主项目配置目录
│   ├── __init__.py
│   ├── settings.py             # 项目设置 (数据库, App注册, 中间件等)
│   ├── urls.py                 # 主 URL 路由配置
│   ├── wsgi.py                 # WSGI 应用入口
│   └── asgi.py                 # ASGI 应用入口
├── apps/                         # 功能 App 目录
│   ├── __init__.py
│   ├── users/                    # 用户管理 App
│   ├── schools/                  # 院校信息 App
│   ├── visualization/            # 可视化数据接口 App
│   ├── recommendation/           # 推荐算法 App
│   ├── announcements/            # 公告通知 App
│   └── scraper/                  # 数据爬虫 App
├── static/                       # 全局静态文件 (主要服务于Admin)
├── templates/                    # 全局 HTML 模板 (主要服务于Admin)
├── data/                         # 存放数据文件 (例如：你提供的 national_schools_data.xlsx)
├── media/                        # 存放用户上传的媒体文件 (例如：头像)
├── venv/                         # Python 虚拟环境 (不提交到 Git)
├── requirements.txt              # 项目依赖库列表
└── README.md                     # 项目说明文档
```

## 本地运行指南 (轻量化部署)

1. **环境准备:**
    * 安装 Python 3 (推荐 3.8+)。
    * 安装 MySQL 数据库并启动服务。
    * (可选，但推荐) 安装 Git。
    * (如果需要安装 `mysqlclient`) 根据你的操作系统安装 MySQL 开发库。

2. **克隆项目:**

    ```bash
    git clone <your-repository-url>
    cd kaoyan_recommendation_system
    ```

3. **创建并激活虚拟环境:**

    ```bash
    python3 -m venv .venv
    # macOS / Linux
    source .venv/bin/activate
    # Windows
    .venv\Scripts\activate
    ```

4. **安装依赖:**

    ```bash
    pip install -r requirements.txt
    ```

5. **数据库设置:**
    * 登录你的 MySQL 服务器。
    * 创建一个新的数据库 (例如 `kaoyan_recommendation`): `CREATE DATABASE kaoyan_recommendation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`
    * 打开 `config/settings.py` 文件，找到 `DATABASES` 配置部分。
    * **修改 `USER`, `PASSWORD`, `NAME` (如果需要), `HOST`, `PORT`** 以匹配你的本地 MySQL 设置。

6. **数据库迁移:**

    ```bash
    python3 manage.py makemigrations
    python3 manage.py migrate
    ```

7. **创建超级用户 (用于访问 Admin 后台):**

    ```bash
    python3 manage.py createsuperuser
    ```

    按照提示设置用户名、邮箱和密码。

8. **导入初始数据 (可选):**
    * 如果你有初始数据文件 (如 `data/national_schools_data.xlsx`)，你需要编写一个管理命令或脚本来读取文件并将其填充到数据库中。
    * 例如，创建一个 `apps/schools/management/commands/import_data.py` 命令。

9. **运行开发服务器:**

    ```bash
    python3 manage.py runserver
    ```

    服务器将在 `http://127.0.0.1:8000/` 启动。

10. **访问系统:**
    * **API 接口:** 可以在浏览器或 API 测试工具 (如 Postman) 中访问，例如 `http://127.0.0.1:8000/api/schools/schools/`。
    * **API 文档:** `http://127.0.0.1:8000/api/docs/`。
    * **Admin 后台:** `http://127.0.0.1:8000/admin/` (使用你创建的超级用户登录)。

## 注意事项

* **爬虫实现:** `apps/scraper/core/parser.py` 中的解析逻辑需要根据你想要爬取的目标网站的 HTML 结构进行具体实现。管理命令 `scrape_schools` 中的数据存储逻辑也需要相应调整。
* **推荐算法:** `apps/recommendation/services.py` 中的 `get_recommended_schools` 函数目前缺少获取学校平均录取分数的实际逻辑，需要根据你的数据源（`ScoreLine` 或 `Admission` 模型）进行实现。
* **前端交互:** 本项目仅提供后端 API。前端的可视化（包括中国地图交互）需要单独开发，并调用本项目提供的 API 获取数据。
* **生产环境:** `runserver` 只适用于开发和测试。对于正式部署，请考虑使用更健壮的 WSGI 服务器 (如 Gunicorn 或 uWSGI) 和反向代理 (如 Nginx)。 `.env` 文件和环境变量是管理生产环境配置的最佳实践。
