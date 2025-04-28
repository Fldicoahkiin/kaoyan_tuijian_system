from django.db import models
from django.utils.translation import gettext_lazy as _


class School(models.Model):
    """
    学校模型
    """
    SCHOOL_LEVEL_CHOICES = (
        ('985', '985'),
        ('211', '211'),
        ('double_first_class', '双一流'),
        ('general', '一般'),
    )
    
    CS_LEVEL_CHOICES = (
        ('A+', 'A+'),
        ('A', 'A'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B', 'B'),
        ('B-', 'B-'),
        ('C+', 'C+'),
        ('C', 'C'),
        ('C-', 'C-'),
        ('none', '无等级'),
    )
    
    REGION_TYPE_CHOICES = (
        ('A', 'A区'),
        ('B', 'B区'),
    )
    
    name = models.CharField(verbose_name=_('学校名称'), max_length=100)
    level = models.CharField(verbose_name=_('学校等级'), max_length=20, choices=SCHOOL_LEVEL_CHOICES)
    cs_level = models.CharField(verbose_name=_('计算机等级'), max_length=10, choices=CS_LEVEL_CHOICES)
    region = models.CharField(verbose_name=_('所在地区'), max_length=50)
    region_type = models.CharField(verbose_name=_('区域类型'), max_length=2, choices=REGION_TYPE_CHOICES)
    logo = models.ImageField(verbose_name=_('学校logo'), upload_to='school_logos/', blank=True, null=True)
    description = models.TextField(verbose_name=_('学校简介'), blank=True)
    admission_count = models.IntegerField(verbose_name=_('24年招生人数'), default=0)
    custom_test = models.BooleanField(verbose_name=_('是否自命题'), default=False)
    created_at = models.DateTimeField(verbose_name=_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name=_('更新时间'), auto_now=True)
    
    class Meta:
        verbose_name = _('学校')
        verbose_name_plural = verbose_name
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def favorite_count(self):
        """获取收藏数量"""
        return self.favorited_by.count()


class Department(models.Model):
    """
    院系模型
    """
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='departments', verbose_name=_('所属学校'))
    name = models.CharField(verbose_name=_('院系名称'), max_length=100)
    description = models.TextField(verbose_name=_('院系介绍'), blank=True)
    
    class Meta:
        verbose_name = _('院系')
        verbose_name_plural = verbose_name
        unique_together = ('school', 'name')
    
    def __str__(self):
        return f"{self.school.name} - {self.name}"


class Major(models.Model):
    """
    专业模型
    """
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='majors', verbose_name=_('所属院系'))
    name = models.CharField(verbose_name=_('专业名称'), max_length=100)
    code = models.CharField(verbose_name=_('专业代码'), max_length=20)
    admission_count = models.IntegerField(verbose_name=_('招生人数'), default=0)
    description = models.TextField(verbose_name=_('专业介绍'), blank=True)
    
    class Meta:
        verbose_name = _('专业')
        verbose_name_plural = verbose_name
        unique_together = ('department', 'code')
    
    def __str__(self):
        return f"{self.department.school.name} - {self.department.name} - {self.name}"


class Subject(models.Model):
    """
    考试科目模型
    """
    major = models.ForeignKey(Major, on_delete=models.CASCADE, related_name='subjects', verbose_name=_('所属专业'))
    name = models.CharField(verbose_name=_('科目名称'), max_length=100)
    is_custom = models.BooleanField(verbose_name=_('是否自命题'), default=False)
    description = models.TextField(verbose_name=_('科目说明'), blank=True)
    
    class Meta:
        verbose_name = _('考试科目')
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.major.name} - {self.name}"


class ScoreLine(models.Model):
    """
    分数线模型（国家线和院校复试线）
    """
    TYPE_CHOICES = (
        ('national', '国家线'),
        ('school', '院校复试线'),
    )
    
    SUBJECT_CHOICES = (
        ('total', '总分'),
        ('politics', '政治'),
        ('english1', '英语一'),
        ('english2', '英语二'),
        ('math1', '数学一'),
        ('math2', '数学二'),
        ('professional', '专业课'),
    )
    
    year = models.IntegerField(verbose_name=_('年份'))
    region_type = models.CharField(verbose_name=_('区域类型'), max_length=2, choices=School.REGION_TYPE_CHOICES, null=True, blank=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='score_lines', 
                              verbose_name=_('学校'), null=True, blank=True)
    major = models.ForeignKey(Major, on_delete=models.CASCADE, related_name='score_lines', 
                             verbose_name=_('专业'), null=True, blank=True)
    type = models.CharField(verbose_name=_('线类型'), max_length=10, choices=TYPE_CHOICES)
    subject = models.CharField(verbose_name=_('科目'), max_length=20, choices=SUBJECT_CHOICES)
    score = models.IntegerField(verbose_name=_('分数'))
    
    class Meta:
        verbose_name = _('分数线')
        verbose_name_plural = verbose_name
        unique_together = ('year', 'school', 'major', 'type', 'subject')
    
    def __str__(self):
        if self.type == 'national':
            return f"{self.year}年{self.get_region_type_display()}国家线-{self.get_subject_display()}:{self.score}"
        else:
            return f"{self.year}年{self.school.name}{self.major.name if self.major else ''}复试线-{self.get_subject_display()}:{self.score}"


class Admission(models.Model):
    """
    录取信息模型
    """
    year = models.IntegerField(verbose_name=_('年份'))
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='admissions', verbose_name=_('学校'))
    major = models.ForeignKey(Major, on_delete=models.CASCADE, related_name='admissions', verbose_name=_('专业'))
    student_name = models.CharField(verbose_name=_('学生姓名'), max_length=50, blank=True, null=True)
    score_total = models.IntegerField(verbose_name=_('总分'), null=True, blank=True)
    score_politics = models.IntegerField(verbose_name=_('政治分数'), null=True, blank=True)
    score_english = models.IntegerField(verbose_name=_('英语分数'), null=True, blank=True)
    score_math = models.IntegerField(verbose_name=_('数学分数'), null=True, blank=True)
    score_professional = models.IntegerField(verbose_name=_('专业课分数'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('录取信息')
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['year', 'school', 'major']),
        ]
    
    def __str__(self):
        if self.student_name:
            return f"{self.year}年{self.school.name}{self.major.name}-{self.student_name}({self.score_total}分)"
        else:
            return f"{self.year}年{self.school.name}{self.major.name}-{self.score_total}分" 