# 多链钱包后端

这是一个支持 EVM、Solana 和 Kadena 链的钱包后端项目。

## 功能特点

- 支持 EVM 兼容链（如 Ethereum、BSC、Polygon 等）
- 支持 Solana 链
- 支持 Kadena 链
- 用户认证和授权
- RESTful API 接口

## 安装和设置

1. 创建并激活虚拟环境：
```bash
conda create -n wallet python=3.10
conda activate wallet
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
复制 `.env.example` 文件为 `.env`，并填写相应的配置信息。

4. 运行数据库迁移：
```bash
python manage.py migrate
```

5. 创建超级用户：
```bash
python manage.py createsuperuser
```

6. 运行开发服务器：
```bash
python manage.py runserver
```

## API 端点

- `POST /api/wallets/create_wallet/` - 创建新钱包
- `GET /api/wallets/` - 获取用户的所有钱包
- `GET /api/wallets/{id}/` - 获取特定钱包详情
- `GET /api/wallets/{id}/balance/` - 获取钱包余额

## 安全注意事项

- 私钥存储在数据库中，请确保数据库安全
- 在生产环境中使用 HTTPS
- 定期备份数据库
- 使用强密码和双因素认证

## 贡献

欢迎提交 Pull Request 和 Issue。

## 许可证

MIT 