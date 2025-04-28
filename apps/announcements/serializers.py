from rest_framework import serializers
from .models import AnnouncementCategory, Announcement


class AnnouncementCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnouncementCategory
        fields = ['id', 'name', 'description']


class AnnouncementSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default='')
    
    class Meta:
        model = Announcement
        fields = ['id', 'title', 'category', 'category_name', 'content', 'link', 
                 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at'] 