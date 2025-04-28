from django.contrib import admin
from .models import AnnouncementCategory, Announcement


class AnnouncementCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']


class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'category', 'created_at']
    search_fields = ['title', 'content']
    date_hierarchy = 'created_at'
    fields = ('title', 'category', 'content', 'link', 'is_active')


admin.site.register(AnnouncementCategory, AnnouncementCategoryAdmin)
admin.site.register(Announcement, AnnouncementAdmin) 