document.addEventListener('DOMContentLoaded', function() {
    // setupThemeSwitcher(); // REMOVED:不再需要主题切换
    fetchSchoolsForDashboard();
    initCharts();
    fetchAnnouncements();
});

// REMOVED: 不再需要主题切换逻辑
/*
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
*/

// REMOVED: 不再需要销毁图表逻辑
/*
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
*/

// --- 全局变量 --- 
let allDashboardSchools = []; // 存储从 API 获取的所有学校数据
let dashboardCurrentPage = 1;
const dashboardItemsPerPage = 15; // 仪表盘每页显示的数量

// --- 加载和显示仪表盘院校列表 (含分页) ---
function fetchSchoolsForDashboard() {
    const tableBody = document.getElementById('dashboard-school-table-body');
    const paginationContainer = document.getElementById('dashboard-school-pagination');
    if (!tableBody || !paginationContainer) return;

    // 显示加载状态
    tableBody.innerHTML = `<tr><td colspan="4" class="text-center p-5"><div class="spinner-border spinner-border-sm text-primary" role="status"><span class="visually-hidden">加载中...</span></div> 正在加载院校数据...</td></tr>`;
    paginationContainer.innerHTML = '';

    fetch('/api/schools/list')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            allDashboardSchools = data; // 存储所有数据
            dashboardCurrentPage = 1; // 重置到第一页
            renderDashboardSchoolPage(dashboardCurrentPage);
        })
        .catch(error => {
            console.error('Error fetching schools for dashboard:', error);
            tableBody.innerHTML = `<tr><td colspan="4" class="text-center p-5 text-danger">加载院校数据失败: ${error.message}</td></tr>`;
        });
}

function renderDashboardSchoolPage(page) {
    const tableBody = document.getElementById('dashboard-school-table-body');
    const paginationContainer = document.getElementById('dashboard-school-pagination');
    if (!tableBody || !paginationContainer) return;

    dashboardCurrentPage = page;
    const startIndex = (page - 1) * dashboardItemsPerPage;
    const endIndex = startIndex + dashboardItemsPerPage;
    const schoolsToShow = allDashboardSchools.slice(startIndex, endIndex);

    tableBody.innerHTML = ''; // 清空表格内容
    if (schoolsToShow.length === 0) {
        tableBody.innerHTML = `<tr><td colspan=\"4\" class=\"text-center p-5 text-muted\">没有更多院校数据</td></tr>`;
    } else {
        schoolsToShow.forEach(school => {
            const row = `
                <tr>
                    <td><a href=\"/school/${encodeURIComponent(school.id)}\" class=\"text-decoration-none link-light\">${school.name || 'N/A'}</a></td>
                    <td><span class=\"badge bg-secondary\">${school.level || 'N/A'}</span></td>
                    <td>${school.province || 'N/A'}</td>
                    <td>${school.computer_rank || 'N/A'}</td>
                </tr>
            `;
            tableBody.innerHTML += row;
        });
    }

    renderDashboardPagination();
}

function renderDashboardPagination() {
    const paginationContainer = document.getElementById('dashboard-school-pagination');
    if (!paginationContainer) return;

    const totalPages = Math.ceil(allDashboardSchools.length / dashboardItemsPerPage);
    paginationContainer.innerHTML = ''; // 清空分页

    if (totalPages <= 1) return; // 如果只有一页或没有数据，不显示分页

    const ul = document.createElement('ul');
    ul.className = 'pagination pagination-sm mb-0'; // 使用 Bootstrap 分页样式

    // 上一页按钮
    const prevLi = document.createElement('li');
    prevLi.className = `page-item ${dashboardCurrentPage === 1 ? 'disabled' : ''}`;
    const prevLink = document.createElement('a');
    prevLink.className = 'page-link';
    prevLink.href = '#';
    prevLink.innerHTML = '&laquo;';
    prevLink.addEventListener('click', (e) => {
        e.preventDefault();
        if (dashboardCurrentPage > 1) {
            renderDashboardSchoolPage(dashboardCurrentPage - 1);
        }
    });
    prevLi.appendChild(prevLink);
    ul.appendChild(prevLi);

    // 页码按钮 (简化版，只显示当前页附近几页)
    const maxPagesToShow = 5;
    let startPage = Math.max(1, dashboardCurrentPage - Math.floor(maxPagesToShow / 2));
    let endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);
    if (endPage - startPage + 1 < maxPagesToShow) {
         startPage = Math.max(1, endPage - maxPagesToShow + 1);
     }

    if (startPage > 1) {
        const firstLi = document.createElement('li');
        firstLi.className = 'page-item';
        const firstLink = document.createElement('a');
        firstLink.className = 'page-link';
        firstLink.href = '#';
        firstLink.innerText = '1';
        firstLink.addEventListener('click', (e) => { e.preventDefault(); renderDashboardSchoolPage(1); });
        firstLi.appendChild(firstLink);
        ul.appendChild(firstLi);
        if (startPage > 2) {
             const ellipsisLi = document.createElement('li');
             ellipsisLi.className = 'page-item disabled';
             ellipsisLi.innerHTML = `<span class="page-link">...</span>`;
             ul.appendChild(ellipsisLi);
         }
    }


    for (let i = startPage; i <= endPage; i++) {
        const li = document.createElement('li');
        li.className = `page-item ${i === dashboardCurrentPage ? 'active' : ''}`;
        const link = document.createElement('a');
        link.className = 'page-link';
        link.href = '#';
        link.innerText = i;
        link.addEventListener('click', (e) => {
            e.preventDefault();
            renderDashboardSchoolPage(i);
        });
        li.appendChild(link);
        ul.appendChild(li);
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const ellipsisLi = document.createElement('li');
            ellipsisLi.className = 'page-item disabled';
            ellipsisLi.innerHTML = `<span class="page-link">...</span>`;
            ul.appendChild(ellipsisLi);
        }
        const lastLi = document.createElement('li');
        lastLi.className = 'page-item';
        const lastLink = document.createElement('a');
        lastLink.className = 'page-link';
        lastLink.href = '#';
        lastLink.innerText = totalPages;
        lastLink.addEventListener('click', (e) => { e.preventDefault(); renderDashboardSchoolPage(totalPages); });
        lastLi.appendChild(lastLink);
        ul.appendChild(lastLi);
    }

    // 下一页按钮
    const nextLi = document.createElement('li');
    nextLi.className = `page-item ${dashboardCurrentPage === totalPages ? 'disabled' : ''}`;
    const nextLink = document.createElement('a');
    nextLink.className = 'page-link';
    nextLink.href = '#';
    nextLink.innerHTML = '&raquo;';
    nextLink.addEventListener('click', (e) => {
        e.preventDefault();
        if (dashboardCurrentPage < totalPages) {
            renderDashboardSchoolPage(dashboardCurrentPage + 1);
        }
    });
    nextLi.appendChild(nextLink);
    ul.appendChild(nextLi);

    paginationContainer.appendChild(ul);
}

// --- ECharts 初始化 --- 
function initCharts() {
    // 初始化国家线总分图表
    const nationalLineTotalChartDom = document.getElementById('national-line-total');
    if (nationalLineTotalChartDom) {
        const nationalLineTotalChart = echarts.init(nationalLineTotalChartDom, 'dark');
        fetchNationalLineData('/api/national-lines/total', nationalLineTotalChart, '国家线总分趋势');
    }

    // 初始化国家线政治英语图表
    const nationalLinePoliticsChartDom = document.getElementById('national-line-politics');
    if (nationalLinePoliticsChartDom) {
        const nationalLinePoliticsChart = echarts.init(nationalLinePoliticsChartDom, 'dark');
         fetchNationalLineData('/api/national-lines/politics', nationalLinePoliticsChart, '国家线政治/英语趋势');
    }

    // 初始化国家线其他科目图表
     const nationalLineOthersChartDom = document.getElementById('national-line-others');
     if (nationalLineOthersChartDom) {
         const nationalLineOthersChart = echarts.init(nationalLineOthersChartDom, 'dark');
         fetchNationalLineData('/api/national-lines/others', nationalLineOthersChart, '国家线数/专科趋势');
     }

    // 初始化考试类型比例饼图
    const examTypePieChartDom = document.getElementById('exam-type-pie');
    if (examTypePieChartDom) {
        const examTypePieChart = echarts.init(examTypePieChartDom, 'dark');
         fetchExamTypeRatio(examTypePieChart);
    }
}

function fetchNationalLineData(apiUrl, chartInstance, title) {
     showLoading(chartInstance);
    fetch(apiUrl)
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(data => {
            const option = {
                 title: { text: title, left: 'center', top: 10, textStyle: { color: '#ccc' } },
                 tooltip: { trigger: 'axis' },
                 legend: { data: data.legend, bottom: 10, textStyle: { color: '#ccc' } },
                 grid: { left: '3%', right: '4%', top: '50px', bottom: '40px', containLabel: true },
                 xAxis: { type: 'category', data: data.years, axisLabel: { color: '#ccc' } },
                 yAxis: {
                    type: 'value',
                    min: 'dataMin', // 设置 Y 轴从数据最小值开始
                    axisLabel: { color: '#ccc' } // X轴文字颜色 -> Y轴文字颜色
                 },
                 series: data.series // 直接使用从API获取的series配置
             };
            chartInstance.setOption(option);
            chartInstance.hideLoading();
        })
        .catch(error => handleError(error, chartInstance, `加载 ${title} 数据失败`));
}

function fetchExamTypeRatio(chartInstance) {
    showLoading(chartInstance);
    fetch('/api/stats/exam-type-ratio')
        .then(response => {
             if (!response.ok) throw new Error('Network response was not ok');
             return response.json();
         })
        .then(data => {
            const option = {
                title: { text: '自命题 vs 408 比例', left: 'center', top: 10, textStyle: { color: '#ccc' } },
                tooltip: { trigger: 'item', formatter: '{a} <br/>{b} : {c} ({d}%)' },
                legend: { orient: 'horizontal', bottom: 10, data: data.map(item => item.name), textStyle: { color: '#ccc' } },
                series: [
                    {
                        name: '考试类型',
                        type: 'pie',
                        radius: '55%',
                        center: ['50%', '58%'],
                        data: data,
                        emphasis: {
                            itemStyle: {
                                shadowBlur: 10,
                                shadowOffsetX: 0,
                                shadowColor: 'rgba(0, 0, 0, 0.5)'
                            }
                        },
                         label: { color: '#ccc', fontSize: 11 },
                         labelLine: { lineStyle: { color: '#aaa' }, length: 4, length2: 8 }
                    }
                ]
            };
            chartInstance.setOption(option);
            chartInstance.hideLoading();
        })
        .catch(error => handleError(error, chartInstance, '加载考试类型比例失败'));
}

// --- 加载和显示公告 ---
function fetchAnnouncements() {
    const announcementList = document.getElementById('announcement-list');
    if (!announcementList) return;

    fetch('/api/announcements')
        .then(response => {
             if (!response.ok) throw new Error('Network response was not ok');
             return response.json();
        })
        .then(data => {
            populateAnnouncements(data);
        })
        .catch(error => {
            console.error('Error fetching announcements:', error);
             announcementList.innerHTML = `<li class="list-group-item bg-transparent text-danger">加载公告失败: ${error.message}</li>`;
        });
}

function populateAnnouncements(announcements) {
    const announcementList = document.getElementById('announcement-list');
    if (!announcementList) return;

    announcementList.innerHTML = ''; // 清空现有列表

    if (announcements && announcements.length > 0) {
        announcements.forEach(announcement => {
            const li = document.createElement('li');
             li.className = 'list-group-item bg-transparent border-bottom border-secondary'; // 使用深色主题样式

            const titleSpan = document.createElement('span');
            titleSpan.textContent = announcement.title;

            if (announcement.url) {
                const link = document.createElement('a');
                link.href = announcement.url;
                link.target = '_blank'; // 在新标签页打开
                link.rel = 'noopener noreferrer';
                link.className = 'text-decoration-none'; // 移除下划线
                link.appendChild(titleSpan);
                li.appendChild(link);
            } else {
                li.appendChild(titleSpan);
            }

             // 添加时间戳 (如果数据中有)
             if (announcement.timestamp) {
                 const timeSpan = document.createElement('small');
                 timeSpan.className = 'text-muted float-end';
                 // 简单格式化时间，可以根据需要改进
                 const date = new Date(announcement.timestamp);
                 timeSpan.textContent = date.toLocaleDateString();
                 li.appendChild(timeSpan);
             }

            announcementList.appendChild(li);
        });
    } else {
        announcementList.innerHTML = '<li class="list-group-item bg-transparent text-muted text-center">暂无公告</li>';
    }
}

// --- ECharts 辅助函数 ---
function showLoading(chartInstance, text = '加载中...') {
     if (chartInstance && typeof chartInstance.showLoading === 'function') {
         chartInstance.showLoading('default', {
             text: text,
             color: '#00bcd4',
             textColor: '#ccc',
             maskColor: 'rgba(0, 0, 0, 0.3)',
             zlevel: 0
         });
     }
}

function handleError(error, chartInstance, message) {
     console.error(`${message}:`, error);
     if (chartInstance && typeof chartInstance.hideLoading === 'function') {
         chartInstance.hideLoading();
         // 可选：在图表上显示错误信息
          chartInstance.showLoading('default', {
              text: `${message}\n${error.message}`,
              color: '#dc3545', // 红色
              textColor: '#f8d7da',
              maskColor: 'rgba(0, 0, 0, 0.5)',
              zlevel: 0
          });
     }
}

// (可能需要的旧 fetchSchools 函数 - 如有其他地方调用)
// function fetchSchools() {
//     // ... 旧的实现 ... 
// } 