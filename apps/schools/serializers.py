from rest_framework import serializers
from .models import School, Department, Major, Subject, ScoreLine, Admission


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'is_custom', 'description']


class MajorSerializer(serializers.ModelSerializer):
    subjects = SubjectSerializer(many=True, read_only=True)
    
    class Meta:
        model = Major
        fields = ['id', 'name', 'code', 'admission_count', 'description', 'subjects']


class DepartmentSerializer(serializers.ModelSerializer):
    majors = MajorSerializer(many=True, read_only=True)
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'majors']


class ScoreLineSerializer(serializers.ModelSerializer):
    subject_display = serializers.CharField(source='get_subject_display', read_only=True)
    
    class Meta:
        model = ScoreLine
        fields = ['id', 'year', 'type', 'subject', 'subject_display', 'score']


class SchoolListSerializer(serializers.ModelSerializer):
    """学校列表序列化器，只包含基本信息"""
    favorite_count = serializers.IntegerField(read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    cs_level_display = serializers.CharField(source='get_cs_level_display', read_only=True)
    region_type_display = serializers.CharField(source='get_region_type_display', read_only=True)
    
    class Meta:
        model = School
        fields = ['id', 'name', 'level', 'level_display', 'cs_level', 'cs_level_display', 
                 'region', 'region_type', 'region_type_display', 'admission_count', 
                 'custom_test', 'favorite_count']


class SchoolDetailSerializer(serializers.ModelSerializer):
    """学校详细信息序列化器，包含院系、专业等详细信息"""
    departments = DepartmentSerializer(many=True, read_only=True)
    favorite_count = serializers.IntegerField(read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    cs_level_display = serializers.CharField(source='get_cs_level_display', read_only=True)
    region_type_display = serializers.CharField(source='get_region_type_display', read_only=True)
    is_favorited = serializers.SerializerMethodField()
    
    class Meta:
        model = School
        fields = ['id', 'name', 'level', 'level_display', 'cs_level', 'cs_level_display', 
                 'region', 'region_type', 'region_type_display', 'logo', 'description',
                 'admission_count', 'custom_test', 'favorite_count', 'is_favorited',
                 'departments', 'created_at', 'updated_at']
    
    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.favorited_by.filter(user=request.user).exists()
        return False


class NationalScoreLineSerializer(serializers.ModelSerializer):
    """国家线序列化器"""
    subject_display = serializers.CharField(source='get_subject_display', read_only=True)
    region_type_display = serializers.CharField(source='get_region_type_display', read_only=True)
    
    class Meta:
        model = ScoreLine
        fields = ['id', 'year', 'region_type', 'region_type_display', 'subject', 'subject_display', 'score']


class SchoolScoreLineSerializer(serializers.ModelSerializer):
    """学校复试线序列化器"""
    subject_display = serializers.CharField(source='get_subject_display', read_only=True)
    school_name = serializers.CharField(source='school.name', read_only=True)
    major_name = serializers.CharField(source='major.name', read_only=True, default='')
    
    class Meta:
        model = ScoreLine
        fields = ['id', 'year', 'school', 'school_name', 'major', 'major_name',
                 'subject', 'subject_display', 'score']


class AdmissionSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    major_name = serializers.CharField(source='major.name', read_only=True)
    
    class Meta:
        model = Admission
        fields = ['id', 'year', 'school', 'school_name', 'major', 'major_name',
                 'student_name', 'score_total', 'score_politics', 'score_english',
                 'score_math', 'score_professional'] 