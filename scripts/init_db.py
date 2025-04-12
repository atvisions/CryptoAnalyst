from common.database import Database, Base, engine
import os

def init_db():
    """初始化数据库"""
    # 创建数据库
    db = Database()
    db.init_db()
    print("数据库初始化完成！")

if __name__ == "__main__":
    init_db() 