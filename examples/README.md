# 示例代码

本目录包含TADF数据抽取系统的示例代码。

## quickstart.py

快速开始示例，演示系统各个模块的基本用法：

- 文献管理
- 文档解析
- 图像分类
- 结构识别
- 数据抽取
- 质量控制

运行方式：

```bash
cd examples
python quickstart.py
```

## 更多示例

### 处理单个文献

```python
from main import TADFExtractionPipeline

pipeline = TADFExtractionPipeline()
pipeline.run_full_pipeline("paper_001", "/path/to/paper.pdf")
```

### 导出特定任务数据集

```python
from modules.dataset_builder import DatasetBuilder

builder = DatasetBuilder()

# 导出ΔE_ST数据集
builder.export_ml_dataset_delta_est("delta_est_dataset.json", quality_filter="valid")

# 导出FWHM数据集
builder.export_ml_dataset_fwhm("fwhm_dataset.json", quality_filter="valid")

# 导出EQE数据集
builder.export_ml_dataset_eqe("eqe_dataset.json", quality_filter="valid")
```

### 自定义数据抽取Prompt

```python
from modules.data_extractor import DataExtractor

extractor = DataExtractor()

# 修改系统提示词来适配特定的表格格式
custom_prompt = """
你是一个专业的科学数据抽取专家...
（这里编写你的自定义提示词）
"""

# 使用自定义prompt
# 可以通过继承DataExtractor类并重写相关方法实现
```

### 批量质量审核

```python
from modules.quality_control import QualityController, LLMReviewer

qc = QualityController()
reviewer = LLMReviewer()

# 自动规则验证
validated_records = qc.batch_validate_photophysical(records)

# LLM审核（可选）
reviewed_records = reviewer.batch_review(records, source_tables)
```

## 注意事项

1. 运行示例前，请确保已正确配置 `config.py` 中的API密钥
2. DECIMER服务需要单独部署
3. 某些示例需要实际的文件路径，请根据实际情况修改

