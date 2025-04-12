import json
import os
from django.conf import settings

# 读取 chains.json 文件
CHAINS_CONFIG_PATH = os.path.join(settings.BASE_DIR, 'config', 'init_data', 'chains.json')
with open(CHAINS_CONFIG_PATH, 'r') as f:
    CHAINS_CONFIG = json.load(f)

# 从配置文件生成 EVM_CHAINS 列表
EVM_CHAINS = [chain['code'] for chain in CHAINS_CONFIG['chains'] if chain['type'] == 'evm']

# 从配置文件生成 CHAIN_NAMES 映射
CHAIN_NAMES = {chain['code']: chain['name'] for chain in CHAINS_CONFIG['chains']}

# 从配置文件生成 CHAIN_LOGOS 映射
CHAIN_LOGOS = {chain['code']: chain['logo'] for chain in CHAINS_CONFIG['chains']}

# 从配置文件生成 CHAIN_TYPES 映射
CHAIN_TYPES = {chain['code']: chain['type'].upper() for chain in CHAINS_CONFIG['chains']}

# 从配置文件生成 CHAIN_CHOICES
CHAIN_CHOICES = [(chain['code'], chain['name']) for chain in CHAINS_CONFIG['chains']]

# 链名称映射
CHAIN_NAMES = {
    'ETH': 'Ethereum',
    'BSC': 'BNB Chain',
    'MATIC': 'Polygon',
    'AVAX': 'Avalanche',
    'BASE': 'Base',
    'OP': 'Optimism',
    'ARB': 'Arbitrum',
    'FTM': 'Fantom',
    'CRO': 'Cronos',
    'ZKSYNC': 'zkSync Era',
    'LINEA': 'Linea',
    'SCROLL': 'Scroll',
    'MANTA': 'Manta',
    'SOL': 'Solana',
    'KDA': 'Kadena',
} 