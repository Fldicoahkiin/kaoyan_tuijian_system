from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    自定义用户模型
    """
    EDUCATION_CHOICES = (
        ('bachelor', '本科'),
        ('master', '硕士'),
        ('doctor', '博士'),
        ('other', '其他'),
    )
    
    # 扩展基本信息
    avatar = models.ImageField(verbose_name=_('头像'), upload_to='avatars/', blank=True, null=True)
    phone = models.CharField(verbose_name=_('手机号'), max_length=11, blank=True)
    
    # 考研意向相关信息
    education_background = models.CharField(
        verbose_name=_('学历背景'),
        max_length=20,
        choices=EDUCATION_CHOICES,
        blank=True,
    )
    target_major = models.CharField(verbose_name=_('目标专业'), max_length=100, blank=True)
    target_location = models.CharField(verbose_name=_('目标地区'), max_length=100, blank=True)
    expected_score = models.IntegerField(verbose_name=_('预期分数'), default=0)
    target_school_level = models.CharField(verbose_name=_('期望院校层次'), max_length=20, blank=True)
    
    class Meta:
        verbose_name = _('用户')
        verbose_name_plural = verbose_name
        
    def __str__(self):
        return self.username


class FavoriteSchool(models.Model):
    """
    用户收藏的学校
    """
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='favorites', verbose_name=_('用户'))
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='favorited_by', verbose_name=_('学校'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('收藏时间'))
    
    class Meta:
        verbose_name = _('收藏学校')
        verbose_name_plural = verbose_name
        unique_together = ('user', 'school')
        
    def __str__(self):
        return f"{self.user.username} 收藏了 {self.school.name}" 