from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    SchoolViewSet, DepartmentViewSet, MajorViewSet, 
    ScoreLineViewSet, AdmissionViewSet
)

# 创建路由器并注册视图集
router = DefaultRouter()
router.register(r'schools', SchoolViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'majors', MajorViewSet)
router.register(r'score-lines', ScoreLineViewSet)
router.register(r'admissions', AdmissionViewSet)

urlpatterns = [
    path('', include(router.urls)),
] 