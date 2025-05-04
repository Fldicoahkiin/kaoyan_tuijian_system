document.addEventListener('DOMContentLoaded', function() {
    fetchSchools();
    initCharts();
    fetchAnnouncements();
});

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
    // 初始化 ECharts 实例
    const totalLineChart = echarts.init(document.getElementById('national-line-total'));
    const politicsBarChart = echarts.init(document.getElementById('national-line-politics'));
    const othersLineChart = echarts.init(document.getElementById('national-line-others'));
    const examTypePieChart = echarts.init(document.getElementById('exam-type-pie'));

    // 设置加载动画
    showLoading(totalLineChart, '加载总分国家线...');
    showLoading(politicsBarChart, '加载政治国家线...');
    showLoading(othersLineChart, '加载英数国家线...');
    showLoading(examTypePieChart, '加载考试类型比例...');

    // 获取并绘制总分国家线折线图
    fetch('/api/national-lines/total')
        .then(response => response.json())
        .then(data => {
            const option = {
                title: { text: '近三年总分国家线 (计算机)', left: 'center', textStyle: { fontSize: 14 } },
                tooltip: { trigger: 'axis' },
                legend: { data: Object.keys(data.scores), top: 30 },
                grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
                xAxis: { type: 'category', boundaryGap: false, data: data.years },
                yAxis: { type: 'value', name: '分数' },
                series: Object.entries(data.scores).map(([name, values]) => ({
                    name: name,
                    type: 'line',
                    // stack: 'Total', // 如果希望堆叠显示可以取消注释
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
            const option = {
                title: { text: '近三年政治国家线', left: 'center', textStyle: { fontSize: 14 } },
                tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                legend: { data: Object.keys(data.scores), top: 30 },
                grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
                xAxis: { type: 'category', data: data.years },
                yAxis: { type: 'value', name: '分数' },
                series: Object.entries(data.scores).map(([name, values]) => ({
                    name: name,
                    type: 'bar',
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
            const option = {
                title: { text: '近三年英/数国家线', left: 'center', textStyle: { fontSize: 14 } },
                tooltip: { trigger: 'axis' },
                legend: { data: Object.keys(data.scores), top: 30, type: 'scroll', orient: 'horizontal' }, // 可能需要滚动图例
                grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true }, // 留出更多底部空间给图例
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
            const option = {
                title: { text: '考试类型比例 (自命题 vs 408)', left: 'center', textStyle: { fontSize: 14 } },
                tooltip: { trigger: 'item', formatter: '{a} <br/>{b} : {c} ({d}%)' },
                legend: { orient: 'vertical', left: 'left', top: 'middle' }, // 图例放左侧垂直排列
                series: [
                    {
                        name: '考试类型',
                        type: 'pie',
                        radius: '50%', // 饼图半径
                        center: ['65%', '55%'], // 饼图中心位置，调整以避开图例
                        data: data,
                        emphasis: {
                            itemStyle: {
                                shadowBlur: 10,
                                shadowOffsetX: 0,
                                shadowColor: 'rgba(0, 0, 0, 0.5)'
                            }
                        }
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

// --- 辅助函数 ---
function showLoading(chartInstance, text = '加载中...') {
    chartInstance.showLoading('default', {
        text: text,
        color: '#4477cc',
        textColor: '#333',
        maskColor: 'rgba(255, 255, 255, 0.8)',
        zlevel: 0
    });
}

function handleError(error, chartInstance, message) {
    console.error(message + ':', error);
    chartInstance.hideLoading();
    // 可选：在图表区域显示错误信息
    chartInstance.showLoading('default', {
        text: message + '，请稍后重试。',
        color: '#c23531',
        textColor: '#c23531'
    });
} 