from rest_framework import serializers
from apps.schools.models import School


class RecommendationInputSerializer(serializers.Serializer):
    """
    推荐算法输入序列化器
    """
    target_score = serializers.IntegerField(required=True, label="目标分数")
    target_level = serializers.ChoiceField(required=True, label="目标院校等级", choices=School.SCHOOL_LEVEL_CHOICES)
    target_cs_level = serializers.ChoiceField(required=True, label="目标计算机等级", choices=School.CS_LEVEL_CHOICES)
    target_region = serializers.CharField(required=True, label="目标地区", max_length=50)


class RecommendedSchoolSerializer(serializers.Serializer):
    """
    推荐结果序列化器
    """
    school_id = serializers.IntegerField(label="学校ID")
    name = serializers.CharField(label="学校名称")
    level = serializers.CharField(label="院校等级")
    cs_level = serializers.CharField(label="计算机等级")
    admission_count = serializers.IntegerField(label="24年招生人数")
    favorite_count = serializers.IntegerField(label="收藏人数")
    recommendation_score = serializers.FloatField(label="推荐得分") 