from django.core.management.base import BaseCommand
from CryptoAnalyst.models import User, VerificationCode
from datetime import datetime, timezone

class Command(BaseCommand):
    help = '检查用户和验证码数据'

    def handle(self, *args, **options):
        # 检查用户
        self.stdout.write('=== 用户数据 ===')
        users = User.objects.all()
        if users:
            for user in users:
                self.stdout.write(f"ID: {user.id}, 邮箱: {user.email}, 用户名: {user.username}, 创建时间: {user.created_at}")
        else:
            self.stdout.write('没有用户数据')

        # 检查验证码
        self.stdout.write('\n=== 验证码数据 ===')
        codes = VerificationCode.objects.all()
        if codes:
            for code in codes:
                self.stdout.write(f"邮箱: {code.email}, 验证码: {code.code}, 是否使用: {code.is_used}, 过期时间: {code.expires_at}")
        else:
            self.stdout.write('没有验证码数据') 