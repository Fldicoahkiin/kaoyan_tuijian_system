from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, FavoriteSchool


class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('个人信息'), {'fields': ('first_name', 'last_name', 'email', 'avatar', 'phone')}),
        (_('考研意向'), {
            'fields': ('education_background', 'target_major', 'target_location', 
                      'expected_score', 'target_school_level'),
        }),
        (_('权限'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('重要日期'), {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'expected_score']
    search_fields = ['username', 'email', 'first_name', 'last_name']


class FavoriteSchoolAdmin(admin.ModelAdmin):
    list_display = ['user', 'school', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'school__name']
    date_hierarchy = 'created_at'


admin.site.register(User, CustomUserAdmin)
admin.site.register(FavoriteSchool, FavoriteSchoolAdmin) 