from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from urllib.parse import quote_plus

# 数据库配置
DB_CONFIG = {
    "database": os.getenv("MYSQL_DATABASE", "wallet"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "@Liuzhao-9575@"),
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": os.getenv("MYSQL_PORT", "3306")
}

# 创建数据库连接
encoded_password = quote_plus(DB_CONFIG['password'])
DATABASE_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{encoded_password}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)

# 创建会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()

class Wallet(Base):
    """钱包表"""
    __tablename__ = "wallets"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), index=True)
    address = Column(String(128), index=True)
    private_key = Column(String(256))  # 加密后的私钥
    chain = Column(String(32))  # 链类型：ETH, SOL, KDA
    name = Column(String(64), default="")  # 钱包名称
    is_watch_only = Column(Boolean, default=False)  # 是否为观察者钱包
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PaymentPassword(Base):
    """支付密码表"""
    __tablename__ = "payment_passwords"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), unique=True, index=True)
    password_hash = Column(String(256))  # 密码哈希
    salt = Column(String(64))  # 密码盐值
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Chain(Base):
    """链配置表"""
    __tablename__ = "chains"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), index=True)
    chain = Column(String(32))  # 链类型：ETH, SOL, KDA
    is_selected = Column(Boolean, default=False)  # 是否选中
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Database:
    """数据库操作类"""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def init_db(self):
        """初始化数据库"""
        Base.metadata.create_all(bind=self.engine)
    
    def get_db(self):
        """获取数据库会话"""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def add_wallet(self, wallet_data: dict):
        """添加钱包"""
        db = self.SessionLocal()
        try:
            wallet = Wallet(**wallet_data)
            db.add(wallet)
            db.commit()
            db.refresh(wallet)
            return wallet
        finally:
            db.close()
    
    def get_wallet(self, wallet_id: int):
        """获取钱包"""
        db = self.SessionLocal()
        try:
            return db.query(Wallet).filter(Wallet.id == wallet_id).first()
        finally:
            db.close()
    
    def get_wallets_by_device(self, device_id: str):
        """获取设备的所有钱包"""
        db = self.SessionLocal()
        try:
            return db.query(Wallet).filter(Wallet.device_id == device_id).all()
        finally:
            db.close()
    
    def update_wallet(self, wallet_id: int, update_data: dict):
        """更新钱包"""
        db = self.SessionLocal()
        try:
            wallet = db.query(Wallet).filter(Wallet.id == wallet_id).first()
            if wallet:
                for key, value in update_data.items():
                    setattr(wallet, key, value)
                db.commit()
                db.refresh(wallet)
            return wallet
        finally:
            db.close()
    
    def delete_wallet(self, wallet_id: int):
        """删除钱包"""
        db = self.SessionLocal()
        try:
            wallet = db.query(Wallet).filter(Wallet.id == wallet_id).first()
            if wallet:
                db.delete(wallet)
                db.commit()
                return True
            return False
        finally:
            db.close()
    
    def add_payment_password(self, password_data: dict):
        """添加支付密码"""
        db = self.SessionLocal()
        try:
            password = PaymentPassword(**password_data)
            db.add(password)
            db.commit()
            db.refresh(password)
            return password
        finally:
            db.close()
    
    def get_payment_password(self, device_id: str):
        """获取支付密码"""
        db = self.SessionLocal()
        try:
            return db.query(PaymentPassword).filter(PaymentPassword.device_id == device_id).first()
        finally:
            db.close()
    
    def update_payment_password(self, device_id: str, update_data: dict):
        """更新支付密码"""
        db = self.SessionLocal()
        try:
            password = db.query(PaymentPassword).filter(PaymentPassword.device_id == device_id).first()
            if password:
                for key, value in update_data.items():
                    setattr(password, key, value)
                db.commit()
                db.refresh(password)
            return password
        finally:
            db.close()
    
    def add_chain(self, chain_data: dict):
        """添加链配置"""
        db = self.SessionLocal()
        try:
            chain = Chain(**chain_data)
            db.add(chain)
            db.commit()
            db.refresh(chain)
            return chain
        finally:
            db.close()
    
    def get_chain(self, device_id: str, chain: str):
        """获取链配置"""
        db = self.SessionLocal()
        try:
            return db.query(Chain).filter(
                Chain.device_id == device_id,
                Chain.chain == chain
            ).first()
        finally:
            db.close()
    
    def update_chain(self, device_id: str, chain: str, update_data: dict):
        """更新链配置"""
        db = self.SessionLocal()
        try:
            chain_obj = db.query(Chain).filter(
                Chain.device_id == device_id,
                Chain.chain == chain
            ).first()
            if chain_obj:
                for key, value in update_data.items():
                    setattr(chain_obj, key, value)
                db.commit()
                db.refresh(chain_obj)
            return chain_obj
        finally:
            db.close() 