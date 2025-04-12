from typing import Dict, Any

class Config:
    """配置管理类"""
    
    # API 密钥配置
    MORALIS_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6IjZiNGRlNzlkLTc3YzctNGM1Ny04MDE4LTNmYzk1OGUxOTBiYSIsIm9yZ0lkIjoiNDI4MzE0IiwidXNlcklkIjoiNDQwNTc1IiwidHlwZUlkIjoiNDE4MjdjY2UtYmNhMi00YjZiLTgzMmUtMDE1ZWNmZGMwODZkIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE3MzgyNDY2NDYsImV4cCI6NDg5NDAwNjY0Nn0.fj9LXbkQcSLMLIjoeD6IXkLLVigPQx3wNaSiUzfQkl8"
    ALCHEMY_API_KEY = "Dwhp-JulbzNpZrEHruaBSD7RRx4Eeukb"
    HELIUS_API_KEY = "87466c84-da3e-42be-b346-a4e837da857f"
    
    # RPC 节点配置
    RPC_CONFIGS: Dict[str, Dict[str, Any]] = {
        # EVM 兼容链
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
        
        # 非 EVM 链
        "SOL": {
            "rpc_url": f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
        },
        "SOL_DEVNET": {
            "rpc_url": f"https://devnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
        },
        "SOL_TESTNET": {
            "rpc_url": f"https://testnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
        },
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
    def get_rpc_url(cls, chain: str) -> str:
        """获取指定链的 RPC URL"""
        if chain not in cls.RPC_CONFIGS:
            raise ValueError(f"不支持的链类型: {chain}")
        return cls.RPC_CONFIGS[chain]["rpc_url"]
    
    @classmethod
    def get_moralis_url(cls, chain: str) -> str:
        """获取指定链的 Moralis URL"""
        if chain not in cls.RPC_CONFIGS or "moralis_url" not in cls.RPC_CONFIGS[chain]:
            raise ValueError(f"不支持的链类型或该链不支持 Moralis: {chain}")
        return cls.RPC_CONFIGS[chain]["moralis_url"]
    
    @classmethod
    def get_kadena_config(cls, chain: str) -> Dict[str, Any]:
        """获取 Kadena 链的配置"""
        if chain not in ["KDA", "KDA_TESTNET"]:
            raise ValueError(f"不支持的 Kadena 链类型: {chain}")
        return {
            "rpc_url": cls.RPC_CONFIGS[chain]["rpc_url"],
            "chain_id": cls.RPC_CONFIGS[chain]["chain_id"],
            "network_id": cls.RPC_CONFIGS[chain]["network_id"],
            "api_version": cls.RPC_CONFIGS[chain]["api_version"],
            "nodes": cls.RPC_CONFIGS[chain]["nodes"]
        } 