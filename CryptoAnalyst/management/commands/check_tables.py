from django.core.management.base import BaseCommand
from django.db import connection
from CryptoAnalyst.models import User, VerificationCode

class Command(BaseCommand):
    help = '查看数据库表结构'

    def handle(self, *args, **options):
        # 查看用户表结构
        self.stdout.write('=== 用户表结构 ===')
        with connection.cursor() as cursor:
            cursor.execute("DESCRIBE CryptoAnalyst_user")
            columns = cursor.fetchall()
            for column in columns:
                self.stdout.write(f"字段名: {column[0]}, 类型: {column[1]}, 是否可空: {column[2]}, 键: {column[3]}, 默认值: {column[4]}, 额外信息: {column[5]}")

        # 查看验证码表结构
        self.stdout.write('\n=== 验证码表结构 ===')
        with connection.cursor() as cursor:
            cursor.execute("DESCRIBE CryptoAnalyst_verificationcode")
            columns = cursor.fetchall()
            for column in columns:
                self.stdout.write(f"字段名: {column[0]}, 类型: {column[1]}, 是否可空: {column[2]}, 键: {column[3]}, 默认值: {column[4]}, 额外信息: {column[5]}") 