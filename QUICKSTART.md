# 快速开始指南

## 5分钟快速启动

### 1. 准备工作

```bash
# 克隆或进入项目目录
cd tadf_data_extraction

# 安装基础依赖
pip install -r requirements.txt

# 安装DECIMER（推荐）
pip install decimer
```

### 2. 配置API密钥

编辑 `config.py`:

```python
# MinerU API
MINERU_API_TOKEN = "你的MinerU token"

# 阿里云DashScope（Qwen）
DASHSCOPE_API_KEY = "你的API key"

# DECIMER（本地服务）
DECIMER_API_URL = "http://localhost:8000/predict"
```

### 3. 启动DECIMER服务

```bash
# 方式1: 使用启动脚本（推荐）
./start_decimer_server.sh

# 方式2: 直接运行
python server.py

# 方式3: 使用gunicorn（生产环境）
gunicorn -w 4 -b 0.0.0.0:8000 server:app
```

在另一个终端测试服务：

```bash
# 测试健康检查
curl http://localhost:8000/health

# 运行完整测试
python test_decimer_server.py
```

### 4. 处理第一个PDF

```bash
# 处理单个PDF
python main.py --mode single \
    --paper-id "test_paper" \
    --pdf-path "path/to/paper.pdf"
```

### 5. 查看结果

```bash
# 查看处理结果
ls data/processed/test_paper/

# 查看数据库
sqlite3 data/database/molecules.db "SELECT * FROM molecules LIMIT 5;"
```

### 6. 导出ML数据集

```bash
python main.py --mode export \
    --output-dir "ml_datasets"

# 查看导出的数据集
ls ml_datasets/
```

## 目录结构

```
tadf_data_extraction/
├── config.py                   # 配置文件 ⚙️
├── main.py                     # 主程序入口 🚀
├── server.py                   # DECIMER服务 🔬
├── modules/                    # 核心模块 📦
├── data/                       # 数据目录 💾
│   ├── raw_pdfs/              # 放置PDF文件
│   ├── mineru_output/         # MinerU输出
│   ├── processed/             # 处理结果
│   └── database/              # SQLite数据库
└── logs/                      # 日志文件 📝
```

## 常用命令

### 处理PDF

```bash
# 单个PDF
python main.py --mode single --paper-id ID --pdf-path PATH

# 批量处理
python main.py --mode batch --pdf-dir DIR

# 导出数据集
python main.py --mode export --output-dir OUTPUT
```

### DECIMER服务

```bash
# 启动服务
python server.py

# 测试服务
python test_decimer_server.py

# 后台运行
nohup python server.py > decimer.log 2>&1 &
```

### 查看数据

```bash
# 查看日志
tail -f logs/tadf_extraction.log

# 查看数据库
sqlite3 data/database/photophysics.db "SELECT COUNT(*) FROM photophysics;"

# 查看JSON结果
cat data/processed/PAPER_ID/structures.json | python -m json.tool
```

## 工作流程

```
1. 准备PDF → data/raw_pdfs/

2. 启动DECIMER服务
   python server.py

3. 处理PDF
   python main.py --mode single --paper-id ID --pdf-path PATH

4. 查看结果
   data/processed/ID/
   ├── parsed/              # 解析结果
   ├── structures.json      # 识别的结构
   ├── extracted/           # 抽取的数据
   └── quality_report.json  # 质量报告

5. 导出数据集
   python main.py --mode export --output-dir OUTPUT
```

## 故障排查

### 问题1: MinerU失败

```bash
# 检查API token
echo $MINERU_API_TOKEN

# 查看错误日志
tail logs/tadf_extraction.log
```

### 问题2: DECIMER服务无法连接

```bash
# 检查服务是否运行
curl http://localhost:8000/health

# 重启服务
pkill -f server.py
python server.py
```

### 问题3: Qwen API失败

```bash
# 检查API key
python -c "from config import DASHSCOPE_API_KEY; print(DASHSCOPE_API_KEY)"

# 测试API
curl -X POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json"
```

## 示例代码

### Python脚本调用

```python
from main import TADFExtractionPipeline

# 创建流水线
pipeline = TADFExtractionPipeline()

# 处理单个PDF
pipeline.run_full_pipeline("paper_001", "path/to/paper.pdf")

# 导出数据集
pipeline.export_ml_datasets("output_dir")
```

### 使用单个模块

```python
from modules.structure_recognizer import StructureRecognizer

# 识别结构
recognizer = StructureRecognizer()
result = recognizer.recognize_structure("structure.png")
print(result['pred_smiles'])
```

## 性能优化

### 加速DECIMER

```bash
# 使用多进程
gunicorn -w 4 -b 0.0.0.0:8000 server:app

# 使用GPU（如果DECIMER支持）
CUDA_VISIBLE_DEVICES=0 python server.py
```

### 批量处理优化

- 使用SSD存储临时文件
- 调整API请求间隔避免限流
- 使用多线程下载MinerU结果

## 获取帮助

```bash
# 查看帮助
python main.py --help

# 查看示例
python examples/quickstart.py

# 查看文档
cat README.md
cat DECIMER_SERVER.md
```

## 下一步

✅ 阅读完整文档: `README.md`
✅ 了解DECIMER服务: `DECIMER_SERVER.md`
✅ 查看项目总结: `PROJECT_SUMMARY.md`
✅ 运行示例代码: `examples/quickstart.py`

## 常见问题

**Q: 可以处理哪些语言的文献?**
A: MinerU支持多语言，但表格抽取针对英文优化。

**Q: 需要GPU吗?**
A: DECIMER在CPU上也能运行，但GPU会更快。

**Q: 数据质量如何保证?**
A: 系统有自动规则验证和质量标记，建议人工抽查。

**Q: 可以离线使用吗?**
A: MinerU和Qwen需要联网，DECIMER可以本地运行。

---

**祝使用愉快！** 🚀

