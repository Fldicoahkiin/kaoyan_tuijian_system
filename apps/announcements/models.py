from django.db import models
from django.utils.translation import gettext_lazy as _


class AnnouncementCategory(models.Model):
    """
    公告分类模型
    """
    name = models.CharField(verbose_name=_('分类名称'), max_length=50, unique=True)
    description = models.TextField(verbose_name=_('分类描述'), blank=True)
    
    class Meta:
        verbose_name = _('公告分类')
        verbose_name_plural = verbose_name
        
    def __str__(self):
        return self.name


class Announcement(models.Model):
    """
    公告内容模型
    """
    category = models.ForeignKey(AnnouncementCategory, on_delete=models.SET_NULL, 
                                 related_name='announcements', verbose_name=_('公告分类'),
                                 null=True, blank=True)
    title = models.CharField(verbose_name=_('公告标题'), max_length=200)
    content = models.TextField(verbose_name=_('公告内容'))
    link = models.URLField(verbose_name=_('相关链接'), blank=True, null=True)
    is_active = models.BooleanField(verbose_name=_('是否激活'), default=True)
    created_at = models.DateTimeField(verbose_name=_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name=_('更新时间'), auto_now=True)
    
    class Meta:
        verbose_name = _('公告通知')
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        
    def __str__(self):
        return self.title 