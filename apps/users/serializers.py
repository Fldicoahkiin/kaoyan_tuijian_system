from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import FavoriteSchool

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'avatar', 'phone',
                 'education_background', 'target_major', 'target_location',
                 'expected_score', 'target_school_level']
        read_only_fields = ['id']


class UserDetailSerializer(UserSerializer):
    """更详细的用户信息序列化器"""
    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['date_joined', 'last_login']


class UserCreateSerializer(serializers.ModelSerializer):
    """用于用户注册的序列化器"""
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm']
    
    def validate(self, data):
        # 验证两次密码是否一致
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "两次输入的密码不一致"})
        return data
    
    def create(self, validated_data):
        # 移除password_confirm字段
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """修改密码的序列化器"""
    old_password = serializers.CharField(required=True, style={'input_type': 'password'})
    new_password = serializers.CharField(required=True, style={'input_type': 'password'})
    new_password_confirm = serializers.CharField(required=True, style={'input_type': 'password'})
    
    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": "两次输入的新密码不一致"})
        return data


class FavoriteSchoolSerializer(serializers.ModelSerializer):
    """用户收藏学校的序列化器"""
    class Meta:
        model = FavoriteSchool
        fields = ['id', 'school', 'created_at']
        read_only_fields = ['id', 'created_at']


class FavoriteSchoolDetailSerializer(serializers.ModelSerializer):
    """带有学校详细信息的收藏序列化器"""
    from apps.schools.serializers import SchoolSerializer
    school = SchoolSerializer(read_only=True)
    
    class Meta:
        model = FavoriteSchool
        fields = ['id', 'school', 'created_at']
        read_only_fields = ['id', 'created_at'] 