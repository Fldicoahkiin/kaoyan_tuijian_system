from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from .models import FavoriteSchool
from .serializers import (
    UserSerializer, UserDetailSerializer, UserCreateSerializer,
    ChangePasswordSerializer, FavoriteSchoolSerializer, FavoriteSchoolDetailSerializer
)
from apps.schools.models import School

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """
    用户视图集
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action == 'retrieve':
            return UserDetailSerializer
        return UserSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return super().get_permissions()
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """获取当前登录用户的信息"""
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put'], serializer_class=ChangePasswordSerializer)
    def change_password(self, request):
        """修改密码"""
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            # 检查旧密码是否正确
            if not user.check_password(serializer.data.get('old_password')):
                return Response({'old_password': ['旧密码不正确']}, 
                                status=status.HTTP_400_BAD_REQUEST)
            
            # 设置新密码
            user.set_password(serializer.data.get('new_password'))
            user.save()
            return Response({'status': '密码已成功修改'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def favorites(self, request):
        """获取当前用户收藏的学校列表"""
        favorites = FavoriteSchool.objects.filter(user=request.user)
        serializer = FavoriteSchoolDetailSerializer(favorites, many=True)
        return Response(serializer.data)


class CustomAuthToken(ObtainAuthToken):
    """
    自定义令牌获取视图
    """
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                          context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'email': user.email
        })


class FavoriteSchoolView(generics.CreateAPIView, generics.DestroyAPIView):
    """
    添加/移除收藏学校
    """
    serializer_class = FavoriteSchoolSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        school_id = self.kwargs.get('school_id')
        school = get_object_or_404(School, id=school_id)
        return get_object_or_404(FavoriteSchool, user=self.request.user, school=school)
    
    def create(self, request, *args, **kwargs):
        school_id = kwargs.get('school_id')
        school = get_object_or_404(School, id=school_id)
        
        # 检查是否已收藏
        if FavoriteSchool.objects.filter(user=request.user, school=school).exists():
            return Response({'detail': '该学校已在收藏列表中'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        favorite = FavoriteSchool(user=request.user, school=school)
        favorite.save()
        serializer = self.get_serializer(favorite)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT) 