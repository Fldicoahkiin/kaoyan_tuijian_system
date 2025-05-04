# 计算机考研院校可视化推荐系统 - 开发文档

## 1. 项目概述

本项目旨在为计算机专业考研学生提供一个集院校信息查询、可视化分析和个性化推荐于一体的 Web 应用。系统核心功能包括：

* **可视化大面板:** 动态展示全国计算机考研相关的宏观数据，如国家线趋势、院校分布、考试类型比例等。
* **院校库查询:** 允许用户根据地区、院校层次、计算机学科评估等级等多维度筛选院校。
* **个性化推荐:** 基于用户的个人情况（预期分数、目标地区、院校偏好等）和预设算法，推荐合适的院校。
* **用户管理:** 支持用户注册登录，保存个人信息和收藏院校。
* **后台管理:** 提供管理员界面，用于管理用户、院校数据（支持爬虫导入）、公告信息等。

本项目的一个关键特点是**不依赖传统数据库**，所有数据将以文件形式（主要是 JSON）存储在服务器的文件系统中，后端逻辑使用 Python 实现。

## 2. 技术栈

* **后端:**
  * **框架:** Flask
  * **数据处理:** Pandas
  * **数据存储:** JSON 文件
  * **Web 服务器 (开发):** Flask 内建服务器
  * **Web 服务器 (生产):** Gunicorn / uWSGI (可选)
  * **爬虫 (可选):** Requests + BeautifulSoup4
* **前端:**
  * **基础:** HTML, CSS, JavaScript
  * **可视化库:** ECharts
* **开发工具:**
  * Python 3.x
  * pip (包管理)
  * Git (版本控制)

## 3. 项目结构

```text
computer_recommendation_system/
├── app.py             # Flask 后端主应用文件
├── data/              # 存放所有数据文件的文件夹
│   ├── schools.json     # 全国院校数据 (转换后)
│   ├── sichuan_schools_detail.json # 四川院校详细数据 (爬取后)
│   ├── national_lines.json # 国家线数据
│   ├── users/           # 存储用户信息的文件夹 (可选)
│   └── announcements.json # 公告通知数据
├── static/            # 存放前端静态文件 (CSS, JS, Images)
│   ├── css/
│   ├── js/
│   └── images/
├── templates/         # 存放 HTML 模板文件
│   ├── index.html       # 可视化大面板/首页
│   ├── school_list.html # 院校库查询结果页
│   ├── school_detail.html # 院校详情页
│   ├── recommendation.html # 推荐结果页
│   └── admin/           # 管理端页面 (可选)
├── utils/             # 存放工具函数、爬虫脚本等
│   ├── data_loader.py   # 加载/处理数据的函数
│   └── scraper.py       # 爬虫脚本 (可选)
├── requirements.txt   # Python 依赖库
└── README.md          # 项目说明和开发文档入口
```

(后续章节将详细介绍功能模块、数据结构、API 设计等)

## 4. 数据结构

核心数据将存储在 `data/` 目录下的 JSON 文件中。

### `schools.json`

此文件包含全国（基于提供的 Excel）或特定区域（如四川）的考研院校及其计算机相关专业的信息。它是一个 JSON 列表，每个元素代表一个学校对象。

```json
[
  {
    "id": "string", // 学校唯一标识符，可使用清理后的院校名称
    "name": "string", // 清理后的院校名称
    "level": "string", // 院校等级 (e.g., "985", "211", "双一流", "一般")，需从Excel提取或映射
    "region": "string", // 地区分类 ("A区", "B区")，需判断
    "province": "string", // 省份 (e.g., "四川", "陕西")，从Excel工作表名或数据中提取
    "intro": "string", // 院校简介
    "computer_rank": "string", // 教育部学科评估计算机等级 (e.g., "A+", "B-", "无")
    "self_vs_408": "string", // 专业课考试类型 ("自命题", "408统考")，需判断
    "departments": [ // 该校所有招收相关专业的院系列表
      {
        "department_name": "string", // 招生院系名称
        "majors": [ // 该院系下的专业列表
          {
            "major_code": "string", // 专业代码 (e.g., "081200")
            "major_name": "string", // 专业名称 (e.g., "计算机科学与技术")
            "exam_subjects": "string", // 初试科目详情 (可能包含多行文本)
            "reference_books": "string", // 参考书目 (可能为空或多行文本)
            "retrial_subjects": "string", // 复试科目详情 (可能包含多行文本)
            "enrollment_24": "number | null", // 24年计划招生人数 (数字或null)
            "tuition_duration": "string", // 学费学制详情 (可能包含多行文本)
            "score_lines": { // 复试分数线信息
              "2024": "string | null", // 24年复试线详情或分数
              "2023": "string | null"  // 23年复试线详情或分数
              // 四川院校需要补充近三年数据
            },
            "admission_info_23": "string | null", // 23年拟录取情况详情
            "admission_info_24": "string | null"  // 24年拟录取情况详情或名单链接
          }
          // ... more majors
        ]
      }
      // ... more departments
    ],
    "favorites_count": 0 // 用户收藏该院校的数量，用于排序
  }
  // ... more schools
]
```

### 其他数据文件 (待定义)

* `national_lines.json`: 存储近几年的国家线数据（总分、政治、英语、数学）。
* `announcements.json`: 存储公告通知信息。
* `users/`: 可能包含每个用户的 JSON 文件，存储其个人信息、偏好和收藏列表（如果选择文件存储用户数据）。
