from typing import Dict, Any
import os

class Config:
    """配置管理类"""
    # API 密钥配置
    MORALIS_API_KEY = os.getenv("MORALIS_API_KEY", "")
    ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY", "")

    # 价格 API 配置
    CRYPTOCOMPARE_API_URL = os.getenv("CRYPTOCOMPARE_API_URL", "https://min-api.cryptocompare.com/data/price")

    # EVM 链配置
    EVM_CONFIGS: Dict[str, Dict[str, Any]] = {
        "ETH": {
            "rpc_url": f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "ETH_GOERLI": {
            "rpc_url": f"https://eth-goerli.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "ETH_SEPOLIA": {
            "rpc_url": f"https://eth-sepolia.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "BSC": {
            "rpc_url": f"https://binance.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "BSC_TESTNET": {
            "rpc_url": f"https://bsc-testnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "MATIC": {
            "rpc_url": f"https://polygon-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "MATIC_MUMBAI": {
            "rpc_url": f"https://polygon-mumbai.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "ARB": {
            "rpc_url": f"https://arb-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "ARB_GOERLI": {
            "rpc_url": f"https://arb-goerli.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "OP": {
            "rpc_url": f"https://opt-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "OP_GOERLI": {
            "rpc_url": f"https://opt-goerli.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "AVAX": {
            "rpc_url": f"https://avax-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "AVAX_FUJI": {
            "rpc_url": f"https://avax-fuji.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "FTM": {
            "rpc_url": f"https://fantom-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "FTM_TESTNET": {
            "rpc_url": f"https://fantom-testnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "CRO": {
            "rpc_url": f"https://cronos-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "CRO_TESTNET": {
            "rpc_url": f"https://cronos-testnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "ZKSYNC": {
            "rpc_url": f"https://zksync-era-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "ZKSYNC_TESTNET": {
            "rpc_url": f"https://zksync-era-testnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "LINEA": {
            "rpc_url": f"https://linea-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "LINEA_GOERLI": {
            "rpc_url": f"https://linea-goerli.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "MANTA": {
            "rpc_url": f"https://manta-pacific.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "MANTA_TESTNET": {
            "rpc_url": f"https://manta-testnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "BASE": {
            "rpc_url": f"https://base-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "BASE_SEPOLIA": {
            "rpc_url": f"https://base-sepolia.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "SCROLL": {
            "rpc_url": f"https://scroll-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "SCROLL_SEPOLIA": {
            "rpc_url": f"https://scroll-sepolia.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "GNOSIS": {
            "rpc_url": f"https://gnosis-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "GNOSIS_CHIADO": {
            "rpc_url": f"https://gnosis-chiado.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "CELO": {
            "rpc_url": f"https://celo-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "CELO_ALFAJORES": {
            "rpc_url": f"https://celo-alfajores.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "CELO_BAKLAVA": {
            "rpc_url": f"https://celo-baklava.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "METIS": {
            "rpc_url": f"https://metis-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "OPBNB": {
            "rpc_url": f"https://opbnb-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "OPBNB_TESTNET": {
            "rpc_url": f"https://opbnb-testnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        }
    }

    # Solana 链配置
    SOLANA_CONFIGS: Dict[str, Dict[str, Any]] = {
        "SOL": {
            "rpc_url": f"https://solana-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://solana-gateway.moralis.io"
        },
        "SOL_DEVNET": {
            "rpc_url": f"https://solana-devnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}",
            "moralis_url": "https://solana-gateway.moralis.io"
        },
        "SOL_TESTNET": {
            "rpc_url": "https://api.testnet.solana.com",
            "moralis_url": "https://solana-gateway.moralis.io"
        }
    }

    # Kadena 链配置
    # 注意: Kadena 有两个不同的 "chain" 概念:
    # 1. 钱包模型中的 "chain" 字段，表示区块链类型，如 "KDA", "KDA_TESTNET"
    # 2. Kadena 平行链 ID，范围为 0-19，用于查询特定链上的余额
    KADENA_CONFIGS: Dict[str, Dict[str, Any]] = {
        "KDA": {  # 这是钱包模型中的 "chain" 字段值
            "rpc_url": "https://api.chainweb.com",
            "kadena_chain_id": "0",  # 这是 Kadena 平行链 ID，默认为 0
            "network_id": "mainnet01",
            "api_version": "chainweb/0.0/mainnet01/chain/0",  # 这里的 "chain/0" 表示平行链 ID
            "nodes": [
                "https://api.chainweb.com",
                "https://us1.chainweb.com",
                "https://us2.chainweb.com",
                "https://eu1.chainweb.com",
                "https://eu2.chainweb.com"
            ],
            "multi_chain": True,  # 标记该链是多链架构
            "chain_count": 20,  # Kadena 有 20 个平行链（0-19）
            "kadena_chain_ids": list(range(20))  # 所有 Kadena 平行链 ID的列表
        },
        "KDA_TESTNET": {  # 这是钱包模型中的 "chain" 字段值
            "rpc_url": "https://api.testnet.chainweb.com",
            "kadena_chain_id": "0",  # 这是 Kadena 平行链 ID，默认为 0
            "network_id": "testnet04",
            "api_version": "chainweb/0.0/testnet04/chain/0",  # 这里的 "chain/0" 表示平行链 ID
            "nodes": [
                "https://api.testnet.chainweb.com",
                "https://us1.testnet.chainweb.com",
                "https://us2.testnet.chainweb.com",
                "https://eu1.testnet.chainweb.com",
                "https://eu2.testnet.chainweb.com"
            ],
            "multi_chain": True,  # 标记该链是多链架构
            "chain_count": 20,  # Kadena 有 20 个平行链（0-19）
            "kadena_chain_ids": list(range(20))  # 所有 Kadena 平行链 ID的列表
        }
    }

    @classmethod
    def get_evm_config(cls, chain: str) -> Dict[str, Any]:
        """获取 EVM 链配置"""
        if chain not in cls.EVM_CONFIGS:
            raise ValueError(f"不支持的 EVM 链类型: {chain}")
        return cls.EVM_CONFIGS[chain]

    @classmethod
    def get_solana_config(cls, chain: str) -> Dict[str, Any]:
        """获取 Solana 链配置"""
        if chain not in cls.SOLANA_CONFIGS:
            raise ValueError(f"不支持的 Solana 链类型: {chain}")
        return cls.SOLANA_CONFIGS[chain]

    @classmethod
    def get_kadena_config(cls, chain: str) -> Dict[str, Any]:
        """获取 Kadena 链配置"""
        if chain not in cls.KADENA_CONFIGS:
            raise ValueError(f"不支持的 Kadena 链类型: {chain}")
        return cls.KADENA_CONFIGS[chain]