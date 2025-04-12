import json
from django.core.management.base import BaseCommand
from wallets.models import Chain, Device
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Load chain configurations from JSON file into database'

    def handle(self, *args, **options):
        # 获取配置文件路径
        config_path = os.path.join(settings.BASE_DIR, 'wallets', 'config', 'chains.json')
        
        try:
            # 读取配置文件
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # 获取或创建默认设备
            default_device, _ = Device.objects.get_or_create(device_id='default')
            
            # 处理每个链的配置
            for chain_config in config['chains']:
                # 更新或创建链记录
                Chain.objects.update_or_create(
                    device=default_device,
                    chain=chain_config['code'],
                    defaults={
                        'is_active': chain_config['is_active'],
                        'is_selected': False  # 默认不选中
                    }
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully processed chain: {chain_config["code"]}')
                )
            
            self.stdout.write(self.style.SUCCESS('Successfully loaded all chain configurations'))
            
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'Configuration file not found at: {config_path}')
            )
        except json.JSONDecodeError:
            self.stdout.write(
                self.style.ERROR('Invalid JSON format in configuration file')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error loading chain configurations: {str(e)}')
            ) 