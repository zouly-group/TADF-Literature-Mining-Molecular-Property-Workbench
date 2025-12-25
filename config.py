#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TADF数据抽取系统 - 配置文件
"""

import os
from pathlib import Path

# ==================== 项目路径配置 ====================
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_PDFS_DIR = DATA_DIR / "raw_pdfs"
MINERU_OUTPUT_DIR = DATA_DIR / "mineru_output"
PROCESSED_DIR = DATA_DIR / "processed"
DATABASE_DIR = DATA_DIR / "database"
LOGS_DIR = PROJECT_ROOT / "logs"

# 创建必要的目录
for dir_path in [DATA_DIR, RAW_PDFS_DIR, MINERU_OUTPUT_DIR, PROCESSED_DIR, DATABASE_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ==================== MinerU API配置 ====================

MINERU_API_TOKEN = os.getenv("MINERU_API_TOKEN", "eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiIyMDkwMjM3MyIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc2NTE2NjMxMywiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiIiwib3BlbklkIjpudWxsLCJ1dWlkIjoiYmQxMDcyZTQtNzlhNy00YTQ0LTk2OGEtNDRkZmEzN2RjYTMwIiwiZW1haWwiOiIiLCJleHAiOjE3NjYzNzU5MTN9.wMuDHY0ENDkZS8VlrDJnEkNZXZBwmyRdRc17SIOPWYvGiUXgK1a-IhLjLeOEF2LRZtWro5n6izunspJkNEDvFw")
MINERU_BASE_URL = "https://mineru.net/api/v4"

# ==================== Qwen LLM配置 ====================
DASHSCOPE_API_KEY ="sk-6818b22bc9874efe985bbb7c8158ae88"
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_CHAT_ENDPOINT = f"{QWEN_BASE_URL}/chat/completions"

# LLM 参数
MODEL_NAME = "qwen-max"
TEMPERATURE = 0.1
MAX_RETRY = 3
SLEEP_BETWEEN = 1.0
TIMEOUT_SEC = 60

# ==================== DECIMER配置 ====================
# 假设DECIMER已经本地部署，提供HTTP API
DECIMER_API_URL = os.getenv("DECIMER_API_URL", "http://localhost:8000/predict")
DECIMER_TIMEOUT = 30

# ==================== 图像分类配置 ====================
# Qwen-VL 图像分类标签
FIGURE_TYPES = [
    "molecular_structure",      # 分子结构图
    "energy_level_diagram",     # 能级图
    "device_structure",         # 器件结构图
    "photophysical_scheme",     # 机理流程示意
    "spectrum_or_curve",        # 光谱/曲线图
    "table_or_flowchart",       # 表格/流程图
    "other"                     # 其他
]

# ==================== 数据质量配置 ====================
# 数值范围校验
LAMBDA_RANGE = (200, 800)      # nm
FWHM_RANGE = (5, 200)          # nm
DELTA_EST_RANGE = (0, 1.5)     # eV (>1标记可疑)
PHI_PL_RANGE = (0, 1)          # 0-1
EQE_RANGE = (0, 100)           # %

# 置信度阈值
SMILES_CONFIDENCE_THRESHOLD = 0.7
LOW_CONFIDENCE_THRESHOLD = 0.5

# ==================== 数据库Schema ====================
# 论文表字段
PAPERS_SCHEMA = {
    "paper_id": "TEXT PRIMARY KEY",
    "doi": "TEXT",
    "title": "TEXT",
    "journal": "TEXT",
    "year": "INTEGER",
    "first_author": "TEXT",
    "pdf_main_path": "TEXT",
    "pdf_si_path": "TEXT",
    "topic_tag": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
}

# 化合物表字段
MOLECULES_SCHEMA = {
    "compound_id": "TEXT PRIMARY KEY",
    "paper_id": "TEXT",
    "paper_local_id": "TEXT",
    "name": "TEXT",
    "smiles": "TEXT",
    "class": "TEXT",
    "structure_figure_id": "TEXT",
    "global_confidence": "REAL",
    "source_info": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
}

# 光物性表字段
PHOTOPHYSICS_SCHEMA = {
    "record_id": "TEXT PRIMARY KEY",
    "compound_id": "TEXT",
    "paper_id": "TEXT",
    "paper_local_id": "TEXT",
    "environment_type": "TEXT",
    "environment_detail": "TEXT",
    "host": "TEXT",
    "doping_wt_percent": "REAL",
    "temperature_K": "REAL",
    "lambda_PL_nm": "REAL",
    "lambda_em_nm": "REAL",
    "FWHM_nm": "REAL",
    "Phi_PL": "REAL",
    "Delta_EST_eV": "REAL",
    "tau_prompt_ns": "REAL",
    "tau_delayed_us": "REAL",
    "k_r": "REAL",
    "k_ISC": "REAL",
    "k_RISC": "REAL",
    "table_id": "TEXT",
    "source_snippet": "TEXT",
    "note": "TEXT",
    "quality_flag": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
}

# 器件性能表字段
DEVICES_SCHEMA = {
    "device_id": "TEXT PRIMARY KEY",
    "paper_id": "TEXT",
    "emitter_compound_id": "TEXT",
    "paper_local_id": "TEXT",
    "device_structure": "TEXT",
    "host": "TEXT",
    "doping_wt_percent": "REAL",
    "lambda_EL_nm": "REAL",
    "CIE_x": "REAL",
    "CIE_y": "REAL",
    "EQE_max_percent": "REAL",
    "EQE_100_cd_m2": "REAL",
    "EQE_1000_cd_m2": "REAL",
    "L_max_cd_m2": "REAL",
    "table_id": "TEXT",
    "source_snippet": "TEXT",
    "quality_flag": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
}

# ==================== 日志配置 ====================
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"
LOG_FILE = LOGS_DIR / "tadf_extraction.log"

