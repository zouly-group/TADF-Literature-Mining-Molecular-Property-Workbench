# DECIMER服务端使用指南

## 概述

本服务提供DECIMER分子结构图识别的REST API接口，支持两种运行模式：
1. **Python包模式**（推荐）：直接调用DECIMER Python包
2. **CLI模式**：调用DECIMER命令行工具

## 安装

### 方式1: 使用DECIMER Python包（推荐）

```bash
# 安装DECIMER
pip install decimer

# 安装Flask
pip install flask werkzeug

# 测试DECIMER是否正常工作
python -c "from DECIMER import predict_SMILES; print('DECIMER installed successfully')"
```

### 方式2: 使用DECIMER CLI

```bash
# 确保decimer命令在PATH中
which decimer

# 如果没有，需要先安装DECIMER
```

## 启动服务

### 基本启动

```bash
# 使用Python包模式（默认）
python server.py

# 使用CLI模式
DECIMER_MODE=cli python server.py

# 指定端口
PORT=8080 python server.py

# 设置超时时间
DECIMER_TIMEOUT=60 python server.py
```

### 使用环境变量

```bash
# 创建 .env 文件
cat > .env << EOF
DECIMER_MODE=python
DECIMER_CLI=decimer
DECIMER_TIMEOUT=30
HOST=0.0.0.0
PORT=8000
EOF

# 启动服务
source .env && python server.py
```

### 后台运行

```bash
# 使用nohup
nohup python server.py > decimer_server.log 2>&1 &

# 使用screen
screen -S decimer
python server.py
# Ctrl+A, D 分离会话

# 重新连接
screen -r decimer
```

### 使用systemd（推荐生产环境）

创建 `/etc/systemd/system/decimer.service`:

```ini
[Unit]
Description=DECIMER REST API Service
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/tadf_data_extraction
Environment="DECIMER_MODE=python"
ExecStart=/usr/bin/python3 server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl start decimer
sudo systemctl enable decimer
sudo systemctl status decimer
```

## API使用

### 1. 健康检查

```bash
curl http://localhost:8000/health
```

响应：
```json
{
  "status": "healthy",
  "mode": "python",
  "python_available": true,
  "timestamp": 1702345678.123
}
```

### 2. 识别分子结构

```bash
# 上传图片文件
curl -X POST \
  -F "image=@/path/to/structure.png" \
  http://localhost:8000/predict
```

成功响应：
```json
{
  "success": true,
  "smiles": "C1=CC=C(C=C1)C2=CC=CC=C2",
  "token_confidences": [],
  "elapsed_time": 1.234,
  "method": "python"
}
```

失败响应：
```json
{
  "success": false,
  "error": "Error message",
  "method": "python"
}
```

### 3. Python客户端示例

```python
import requests

# 识别结构
def recognize_structure(image_path: str, api_url: str = "http://localhost:8000/predict"):
    with open(image_path, 'rb') as f:
        files = {'image': f}
        response = requests.post(api_url, files=files, timeout=30)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            return result.get('smiles')
    
    return None

# 使用
smiles = recognize_structure("molecule.png")
print(f"SMILES: {smiles}")
```

## 配置选项

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DECIMER_MODE` | `python` | 运行模式：`python` 或 `cli` |
| `DECIMER_CLI` | `decimer` | CLI命令路径 |
| `DECIMER_TIMEOUT` | `30` | 超时时间（秒） |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |

### 代码配置

在 `server.py` 中修改：

```python
# 最大文件大小（字节）
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tif', 'tiff', 'bmp'}
```

## 性能优化

### 1. 使用多进程

使用gunicorn运行多个worker：

```bash
pip install gunicorn

# 启动4个worker进程
gunicorn -w 4 -b 0.0.0.0:8000 server:app
```

### 2. 使用nginx反向代理

nginx配置示例：

```nginx
upstream decimer {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    listen 80;
    server_name decimer.example.com;
    
    client_max_body_size 20M;
    
    location / {
        proxy_pass http://decimer;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 60s;
    }
}
```

### 3. 缓存结果

可以添加Redis缓存来避免重复识别相同的结构图：

```python
import hashlib
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def get_cache_key(image_data):
    return hashlib.md5(image_data).hexdigest()

# 在predict函数中添加缓存逻辑
```

## 监控和日志

### 查看日志

```bash
# 实时查看日志
tail -f decimer_server.log

# 查看错误日志
grep ERROR decimer_server.log

# 统计请求数
grep "✅ 识别成功" decimer_server.log | wc -l
```

### 监控指标

建议监控以下指标：
- 请求成功率
- 平均响应时间
- 队列长度
- 内存使用

## 故障排除

### 问题1: DECIMER包未安装

```bash
# 错误信息
⚠️  DECIMER Python包未安装，将使用CLI模式

# 解决方案
pip install decimer
```

### 问题2: CLI命令找不到

```bash
# 错误信息
FileNotFoundError: [Errno 2] No such file or directory: 'decimer'

# 解决方案
which decimer  # 查找decimer路径
export DECIMER_CLI=/path/to/decimer
```

### 问题3: 超时错误

```bash
# 错误信息
DECIMER CLI timeout (>30s)

# 解决方案
export DECIMER_TIMEOUT=60  # 增加超时时间
```

### 问题4: 文件过大

```bash
# 错误信息
413 Request Entity Too Large

# 解决方案
# 在server.py中增加MAX_CONTENT_LENGTH
MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 改为32MB
```

### 问题5: 内存不足

如果处理大量请求时内存不足：

```bash
# 限制worker数量
gunicorn -w 2 -b 0.0.0.0:8000 server:app

# 或添加内存限制
ulimit -v 4194304  # 4GB
```

## 安全建议

### 1. 添加认证

```python
from functools import wraps
from flask import request

API_KEY = "your-secret-key"

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('X-API-Key') != API_KEY:
            return jsonify({"error": "Invalid API key"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route("/predict", methods=["POST"])
@require_api_key
def predict():
    # ...
```

### 2. 限流

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)

@app.route("/predict", methods=["POST"])
@limiter.limit("10 per minute")
def predict():
    # ...
```

### 3. 使用HTTPS

在生产环境中，使用nginx配置SSL证书。

## 测试

### 单元测试

```bash
python -m pytest tests/test_server.py
```

### 压力测试

```bash
# 使用Apache Bench
ab -n 100 -c 10 -p test_image.png -T multipart/form-data \
   http://localhost:8000/predict

# 使用wrk
wrk -t4 -c100 -d30s http://localhost:8000/health
```

## 更新日志

- **v1.0.0** (2024-12): 初始版本
  - 支持Python包和CLI两种模式
  - 文件上传API
  - 健康检查端点
  - 完善的错误处理

## 参考资料

- [DECIMER GitHub](https://github.com/Kohulan/DECIMER-Image_Transformer)
- [Flask文档](https://flask.palletsprojects.com/)
- [Gunicorn文档](https://gunicorn.org/)

## 许可证

MIT License

