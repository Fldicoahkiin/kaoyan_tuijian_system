from rest_framework import views, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes

from apps.announcements.models import Announcement
from apps.announcements.serializers import AnnouncementSerializer

from . import services


class DashboardDataView(views.APIView):
    """
    获取首页仪表盘数据的视图
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        # 获取学校列表数据
        school_list = services.get_school_list_data()
        
        # 获取国家线总分走势
        national_score_trend = services.get_national_score_trend_data()
        
        # 获取政治走势
        politics_trend = services.get_politics_score_trend_data()
        
        # 获取英语和数学走势
        english_math_trend = services.get_english_math_score_trend_data()
        
        # 获取自命题与统考比例
        test_type_ratio = services.get_school_test_type_data()
        
        # 获取公告信息
        announcements = Announcement.objects.filter(is_active=True).order_by('-created_at')[:5]
        announcement_serializer = AnnouncementSerializer(announcements, many=True)
        
        # 组合所有数据
        response_data = {
            'school_list': list(school_list),
            'national_score_trend': national_score_trend,
            'politics_trend': politics_trend,
            'english_math_trend': english_math_trend,
            'test_type_ratio': test_type_ratio,
            'announcements': announcement_serializer.data
        }
        
        return Response(response_data) 