#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DECIMER REST API 服务端
提供分子结构图识别服务
支持两种模式：
1. DECIMER Python包 (推荐)
2. DECIMER CLI命令行工具
"""

import os
import io
import time
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List, Dict

from flask import Flask, request, jsonify, Response
from werkzeug.utils import secure_filename

# ==================== 配置 ====================
app = Flask(__name__)

# 服务配置
HOST = "0.0.0.0"
PORT = 8000
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tif', 'tiff', 'bmp'}

# DECIMER配置
DECIMER_MODE = os.getenv("DECIMER_MODE", "python")  # "python" 或 "cli"
DECIMER_CLI = os.getenv("DECIMER_CLI", "decimer")
DECIMER_TIMEOUT = int(os.getenv("DECIMER_TIMEOUT", "30"))

# 临时文件目录
TEMP_DIR = Path(tempfile.gettempdir()) / "decimer_temp"
TEMP_DIR.mkdir(exist_ok=True)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DECIMER-Server")

app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


# ==================== DECIMER Python包模式 ====================
try:
    if DECIMER_MODE == "python":
        from DECIMER import predict_SMILES
        DECIMER_AVAILABLE = True
        logger.info("✅ DECIMER Python包已加载")
except ImportError:
    DECIMER_AVAILABLE = False
    if DECIMER_MODE == "python":
        logger.warning("⚠️  DECIMER Python包未安装，将使用CLI模式")
        DECIMER_MODE = "cli"


# ==================== 工具函数 ====================
def allowed_file(filename: str) -> bool:
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_decimer_output(stdout: str) -> Tuple[Optional[str], Optional[float], List[Dict]]:
    """
    解析DECIMER CLI输出
    
    Args:
        stdout: CLI标准输出
        
    Returns:
        (smiles, global_confidence, token_confidences)
    """
    smiles = None
    global_confidence = None
    token_confidences = []
    
    lines = stdout.splitlines()
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # 提取SMILES
        if line.lower().startswith("smiles:") or line.lower().startswith("predicted smiles:"):
            smiles = line.split(":", 1)[1].strip()
        
        # 提取置信度
        elif "confidence" in line.lower():
            parts = line.split(":")
            if len(parts) == 2:
                try:
                    conf_value = float(parts[1].strip())
                    if "global" in line.lower():
                        global_confidence = conf_value
                    else:
                        # Token级别置信度
                        token_confidences.append({"confidence": conf_value})
                except ValueError:
                    pass
    
    return smiles, global_confidence, token_confidences


# ==================== DECIMER调用函数 ====================
def predict_smiles_python(image_path: str) -> Dict:
    """
    使用DECIMER Python包识别结构
    
    Args:
        image_path: 图片路径
        
    Returns:
        识别结果字典
    """
    try:
        start_time = time.time()
        
        # 调用DECIMER
        smiles = predict_SMILES(image_path)
        
        elapsed = time.time() - start_time
        
        # DECIMER Python包不直接提供置信度，我们返回空列表
        # 实际使用中可以通过修改DECIMER源码获取
        result = {
            "success": True,
            "smiles": smiles,
            "token_confidences": [],
            "elapsed_time": elapsed,
            "method": "python"
        }
        
        logger.info(f"✅ 识别成功 (Python): {smiles[:50]}... ({elapsed:.2f}s)")
        return result
        
    except Exception as e:
        logger.error(f"❌ Python模式识别失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "method": "python"
        }


def predict_smiles_cli(image_path: str) -> Dict:
    """
    使用DECIMER CLI识别结构
    
    Args:
        image_path: 图片路径
        
    Returns:
        识别结果字典
    """
    try:
        start_time = time.time()
        
        # 调用CLI
        proc = subprocess.Popen(
            [DECIMER_CLI, image_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = proc.communicate(timeout=DECIMER_TIMEOUT)
        elapsed = time.time() - start_time
        
        if proc.returncode != 0:
            logger.error(f"❌ CLI返回错误: {stderr}")
            return {
                "success": False,
                "error": stderr.strip() or "DECIMER CLI failed",
                "method": "cli"
            }
        
        # 解析输出
        smiles, global_conf, token_confs = parse_decimer_output(stdout)
        
        if not smiles:
            logger.error(f"❌ 无法从CLI输出中提取SMILES")
            return {
                "success": False,
                "error": "Could not extract SMILES from CLI output",
                "raw_output": stdout,
                "method": "cli"
            }
        
        result = {
            "success": True,
            "smiles": smiles,
            "token_confidences": token_confs,
            "global_confidence": global_conf,
            "elapsed_time": elapsed,
            "raw_output": stdout,
            "method": "cli"
        }
        
        logger.info(f"✅ 识别成功 (CLI): {smiles[:50]}... ({elapsed:.2f}s)")
        return result
        
    except subprocess.TimeoutExpired:
        logger.error(f"❌ CLI超时 (>{DECIMER_TIMEOUT}s)")
        return {
            "success": False,
            "error": f"DECIMER CLI timeout (>{DECIMER_TIMEOUT}s)",
            "method": "cli"
        }
    except Exception as e:
        logger.error(f"❌ CLI模式识别失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "method": "cli"
        }


def predict_smiles(image_path: str) -> Dict:
    """
    识别分子结构（自动选择模式）
    
    Args:
        image_path: 图片路径
        
    Returns:
        识别结果字典
    """
    if DECIMER_MODE == "python" and DECIMER_AVAILABLE:
        return predict_smiles_python(image_path)
    else:
        return predict_smiles_cli(image_path)


# ==================== API路由 ====================
@app.route("/", methods=["GET"])
def index():
    """服务首页"""
    return jsonify({
        "service": "DECIMER REST API",
        "version": "1.0.0",
        "mode": DECIMER_MODE,
        "endpoints": {
            "/": "服务信息",
            "/health": "健康检查",
            "/predict": "POST - 上传图片识别SMILES"
        }
    })


@app.route("/health", methods=["GET"])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "mode": DECIMER_MODE,
        "python_available": DECIMER_AVAILABLE,
        "timestamp": time.time()
    })


@app.route("/predict", methods=["POST"])
def predict():
    """
    主要识别端点
    接受multipart/form-data文件上传
    """
    # 检查是否有文件
    if 'image' not in request.files:
        logger.warning("请求缺少image字段")
        return jsonify({
            "success": False,
            "error": "No image file provided. Use 'image' field in multipart/form-data"
        }), 400
    
    file = request.files['image']
    
    # 检查文件名
    if file.filename == '':
        logger.warning("空文件名")
        return jsonify({
            "success": False,
            "error": "Empty filename"
        }), 400
    
    # 检查文件类型
    if not allowed_file(file.filename):
        logger.warning(f"不支持的文件类型: {file.filename}")
        return jsonify({
            "success": False,
            "error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400
    
    # 保存临时文件
    filename = secure_filename(file.filename)
    timestamp = int(time.time() * 1000)
    temp_filename = f"{timestamp}_{filename}"
    temp_path = TEMP_DIR / temp_filename
    
    try:
        file.save(str(temp_path))
        logger.info(f"📥 接收文件: {filename} -> {temp_path}")
        
        # 调用DECIMER
        result = predict_smiles(str(temp_path))
        
        # 清理临时文件
        try:
            temp_path.unlink()
        except:
            pass
        
        # 返回结果
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"❌ 处理请求时出错: {e}")
        
        # 清理临时文件
        try:
            if temp_path.exists():
                temp_path.unlink()
        except:
            pass
        
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    """文件过大处理"""
    return jsonify({
        "success": False,
        "error": f"File too large. Maximum size: {MAX_CONTENT_LENGTH // (1024*1024)}MB"
    }), 413


# ==================== 主函数 ====================
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 DECIMER REST API 服务启动")
    logger.info("=" * 60)
    logger.info(f"模式: {DECIMER_MODE}")
    logger.info(f"地址: http://{HOST}:{PORT}")
    logger.info(f"Python包可用: {DECIMER_AVAILABLE}")
    logger.info(f"临时目录: {TEMP_DIR}")
    logger.info(f"最大文件大小: {MAX_CONTENT_LENGTH // (1024*1024)}MB")
    logger.info(f"允许的文件类型: {', '.join(ALLOWED_EXTENSIONS)}")
    logger.info("=" * 60)
    
    app.run(
        host=HOST,
        port=PORT,
        debug=False,
        threaded=True
    )
