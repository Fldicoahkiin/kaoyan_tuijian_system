from django.db.models import Count
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404

from .models import School, Department, Major, Subject, ScoreLine, Admission
from .serializers import (
    SchoolListSerializer, SchoolDetailSerializer, DepartmentSerializer,
    MajorSerializer, SubjectSerializer, ScoreLineSerializer,
    NationalScoreLineSerializer, SchoolScoreLineSerializer, AdmissionSerializer
)


class SchoolViewSet(viewsets.ReadOnlyModelViewSet):
    """
    学校视图集
    """
    queryset = School.objects.all().annotate(favorite_count=Count('favorited_by'))
    serializer_class = SchoolListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['level', 'cs_level', 'region', 'region_type', 'custom_test']
    search_fields = ['name', 'description', 'region']
    ordering_fields = ['name', 'admission_count', 'favorite_count']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return SchoolDetailSerializer
        return SchoolListSerializer
    
    def get_permissions(self):
        if self.action == 'score_lines' or self.action == 'admissions':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]
    
    @action(detail=True, methods=['get'])
    def score_lines(self, request, pk=None):
        """获取学校的分数线"""
        school = self.get_object()
        score_lines = ScoreLine.objects.filter(school=school, type='school')
        serializer = SchoolScoreLineSerializer(score_lines, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def admissions(self, request, pk=None):
        """获取学校的录取情况"""
        school = self.get_object()
        year = request.query_params.get('year')
        major_id = request.query_params.get('major_id')
        
        admissions = Admission.objects.filter(school=school)
        if year:
            admissions = admissions.filter(year=year)
        if major_id:
            admissions = admissions.filter(major_id=major_id)
            
        serializer = AdmissionSerializer(admissions, many=True)
        return Response(serializer.data)


class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    院系视图集
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['school']
    search_fields = ['name', 'description']


class MajorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    专业视图集
    """
    queryset = Major.objects.all()
    serializer_class = MajorSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['department', 'department__school', 'code']
    search_fields = ['name', 'code', 'description']


class ScoreLineViewSet(viewsets.ReadOnlyModelViewSet):
    """
    分数线视图集
    """
    queryset = ScoreLine.objects.all()
    serializer_class = ScoreLineSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['year', 'type', 'subject', 'school', 'major', 'region_type']
    
    def get_serializer_class(self):
        type_param = self.request.query_params.get('type')
        if type_param == 'national':
            return NationalScoreLineSerializer
        elif type_param == 'school':
            return SchoolScoreLineSerializer
        return ScoreLineSerializer
    
    @action(detail=False, methods=['get'])
    def national(self, request):
        """获取国家线"""
        # 筛选年份和区域类型
        year = request.query_params.get('year')
        region_type = request.query_params.get('region_type')
        subject = request.query_params.get('subject')
        
        queryset = ScoreLine.objects.filter(type='national')
        if year:
            queryset = queryset.filter(year=year)
        if region_type:
            queryset = queryset.filter(region_type=region_type)
        if subject:
            queryset = queryset.filter(subject=subject)
            
        serializer = NationalScoreLineSerializer(queryset, many=True)
        return Response(serializer.data)


class AdmissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    录取信息视图集
    """
    queryset = Admission.objects.all()
    serializer_class = AdmissionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['year', 'school', 'major']
    search_fields = ['student_name', 'school__name', 'major__name']
    ordering_fields = ['year', 'score_total']
    ordering = ['-score_total'] 