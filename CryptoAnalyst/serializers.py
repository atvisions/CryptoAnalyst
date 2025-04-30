from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from .models import User, VerificationCode
from datetime import datetime, timezone

class UserSerializer(serializers.ModelSerializer):
    """用户序列化器"""
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class RegisterSerializer(serializers.Serializer):
    """注册序列化器"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    code = serializers.CharField(min_length=6, max_length=6)
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("该邮箱已被注册")
        return value
    
    def validate_code(self, value):
        email = self.initial_data.get('email')
        verification = VerificationCode.objects.filter(
            email=email,
            code=value,
            is_used=False,
            expires_at__gt=datetime.now(timezone.utc)
        ).first()
        
        if not verification:
            raise serializers.ValidationError("验证码无效或已过期")
        return value

class LoginSerializer(serializers.Serializer):
    """登录序列化器"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class SendVerificationCodeSerializer(serializers.Serializer):
    """发送验证码序列化器"""
    email = serializers.EmailField()
    
    def validate_email(self, value):
        # 检查是否已经发送过未使用的验证码
        existing_code = VerificationCode.objects.filter(
            email=value,
            is_used=False,
            expires_at__gt=datetime.now(timezone.utc)
        ).first()
        
        if existing_code:
            # 如果存在未过期的验证码，删除它
            existing_code.delete()
            
        # 检查邮箱是否已注册
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("该邮箱已被注册")
            
        return value

class TokenRefreshSerializer(serializers.Serializer):
    """Token刷新序列化器"""
    token = serializers.CharField(read_only=True)

    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError('认证失败')
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        # 删除旧token
        Token.objects.filter(user=user).delete()
        # 创建新token
        token = Token.objects.create(user=user)
        return {'token': token.key} 