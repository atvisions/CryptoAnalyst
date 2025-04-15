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
            "rpc_url": "https://bsc-dataseed.binance.org/",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "BSC_TESTNET": {
            "rpc_url": "https://data-seed-prebsc-1-s1.binance.org:8545/",
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
            "rpc_url": "https://api.avax.network/ext/bc/C/rpc",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "AVAX_FUJI": {
            "rpc_url": "https://api.avax-test.network/ext/bc/C/rpc",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "FTM": {
            "rpc_url": "https://rpc.ftm.tools/",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "FTM_TESTNET": {
            "rpc_url": "https://rpc.testnet.fantom.network/",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "CRO": {
            "rpc_url": "https://evm.cronos.org",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "CRO_TESTNET": {
            "rpc_url": "https://evm-t3.cronos.org",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "ZKSYNC": {
            "rpc_url": "https://mainnet.era.zksync.io",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "ZKSYNC_TESTNET": {
            "rpc_url": "https://testnet.era.zksync.dev",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "LINEA": {
            "rpc_url": "https://rpc.linea.build",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "LINEA_GOERLI": {
            "rpc_url": "https://rpc.goerli.linea.build",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "MANTA": {
            "rpc_url": "https://pacific.manta.network/http",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "MANTA_TESTNET": {
            "rpc_url": "https://pacific-testnet.manta.network/http",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "BASE": {
            "rpc_url": "https://mainnet.base.org",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        },
        "BASE_SEPOLIA": {
            "rpc_url": "https://sepolia.base.org",
            "moralis_url": "https://deep-index.moralis.io/api/v2"
        }
    }

    # Solana 链配置
    SOLANA_CONFIGS: Dict[str, Dict[str, Any]] = {
        "SOL": {
            "rpc_url": "https://api.mainnet-beta.solana.com",
            "moralis_url": "https://solana-gateway.moralis.io"
        },
        "SOL_DEVNET": {
            "rpc_url": "https://api.devnet.solana.com",
            "moralis_url": "https://solana-gateway.moralis.io"
        },
        "SOL_TESTNET": {
            "rpc_url": "https://api.testnet.solana.com",
            "moralis_url": "https://solana-gateway.moralis.io"
        }
    }

    # Kadena 链配置
    KADENA_CONFIGS: Dict[str, Dict[str, Any]] = {
        "KDA": {
            "rpc_url": "https://api.chainweb.com/openapi",
            "chain_id": "mainnet01",
            "network_id": "mainnet01",
            "api_version": "v1",
            "nodes": [
                "https://api.chainweb.com/openapi",
                "https://us1.chainweb.com/openapi",
                "https://us2.chainweb.com/openapi",
                "https://eu1.chainweb.com/openapi",
                "https://eu2.chainweb.com/openapi"
            ]
        },
        "KDA_TESTNET": {
            "rpc_url": "https://api.testnet.chainweb.com/openapi",
            "chain_id": "testnet04",
            "network_id": "testnet04",
            "api_version": "v1",
            "nodes": [
                "https://api.testnet.chainweb.com/openapi",
                "https://us1.testnet.chainweb.com/openapi",
                "https://us2.testnet.chainweb.com/openapi",
                "https://eu1.testnet.chainweb.com/openapi",
                "https://eu2.testnet.chainweb.com/openapi"
            ]
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