from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import UserViewSet, CustomAuthToken, FavoriteSchoolView

# 创建路由器并注册视图集
router = DefaultRouter()
router.register(r'', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('login/', CustomAuthToken.as_view(), name='api_token_auth'),
    path('favorite/<int:school_id>/', FavoriteSchoolView.as_view(), name='favorite_school'),
] 