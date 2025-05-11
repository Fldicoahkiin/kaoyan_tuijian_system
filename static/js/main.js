// --- 添加 CSS 样式 (注入到 head 或 link 到 CSS 文件) ---
const styles = `
.col-resizer {
    position: absolute;
    top: 0;
    right: -3px; /* slight overlap */
    width: 6px;
    height: 100%;
    cursor: col-resize;
    background-color: rgba(100, 100, 100, 0.1); /* subtle visibility */
    z-index: 1;
}
.col-resizer:hover,
.col-resizer.dragging {
    background-color: rgba(0, 150, 255, 0.3);
}
.dashboard-schools-table th {
    white-space: nowrap; /* Prevent header text wrapping */
    overflow: hidden;
    text-overflow: ellipsis;
}
.dashboard-schools-table td {
    white-space: nowrap; /* Prevent content wrapping initially */
    overflow: hidden;
    text-overflow: ellipsis;
}
`;
const styleSheet = document.createElement("style");
styleSheet.type = "text/css";
styleSheet.innerText = styles;
document.head.appendChild(styleSheet);

document.addEventListener('DOMContentLoaded', function() {
    // setupThemeSwitcher(); // REMOVED:不再需要主题切换
    initCharts();
    fetchSchoolsForDashboard();
    fetchAnnouncements();
    
    // Initialize resizable tables on the page
    document.querySelectorAll('.resizable-table').forEach(enableColumnResizing);

    // Initial height adjustment after a short delay to allow ECharts to render
    // setTimeout(adjustColumnHeights, 500); // REMOVE THIS
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
    tableBody.innerHTML = `<tr><td colspan="7" class="text-center p-5"><div class="spinner-border spinner-border-sm text-primary" role="status"><span class="visually-hidden">加载中...</span></div> 正在加载院校数据...</td></tr>`;
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
            tableBody.innerHTML = `<tr><td colspan="7" class="text-center p-5 text-danger">加载院校数据失败: ${error.message}</td></tr>`;
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
        tableBody.innerHTML = `<tr><td colspan=\"7\" class=\"text-center p-5 text-muted\">没有更多院校数据</td></tr>`;
    } else {
        schoolsToShow.forEach(school => {
            let levelBadgeClass = 'bg-secondary'; // Default color
            switch (school.level) {
                case '985': levelBadgeClass = 'bg-danger'; break;
                case '211': levelBadgeClass = 'bg-warning text-dark'; break;
                case '双一流': levelBadgeClass = 'bg-info'; break;
            }

            const row = `
                <tr>
                    <td style=\"min-width: 180px; white-space: nowrap;\"><a href=\"/school/${encodeURIComponent(school.id)}\" class=\"text-decoration-none link-light\">${school.name || 'N/A'}</a></td>
                    <td style=\"min-width: 80px; white-space: nowrap;\"><span class=\"badge ${levelBadgeClass}\">${school.level || '普通院校'}</span></td>
                    <td style=\"min-width: 80px; white-space: nowrap;\">${school.province || 'N/A'}</td>
                    <td style=\"min-width: 60px; white-space: nowrap;\"><span class=\"badge ${ school.region === 'A区' ? 'bg-primary' : (school.region === 'B区' ? 'bg-info' : 'bg-secondary') }\">${school.region || 'N/A'}</span></td>
                    <td style=\"min-width: 120px; white-space: nowrap;\">${school.computer_rank || 'N/A'}</td>
                    <td style=\"min-width: 100px; text-align: center; white-space: nowrap;\">${school.enrollment_24_school_total || '-'}</td>
                    <td style=\"min-width: 100px; text-align: center; white-space: nowrap;\">${school.enrollment_24_academic || '-'}</td>
                    <td style=\"min-width: 100px; text-align: center; white-space: nowrap;\">${school.enrollment_24_professional || '-'}</td>
                    <td style=\"white-space: nowrap;\">${school.exam_subjects || '-'}</td>
                </tr>
            `;
            tableBody.innerHTML += row;
        });
    }
    renderDashboardPagination();
    // 在渲染完分页 *之后* 尝试调整高度
    // setTimeout(adjustColumnHeights, 50); // 短暂延迟确保渲染完成
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
    // Initialize new charts
    // 1. 左上角: 计算机总分近三年国家线折线图
    const csTotalChartDom = document.getElementById('national-line-cs-total');
    if (csTotalChartDom) {
        const csTotalChart = echarts.init(csTotalChartDom, 'dark');
        // The API /api/national-lines/computer-science-total is expected to return line chart data
        fetchNationalLineData('/api/national-lines/computer-science-total', csTotalChart, '近三年计算机总分国家线');
    }

    // 2. 左中: 政治近3年国家线柱状图
    const politicsRecentChartDom = document.getElementById('national-line-politics-recent');
    if (politicsRecentChartDom) {
        const politicsRecentChart = echarts.init(politicsRecentChartDom, 'dark');
        // The API /api/national-lines/politics-recent is expected to return bar chart data
        fetchNationalLineData('/api/national-lines/politics-recent', politicsRecentChart, '近三年政治国家线');
    }

    // 3. 左下角: 英语(1,2)数学(1,2)国家线走向折线图
    const engMathChartDom = document.getElementById('national-line-eng-math');
    if (engMathChartDom) {
        const engMathChart = echarts.init(engMathChartDom, 'dark');
        // The API /api/national-lines/english-math-subjects is expected to return line chart data for 4 lines
        fetchNationalLineData('/api/national-lines/english-math-subjects', engMathChart, '英/数主要科目国家线趋势');
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
                 grid: { left: '3%', right: '4%', top: '50px', bottom: '60px', containLabel: true },
                 xAxis: {
                    type: 'category',
                    boundaryGap: data.series && data.series.some(s => s.type === 'bar'), // True for bar charts
                    data: data.years || [], // Use years data from API
                    axisLabel: { color: '#ccc' }
                 },
                 yAxis: {
                    type: 'value',
                    // Use min AND max values from API if provided, otherwise default (null lets ECharts decide)
                    min: data.yAxis && data.yAxis.min !== null ? data.yAxis.min : null,
                    max: data.yAxis && data.yAxis.max !== null ? data.yAxis.max : null,
                    axisLabel: { color: '#ccc' }
                 },
                 series: data.series || [] // Use series data from API
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
                legend: { orient: 'horizontal', bottom: 15, data: data.map(item => item.name), textStyle: { color: '#ccc', overflow: 'breakAll' } },
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
                         label: { color: '#ccc', fontSize: 11, overflow: 'breakAll' },
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

// --- 高度调整函数 ---
function adjustColumnHeights() {
    const leftCol = document.querySelector('.left-column');
    const rightCol = document.querySelector('.right-column');
    const middleCol = document.getElementById('school-list-container');
    const middleTableContainer = middleCol.querySelector('.dashboard-schools-table-container');
    const middleHeader = middleCol.querySelector('h4');
    const middlePagination = middleCol.querySelector('#dashboard-school-pagination');

    if (!leftCol || !rightCol || !middleCol || !middleTableContainer || !middleHeader || !middlePagination) {
        console.warn("Height adjustment elements not found.");
        return;
    }

    const leftHeight = leftCol.offsetHeight;
    const rightHeight = rightCol.offsetHeight;
    const maxHeight = Math.max(leftHeight, rightHeight);

    const headerHeight = middleHeader.offsetHeight;
    const paginationHeight = middlePagination.offsetHeight;
    // 获取 middleCol 的 padding/margin (如果需要更精确计算)
    const middleColStyle = window.getComputedStyle(middleCol);
    const middleColPaddingTop = parseFloat(middleColStyle.paddingTop);
    const middleColPaddingBottom = parseFloat(middleColStyle.paddingBottom);
    const middleColMarginTop = parseFloat(middleColStyle.marginTop);
    const middleColMarginBottom = parseFloat(middleColStyle.marginBottom);
    
    // 计算表格容器应该占据的高度
    // 可用总高 = max(左右高) - middleCol上下margin/padding (粗略)
    // 表格高 = 可用总高 - header高 - pagination高
    const availableHeight = maxHeight - (middleColMarginTop + middleColMarginBottom + middleColPaddingTop + middleColPaddingBottom);
    let tableContainerHeight = availableHeight - headerHeight - paginationHeight;
    
    // 避免负高度
    tableContainerHeight = Math.max(50, tableContainerHeight); // 设置一个最小高度

    console.log(`Adjusting heights: Max=${maxHeight}, Header=${headerHeight}, Pager=${paginationHeight}, Available=${availableHeight}, CalculatedTableHeight=${tableContainerHeight}`);

    // 重新设置 flex-grow: 1 以防万一 height 被覆盖
    middleTableContainer.style.flexGrow = '1';
    middleTableContainer.style.overflowY = 'auto'; // 确保垂直滚动

}

// --- 列宽调整函数 (修改为查找 .resizable-table) ---
function enableColumnResizing() {
    document.querySelectorAll('.resizable-table').forEach(table => { // Target tables with the class
        if (!table) return;
        console.log('Enabling resizing for table:', table.id || 'No ID');

        let thBeingResized = null;
        let startX, startWidth;

        const onMouseMove = (e) => {
            if (!thBeingResized) return;
            const currentX = e.clientX;
            const diffX = currentX - startX;
            let newWidth = startWidth + diffX;
            // 设置最小宽度，防止列消失
            if (newWidth < 40) newWidth = 40;
            thBeingResized.style.width = `${newWidth}px`;
            // console.log(`Resizing ${thBeingResized.cellIndex} to ${newWidth}px`); // Reduce logging
        };

        const onMouseUp = () => {
            if (thBeingResized) {
                thBeingResized.querySelector('.col-resizer').classList.remove('dragging');
            }
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            thBeingResized = null;
            // console.log('Resizing finished'); // Reduce logging
        };

        table.querySelectorAll('thead th .col-resizer').forEach(resizer => { // Ensure we target resizers in the header
            resizer.addEventListener('mousedown', (e) => {
                // ... (mouse down logic - unchanged) ...
                e.preventDefault();
                thBeingResized = resizer.parentElement; 
                startX = e.clientX;
                startWidth = thBeingResized.offsetWidth;
                resizer.classList.add('dragging');
                // console.log(`Start resizing ${thBeingResized.cellIndex} from ${startWidth}px`); // Reduce logging

                document.addEventListener('mousemove', onMouseMove);
                document.addEventListener('mouseup', onMouseUp);
            });
        });
    }); // End forEach table
} 