document.addEventListener('DOMContentLoaded', function() {
    setupThemeSwitcher(); // 初始化主题切换器
    fetchSchools();
    initCharts();
    fetchAnnouncements();
});

// --- 主题切换逻辑 ---
function setupThemeSwitcher() {
    const themeSwitch = document.getElementById('themeSwitch');
    const currentTheme = localStorage.getItem('theme') ? localStorage.getItem('theme') : null;
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const themeLabelIcon = document.querySelector('label[for="themeSwitch"] i'); // 获取图标元素

    // 根据存储或系统偏好设置初始主题
    if (currentTheme === 'dark' || (!currentTheme && prefersDark)) {
        document.body.classList.add('dark-theme');
        if (themeSwitch) themeSwitch.checked = true;
        if (themeLabelIcon) themeLabelIcon.className = 'fas fa-sun'; // 设置为太阳图标
    } else {
        // 默认是亮色主题 (移除 dark-theme 类)
        document.body.classList.remove('dark-theme');
        if (themeSwitch) themeSwitch.checked = false;
        if (themeLabelIcon) themeLabelIcon.className = 'fas fa-moon'; // 设置为月亮图标
    }

    // 监听切换事件
    if (themeSwitch) {
        themeSwitch.addEventListener('change', function(e) {
            if (e.target.checked) {
                document.body.classList.add('dark-theme');
                localStorage.setItem('theme', 'dark');
                if (themeLabelIcon) themeLabelIcon.className = 'fas fa-sun';
                // 需要重新初始化图表以应用深色主题
                if (typeof initCharts === 'function') {
                   // 销毁旧图表实例 (如果存在)
                   destroyCharts();
                   initCharts();
                }
            } else {
                document.body.classList.remove('dark-theme');
                localStorage.setItem('theme', 'light');
                if (themeLabelIcon) themeLabelIcon.className = 'fas fa-moon';
                // 重新初始化图表以应用亮色主题
                 if (typeof initCharts === 'function') {
                    destroyCharts();
                    initCharts();
                 }
            }
        });
    }
}

// 辅助函数：销毁 ECharts 实例 (防止重复初始化)
// 注意: 这需要确保 chart 实例是全局可访问的，或者修改 initCharts 让其返回实例
// 简单起见，我们假设 DOM 元素 ID 不变，直接 dispose
function destroyCharts() {
    const chartIds = ['national-line-total', 'national-line-politics', 'national-line-others', 'exam-type-pie'];
    chartIds.forEach(id => {
        const chartDom = document.getElementById(id);
        if (chartDom) {
            const chartInstance = echarts.getInstanceByDom(chartDom);
            if (chartInstance) {
                chartInstance.dispose();
            }
        }
    });
}

function fetchSchools() {
    fetch('/api/schools/list') // 调用后端的 API
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json(); // 解析 JSON 数据
        })
        .then(schools => {
            populateSchoolTable(schools); // 使用获取的数据填充表格
        })
        .catch(error => {
            console.error('获取学校列表失败:', error);
            const tableBody = document.getElementById('school-table-body');
            if (tableBody) {
                tableBody.innerHTML = '<tr><td colspan="6">加载学校列表失败，请稍后重试。</td></tr>';
            }
        });
}

function populateSchoolTable(schools) {
    const tableBody = document.getElementById('school-table-body');
    if (!tableBody) return;

    tableBody.innerHTML = ''; // 清空现有的表格内容

    if (!schools || schools.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6">暂无学校数据。</td></tr>';
        return;
    }

    schools.forEach(school => {
        const row = tableBody.insertRow();
        row.innerHTML = `
            <td>${school.name || 'N/A'}</td>
            <td>${school.level || 'N/A'}</td>
            <td>${school.computer_rank || 'N/A'}</td>
            <td>${school.enrollment_24 || 'N/A'}</td>
            <td>${school.subjects || 'N/A'}</td>
            <td>${school.region || 'N/A'}</td>
        `;
    });
}

// --- 图表初始化和数据获取 ---
function initCharts() {
    // 获取 DOM 元素
    const totalLineChartDom = document.getElementById('national-line-total');
    const politicsBarChartDom = document.getElementById('national-line-politics');
    const othersLineChartDom = document.getElementById('national-line-others');
    const examTypePieChartDom = document.getElementById('exam-type-pie');

    // 检查元素是否存在
    if (!totalLineChartDom || !politicsBarChartDom || !othersLineChartDom || !examTypePieChartDom) {
        console.error("One or more chart containers not found!");
        return;
    }

    // 初始化 ECharts 实例，根据当前主题应用 'dark' 或 null
    const currentTheme = document.body.classList.contains('dark-theme') ? 'dark' : null;
    const totalLineChart = echarts.init(totalLineChartDom, currentTheme);
    const politicsBarChart = echarts.init(politicsBarChartDom, currentTheme);
    const othersLineChart = echarts.init(othersLineChartDom, currentTheme);
    const examTypePieChart = echarts.init(examTypePieChartDom, currentTheme);

    // 设置加载动画 (更新颜色以适应深色主题)
    showLoading(totalLineChart, '加载总分国家线...');
    showLoading(politicsBarChart, '加载政治国家线...');
    showLoading(othersLineChart, '加载英数国家线...');
    showLoading(examTypePieChart, '加载考试类型比例...');

    // 获取并绘制总分国家线折线图
    fetch('/api/national-lines/total')
        .then(response => response.json())
        .then(data => {
            if (!data || !data.years || !data.scores) throw new Error("Invalid data format");
            const option = {
                title: { text: '近三年总分国家线 (计算机)', left: 'center' }, // 移除颜色设置
                tooltip: { trigger: 'axis' },
                legend: { data: Object.keys(data.scores), top: 30 }, // 移除颜色设置
                grid: { left: '3%', right: '4%', top: '20%', bottom: '15%', containLabel: true }, // 恢复一些底部边距
                xAxis: { type: 'category', boundaryGap: false, data: data.years }, // 移除颜色设置
                yAxis: { type: 'value', name: '分数' }, // 移除颜色设置
                series: Object.entries(data.scores).map(([name, values]) => ({
                    name: name,
                    type: 'line',
                    data: values
                }))
            };
            totalLineChart.setOption(option);
            totalLineChart.hideLoading();
        })
        .catch(error => handleError(error, totalLineChart, '加载总分国家线失败'));

    // 获取并绘制政治国家线柱状图
    fetch('/api/national-lines/politics')
        .then(response => response.json())
        .then(data => {
             if (!data || !data.years || !data.scores) throw new Error("Invalid data format");
            const option = {
                title: { text: '近三年政治国家线', left: 'center' },
                tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                legend: { data: Object.keys(data.scores), top: 30 },
                grid: { left: '3%', right: '4%', top: '18%', bottom: '15%', containLabel: true }, // 稍微增加底部边距
                xAxis: { type: 'category', data: data.years },
                yAxis: { type: 'value', name: '分数' },
                series: Object.entries(data.scores).map(([name, values]) => ({
                    name: name,
                    type: 'bar',
                    barMaxWidth: 30, // 控制柱子最大宽度
                    data: values
                }))
            };
            politicsBarChart.setOption(option);
            politicsBarChart.hideLoading();
        })
        .catch(error => handleError(error, politicsBarChart, '加载政治国家线失败'));

    // 获取并绘制英数国家线折线图
    fetch('/api/national-lines/others')
        .then(response => response.json())
        .then(data => {
            if (!data || !data.years || !data.scores) throw new Error("Invalid data format");
            const option = {
                title: { text: '近三年英/数国家线', left: 'center' },
                tooltip: { trigger: 'axis' },
                legend: { data: Object.keys(data.scores), top: 30, type: 'scroll', orient: 'horizontal' },
                grid: { left: '3%', right: '4%', top: '20%', bottom: '15%', containLabel: true }, // 保持调整后的边距
                xAxis: { type: 'category', boundaryGap: false, data: data.years },
                yAxis: { type: 'value', name: '分数' },
                series: Object.entries(data.scores).map(([name, values]) => ({
                    name: name,
                    type: 'line',
                    data: values
                }))
            };
            othersLineChart.setOption(option);
            othersLineChart.hideLoading();
        })
        .catch(error => handleError(error, othersLineChart, '加载英数国家线失败'));

    // 获取并绘制考试类型饼图
    fetch('/api/stats/exam-type-ratio')
        .then(response => response.json())
        .then(data => {
             if (!Array.isArray(data)) throw new Error("Invalid data format");
            const option = {
                title: { text: '考试类型比例 (自命题 vs 408)', left: 'center' },
                tooltip: { trigger: 'item', formatter: '{a} <br/>{b} : {c} ({d}%)' },
                legend: { orient: 'vertical', left: 10, top: 'center' }, // 图例移到左侧居中
                series: [
                    {
                        name: '考试类型',
                        type: 'pie',
                        radius: ['40%', '60%'], // 改为圆环图，更有科技感
                        center: ['65%', '55%'], // 调整中心，给图例留空间
                        avoidLabelOverlap: false,
                        itemStyle: {
                            borderRadius: 5, // 圆角
                            borderColor: '#1a1a2e', // 边框颜色用背景色
                            borderWidth: 2
                        },
                         label: {
                            show: false, // 默认不显示标签
                            position: 'center'
                        },
                        emphasis: {
                             label: {
                                show: true,
                                fontSize: '20',
                                fontWeight: 'bold',
                                color: '#e0e0e0' // 强调时显示标签
                            },
                            itemStyle: {
                                shadowBlur: 10,
                                shadowOffsetX: 0,
                                shadowColor: 'rgba(0, 0, 0, 0.5)'
                            }
                        },
                        labelLine: {
                            show: false
                        },
                        data: data
                    }
                ]
            };
            examTypePieChart.setOption(option);
            examTypePieChart.hideLoading();
        })
        .catch(error => handleError(error, examTypePieChart, '加载考试类型比例失败'));
}

// --- 公告数据获取和填充 ---
function fetchAnnouncements() {
    fetch('/api/announcements')
        .then(response => response.json())
        .then(announcements => {
            populateAnnouncements(announcements);
        })
        .catch(error => {
            console.error('获取公告失败:', error);
            const list = document.getElementById('announcement-list');
            if (list) {
                list.innerHTML = '<li>加载公告失败。</li>';
            }
        });
}

function populateAnnouncements(announcements) {
    const list = document.getElementById('announcement-list');
    if (!list) return;
    list.innerHTML = '';
    if (!announcements || announcements.length === 0) {
        list.innerHTML = '<li>暂无公告。</li>';
        return;
    }
    announcements.forEach(announce => {
        const listItem = document.createElement('li');
        // 如果有 URL，创建链接
        if (announce.url && announce.url !== '#') {
            listItem.innerHTML = `<a href="${announce.url}" target="_blank">${announce.title}</a>`;
        } else {
            listItem.textContent = announce.title;
        }
        list.appendChild(listItem);
    });
}

// --- 辅助函数 (更新样式) ---
function showLoading(chartInstance, text = '加载中...') {
    chartInstance.showLoading('default', {
        text: text,
        color: '#478eff', // 主题亮色
        textColor: '#e0e0e0', // 主要文字颜色
        maskColor: 'rgba(26, 26, 46, 0.8)', // 使用深色背景的半透明遮罩
        zlevel: 0
    });
}

function handleError(error, chartInstance, message) {
    console.error(message + ':', error);
    chartInstance.hideLoading();
    // 在图表区域显示错误信息
    chartInstance.setOption({ // 使用 setOption 清除可能存在的旧图形
        title: {
            text: message + '，请稍后重试。',
            left: 'center',
            top: 'center'
        }
    });
     // 可以选择不显示 loading 图标，只显示文字
    /*
    chartInstance.showLoading('default', {
        text: message + '，请稍后重试。',
        color: '#dc3545', // 危险色
        textColor: '#dc3545',
        maskColor: 'rgba(26, 26, 46, 0.8)',
    });
    */
} 