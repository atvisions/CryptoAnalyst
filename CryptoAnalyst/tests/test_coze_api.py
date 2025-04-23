import unittest
from django.test import TestCase
import requests
import json
import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class CozeAPITest(TestCase):
    """测试 Coze API 连接"""

    def setUp(self):
        """测试前的准备工作"""
        # 加载环境变量
        load_dotenv()
        
        # 从环境变量获取配置
        self.api_url = "https://api.coze.cn/api/v3/chat/completions"
        self.api_key = os.getenv('COZE_API_KEY')
        self.bot_id = os.getenv('COZE_BOT_ID')
        
        # 验证必要的配置
        if not self.api_key:
            raise ValueError("COZE_API_KEY 环境变量未设置")
        if not self.bot_id:
            raise ValueError("COZE_BOT_ID 环境变量未设置")

    def test_coze_api_connection(self):
        """测试 Coze API 连接是否正常"""
        try:
            # 准备请求头
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 准备请求体 - 最简单的格式
            payload = {
                "bot_id": self.bot_id,
                "messages": [
                    {
                        "role": "user",
                        "content": "hi"
                    }
                ]
            }
            
            # 打印请求信息
            print(f"\n=== 请求信息 ===")
            print(f"URL: {self.api_url}")
            print(f"Headers: {json.dumps(headers, ensure_ascii=False)}")
            print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
            
            # 发送请求
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            # 打印响应信息
            print(f"\n=== 响应信息 ===")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            
            # 验证响应
            self.assertEqual(response.status_code, 200)
            response_data = response.json()
            
            # 验证响应格式
            self.assertIn('choices', response_data)
            self.assertTrue(len(response_data['choices']) > 0)
            self.assertIn('message', response_data['choices'][0])
            self.assertIn('content', response_data['choices'][0]['message'])
            
        except Exception as e:
            print(f"\n=== 错误信息 ===")
            print(f"Error: {str(e)}")
            raise 