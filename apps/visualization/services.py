from django.db.models import Count, Q, Avg, Sum
from apps.schools.models import School, ScoreLine


def get_school_list_data():
    """
    获取学校列表数据
    返回：院校名称，院校等级，计算机等级，24年招生人数，初试科目，地区
    """
    return School.objects.all().values(
        'id', 'name', 'level', 'cs_level', 'admission_count', 'region', 'region_type', 'custom_test'
    ).annotate(favorite_count=Count('favorited_by'))


def get_national_score_trend_data():
    """
    获取计算机考研国家线三年走势数据
    """
    # 获取近三年总分国家线数据
    total_scores = ScoreLine.objects.filter(
        type='national',
        subject='total'
    ).order_by('year')
    
    # 格式化为前端所需数据结构
    result = {
        'years': [],
        'a_scores': [],
        'b_scores': []
    }
    
    for score in total_scores:
        result['years'].append(str(score.year))
        if score.region_type == 'A':
            result['a_scores'].append(score.score)
        elif score.region_type == 'B':
            result['b_scores'].append(score.score)
    
    return result


def get_politics_score_trend_data():
    """
    获取政治近三年国家线走势数据
    """
    # 获取政治国家线数据
    politics_scores = ScoreLine.objects.filter(
        type='national',
        subject='politics'
    ).order_by('year')
    
    # 格式化为前端所需数据结构
    result = {
        'years': [],
        'a_scores': [],
        'b_scores': []
    }
    
    for score in politics_scores:
        if str(score.year) not in result['years']:
            result['years'].append(str(score.year))
        
        if score.region_type == 'A':
            result['a_scores'].append(score.score)
        elif score.region_type == 'B':
            result['b_scores'].append(score.score)
    
    return result


def get_english_math_score_trend_data():
    """
    获取英语和数学近三年国家线走势数据
    """
    # 获取英语和数学国家线数据
    english_math_scores = ScoreLine.objects.filter(
        type='national',
        subject__in=['english1', 'english2', 'math1', 'math2']
    ).order_by('year')
    
    # 格式化为前端所需数据结构
    result = {
        'years': [],
        'english1_scores': [],
        'english2_scores': [],
        'math1_scores': [],
        'math2_scores': []
    }
    
    years = set()
    for score in english_math_scores:
        years.add(score.year)
    
    result['years'] = [str(year) for year in sorted(years)]
    
    # 填充默认值
    for _ in result['years']:
        result['english1_scores'].append(None)
        result['english2_scores'].append(None)
        result['math1_scores'].append(None)
        result['math2_scores'].append(None)
    
    # 填充实际值
    for score in english_math_scores:
        year_index = result['years'].index(str(score.year))
        if score.subject == 'english1':
            result['english1_scores'][year_index] = score.score
        elif score.subject == 'english2':
            result['english2_scores'][year_index] = score.score
        elif score.subject == 'math1':
            result['math1_scores'][year_index] = score.score
        elif score.subject == 'math2':
            result['math2_scores'][year_index] = score.score
    
    return result


def get_school_test_type_data():
    """
    获取计算机院校自命题与408统考的比例数据
    """
    custom_count = School.objects.filter(custom_test=True).count()
    national_count = School.objects.filter(custom_test=False).count()
    
    return {
        'labels': ['自命题', '统考408'],
        'data': [custom_count, national_count]
    } 