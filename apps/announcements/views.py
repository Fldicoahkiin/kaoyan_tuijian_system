from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import AnnouncementCategory, Announcement
from .serializers import AnnouncementCategorySerializer, AnnouncementSerializer


class AnnouncementCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    公告分类视图集 (只读)
    """
    queryset = AnnouncementCategory.objects.all()
    serializer_class = AnnouncementCategorySerializer
    permission_classes = [permissions.AllowAny] # 分类信息通常公开
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class AnnouncementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    公告通知视图集 (只读)
    """
    queryset = Announcement.objects.filter(is_active=True)
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.AllowAny] # 公告信息通常公开
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at'] 