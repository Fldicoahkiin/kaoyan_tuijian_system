from django.db.models import Count
from apps.schools.models import School, ScoreLine


# 权重配置
SCORE_WEIGHT = 0.4
LEVEL_WEIGHT = 0.2
CS_LEVEL_WEIGHT = 0.2
REGION_WEIGHT = 0.2

# 分数映射
LEVEL_SCORES = {'985': 60, '211': 40, 'double_first_class': 20, 'general': 0}
CS_LEVEL_SCORES = {
    'A+': 100, 'A': 80, 'A-': 70, 'B+': 60, 'B': 50, 
    'B-': 40, 'C+': 30, 'C': 20, 'C-': 10, 'none': 0
}
REGION_SCORES = {'match': 100, 'no_match': 0}


def calculate_score_similarity(target_score, school_average_score):
    """计算分数相似度，使用误差的倒数，并限制范围"""
    if school_average_score is None or school_average_score == 0:
        return 0
    error = abs(target_score - school_average_score)
    # 避免除零，并设定一个最大相似度
    max_score_diff = 100 # 假设最大分数差为100分，可调整
    similarity = max(0, 1 - (error / max_score_diff))
    return similarity * 100 # 转换为百分制


def calculate_recommendation_score(school_data, preferences):
    """
    计算单个学校的推荐得分
    school_data: 包含学校信息的字典 (id, name, level, cs_level, region, average_score)
    preferences: 用户偏好字典 (target_score, target_level, target_cs_level, target_region)
    """
    # 分数相似度
    score_similarity = calculate_score_similarity(
        preferences['target_score'], 
        school_data.get('average_score', 0)
    )
    
    # 院校等级得分
    level_score = LEVEL_SCORES.get(school_data['level'], 0)
    target_level_score = LEVEL_SCORES.get(preferences['target_level'], 0)
    level_similarity = 100 if level_score >= target_level_score else 0 # 可以更复杂，比如计算差值
    
    # 计算机等级得分
    cs_level_score = CS_LEVEL_SCORES.get(school_data['cs_level'], 0)
    target_cs_level_score = CS_LEVEL_SCORES.get(preferences['target_cs_level'], 0)
    cs_level_similarity = 100 if cs_level_score >= target_cs_level_score else 0 # 可以更复杂
    
    # 地区得分
    region_match_score = REGION_SCORES['match'] if school_data['region'] == preferences['target_region'] else REGION_SCORES['no_match']
    
    # 加权总分
    total_score = (
        score_similarity * SCORE_WEIGHT +
        level_similarity * LEVEL_WEIGHT +
        cs_level_similarity * CS_LEVEL_WEIGHT +
        region_match_score * REGION_WEIGHT
    )
    
    return total_score


def get_recommended_schools(preferences):
    """
    根据用户偏好获取推荐学校列表
    """
    # 1. 获取所有学校的基础信息和收藏数
    schools = School.objects.annotate(favorite_count=Count('favorited_by')).values(
        'id', 'name', 'level', 'cs_level', 'region', 'admission_count', 'favorite_count'
    )
    
    # 2. 获取学校近年的平均录取分数 (简化处理，实际应更复杂)
    # 这里可以考虑只用最近一年的分数线或平均录取分数
    # 为了简化，我们假设有一个平均分数，实际应用中需要计算或获取
    # 此处仅为示例，实际需要关联 ScoreLine 或 Admission 表计算平均分
    school_scores = {
        # 示例: school_id: average_score
        # 1: 380, 2: 370, ...
    }
    # 实际应用中需要从数据库获取或计算这些分数
    # 例如: ScoreLine.objects.filter(type='school', subject='total', year=SOME_YEAR).values(...)
    # 或 Admission.objects.filter(...).aggregate(Avg('score_total'))
    
    # 3. 计算每个学校的推荐得分
    recommended_list = []
    for school in schools:
        # 获取该学校的平均分（需要实现这部分逻辑）
        school['average_score'] = school_scores.get(school['id'], 0) 
        
        recommendation_score = calculate_recommendation_score(school, preferences)
        recommended_list.append({
            'school_id': school['id'],
            'name': school['name'],
            'level': school['level'],
            'cs_level': school['cs_level'],
            'admission_count': school['admission_count'],
            'favorite_count': school['favorite_count'],
            'recommendation_score': recommendation_score
        })
        
    # 4. 按推荐得分排序
    recommended_list.sort(key=lambda x: x['recommendation_score'], reverse=True)
    
    # 5. 返回前20个结果
    return recommended_list[:20] 