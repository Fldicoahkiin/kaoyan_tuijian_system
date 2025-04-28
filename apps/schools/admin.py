from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import School, Department, Major, Subject, ScoreLine, Admission


class DepartmentInline(admin.TabularInline):
    model = Department
    extra = 1


class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'level', 'cs_level', 'region', 'region_type', 'admission_count', 'custom_test', 'favorite_count']
    list_filter = ['level', 'cs_level', 'region', 'region_type', 'custom_test']
    search_fields = ['name', 'description']
    inlines = [DepartmentInline]
    fieldsets = (
        (None, {'fields': ('name', 'level', 'cs_level', 'region', 'region_type', 'logo')}),
        (_('招生信息'), {'fields': ('admission_count', 'custom_test')}),
        (_('详细信息'), {'fields': ('description',)}),
    )
    
    def favorite_count(self, obj):
        return obj.favorite_count
    favorite_count.short_description = _('收藏数')


class MajorInline(admin.TabularInline):
    model = Major
    extra = 1


class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'get_major_count']
    list_filter = ['school']
    search_fields = ['name', 'school__name']
    inlines = [MajorInline]
    
    def get_major_count(self, obj):
        return obj.majors.count()
    get_major_count.short_description = _('专业数量')


class SubjectInline(admin.TabularInline):
    model = Subject
    extra = 1


class MajorAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'department', 'get_school', 'admission_count']
    list_filter = ['department__school', 'department']
    search_fields = ['name', 'code', 'department__name', 'department__school__name']
    inlines = [SubjectInline]
    
    def get_school(self, obj):
        return obj.department.school
    get_school.short_description = _('学校')
    get_school.admin_order_field = 'department__school__name'


class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'major', 'get_school', 'is_custom']
    list_filter = ['is_custom', 'major__department__school']
    search_fields = ['name', 'major__name', 'major__department__school__name']
    
    def get_school(self, obj):
        return obj.major.department.school
    get_school.short_description = _('学校')
    get_school.admin_order_field = 'major__department__school__name'


class ScoreLineAdmin(admin.ModelAdmin):
    list_display = ['year', 'get_display_name', 'type', 'subject', 'score']
    list_filter = ['year', 'type', 'subject', 'region_type', 'school']
    search_fields = ['school__name', 'major__name']
    
    def get_display_name(self, obj):
        if obj.type == 'national':
            return f"{obj.get_region_type_display()}国家线"
        else:
            return f"{obj.school.name} {obj.major.name if obj.major else ''}"
    get_display_name.short_description = _('名称')


class AdmissionAdmin(admin.ModelAdmin):
    list_display = ['year', 'school', 'major', 'student_name', 'score_total']
    list_filter = ['year', 'school', 'major__department']
    search_fields = ['student_name', 'school__name', 'major__name']


admin.site.register(School, SchoolAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Major, MajorAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(ScoreLine, ScoreLineAdmin)
admin.site.register(Admission, AdmissionAdmin) 