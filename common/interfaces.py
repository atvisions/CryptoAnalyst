from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class WalletInterface(ABC):
    """钱包基础接口"""
    
    @abstractmethod
    def create_wallet(self, device_id: str, payment_password: str) -> Dict[str, Any]:
        """创建新钱包
        
        Args:
            device_id: 设备ID
            payment_password: 支付密码
            
        Returns:
            包含钱包信息的字典
        """
        pass
    
    @abstractmethod
    def import_by_private_key(self, device_id: str, private_key: str, payment_password: str) -> Dict[str, Any]:
        """通过私钥导入钱包
        
        Args:
            device_id: 设备ID
            private_key: 私钥
            payment_password: 支付密码
            
        Returns:
            包含钱包信息的字典
        """
        pass
    
    @abstractmethod
    def import_by_mnemonic(self, device_id: str, mnemonic: str, payment_password: str) -> Dict[str, Any]:
        """通过助记词导入钱包
        
        Args:
            device_id: 设备ID
            mnemonic: 助记词
            payment_password: 支付密码
            
        Returns:
            包含钱包信息的字典
        """
        pass
    
    @abstractmethod
    def import_watch_only(self, device_id: str, address: str, name: str) -> Dict[str, Any]:
        """导入观察者钱包
        
        Args:
            device_id: 设备ID
            address: 钱包地址
            name: 钱包名称
            
        Returns:
            包含钱包信息的字典
        """
        pass
    
    @abstractmethod
    def get_wallet_list(self, device_id: str) -> List[Dict[str, Any]]:
        """获取钱包列表
        
        Args:
            device_id: 设备ID
            
        Returns:
            钱包列表
        """
        pass
    
    @abstractmethod
    def rename_wallet(self, wallet_id: int, new_name: str) -> Dict[str, Any]:
        """重命名钱包
        
        Args:
            wallet_id: 钱包ID
            new_name: 新名称
            
        Returns:
            更新后的钱包信息
        """
        pass
    
    @abstractmethod
    def delete_wallet(self, wallet_id: int, payment_password: str) -> bool:
        """删除钱包
        
        Args:
            wallet_id: 钱包ID
            payment_password: 支付密码
            
        Returns:
            是否删除成功
        """
        pass
    
    @abstractmethod
    def show_private_key(self, wallet_id: int, payment_password: str) -> str:
        """显示私钥
        
        Args:
            wallet_id: 钱包ID
            payment_password: 支付密码
            
        Returns:
            私钥
        """
        pass

class PaymentPasswordInterface(ABC):
    """支付密码接口"""
    
    @abstractmethod
    def set_password(self, device_id: str, payment_password: str, payment_password_confirm: str) -> bool:
        """设置支付密码
        
        Args:
            device_id: 设备ID
            payment_password: 支付密码
            payment_password_confirm: 确认支付密码
            
        Returns:
            是否设置成功
        """
        pass
    
    @abstractmethod
    def verify_password(self, device_id: str, payment_password: str) -> bool:
        """验证支付密码
        
        Args:
            device_id: 设备ID
            payment_password: 支付密码
            
        Returns:
            是否验证成功
        """
        pass
    
    @abstractmethod
    def change_password(self, device_id: str, old_password: str, new_password: str, confirm_password: str) -> bool:
        """修改支付密码
        
        Args:
            device_id: 设备ID
            old_password: 旧密码
            new_password: 新密码
            confirm_password: 确认新密码
            
        Returns:
            是否修改成功
        """
        pass
    
    @abstractmethod
    def get_password_status(self, device_id: str) -> bool:
        """获取密码设置状态
        
        Args:
            device_id: 设备ID
            
        Returns:
            是否已设置密码
        """
        pass

class ChainInterface(ABC):
    """链接口"""
    
    @abstractmethod
    def get_supported_chains(self) -> List[Dict[str, Any]]:
        """获取支持的链列表
        
        Returns:
            支持的链列表
        """
        pass
    
    @abstractmethod
    def select_chain(self, device_id: str, chain: str) -> bool:
        """选择链
        
        Args:
            device_id: 设备ID
            chain: 链名称
            
        Returns:
            是否选择成功
        """
        pass
    
    @abstractmethod
    def verify_mnemonic(self, device_id: str, chain: str, mnemonic: str, payment_password: str) -> bool:
        """验证助记词
        
        Args:
            device_id: 设备ID
            chain: 链名称
            mnemonic: 助记词
            payment_password: 支付密码
            
        Returns:
            是否验证成功
        """
        pass 