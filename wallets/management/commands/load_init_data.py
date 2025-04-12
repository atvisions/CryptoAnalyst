import json
from django.core.management.base import BaseCommand
from wallets.models import Chain
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Load initial data from JSON files into database'

    def handle(self, *args, **options):
        # 初始化 EVM 链
        evm_chains = [
            {
                'chain': 'ETH',
                'is_active': True,
                'logo': 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/ethereum/info/logo.png'
            },
            {
                'chain': 'BSC',
                'is_active': True,
                'logo': 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/binance/info/logo.png'
            },
            {
                'chain': 'MATIC',
                'is_active': True,
                'logo': 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/polygon/info/logo.png'
            },
            {
                'chain': 'ARB',
                'is_active': True,
                'logo': 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/arbitrum/info/logo.png'
            },
            {
                'chain': 'OP',
                'is_active': True,
                'logo': 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/optimism/info/logo.png'
            },
            {
                'chain': 'AVAX',
                'is_active': True,
                'logo': 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/avalanchex/info/logo.png'
            },
            {
                'chain': 'BASE',
                'is_active': True,
                'logo': 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/base/info/logo.png'
            }
        ]

        for chain_data in evm_chains:
            Chain.objects.update_or_create(
                chain=chain_data['chain'],
                defaults={
                    'is_active': chain_data['is_active'],
                    'logo': chain_data['logo']
                }
            )

        self.stdout.write(self.style.SUCCESS('Successfully initialized EVM chains'))

        # 获取配置文件目录
        config_dir = os.path.join(settings.BASE_DIR, 'config', 'init_data')
        
        try:
            # 加载链配置
            chains_path = os.path.join(config_dir, 'chains.json')
            if os.path.exists(chains_path):
                with open(chains_path, 'r') as f:
                    chains_config = json.load(f)
                
                # 处理每个链的配置
                for chain_config in chains_config['chains']:
                    # 更新或创建链记录
                    Chain.objects.update_or_create(
                        chain=chain_config['code'],
                        defaults={
                            'is_active': chain_config['is_active']
                        }
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully processed chain: {chain_config["code"]}')
                    )
            
            self.stdout.write(self.style.SUCCESS('Successfully loaded all initial data'))
            
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'Configuration file not found in: {config_dir}')
            )
        except json.JSONDecodeError:
            self.stdout.write(
                self.style.ERROR('Invalid JSON format in configuration file')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error loading initial data: {str(e)}')
            ) 