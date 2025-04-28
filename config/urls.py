from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.documentation import include_docs_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('apps.users.urls')),
    path('api/schools/', include('apps.schools.urls')),
    path('api/visualization/', include('apps.visualization.urls')),
    path('api/recommendation/', include('apps.recommendation.urls')),
    path('api/announcements/', include('apps.announcements.urls')),
    path('api/docs/', include_docs_urls(title='考研推荐系统API文档')),
]

# 在开发环境中添加媒体文件URL
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) 