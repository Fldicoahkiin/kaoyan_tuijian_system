from rest_framework import views, permissions
from rest_framework.response import Response
from rest_framework import status

from .serializers import RecommendationInputSerializer, RecommendedSchoolSerializer
from .services import get_recommended_schools


class RecommendationView(views.APIView):
    """
    院校推荐视图
    """
    permission_classes = [permissions.IsAuthenticated] # 推荐功能通常需要登录
    
    def post(self, request):
        """
        接收用户偏好，返回推荐结果
        """
        input_serializer = RecommendationInputSerializer(data=request.data)
        if input_serializer.is_valid():
            preferences = input_serializer.validated_data
            
            # 调用推荐服务获取结果
            recommended_schools_data = get_recommended_schools(preferences)
            
            # 序列化推荐结果
            output_serializer = RecommendedSchoolSerializer(recommended_schools_data, many=True)
            
            return Response(output_serializer.data)
        else:
            return Response(input_serializer.errors, status=status.HTTP_400_BAD_REQUEST) 