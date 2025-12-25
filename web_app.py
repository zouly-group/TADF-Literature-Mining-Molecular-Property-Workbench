#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TADF数据抽取系统 - Flask Web应用后端
"""

import os
import json
import uuid
import time
import threading
import csv
import io
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS
from werkzeug.utils import secure_filename
import tempfile
import shutil
import requests
import sqlite3

# 导入项目模块
from config import (
    RAW_PDFS_DIR,
    MINERU_OUTPUT_DIR,
    PROCESSED_DIR,
    DATABASE_DIR,
    DECIMER_API_URL,
    DASHSCOPE_API_KEY,
    MINERU_API_TOKEN,
    MINERU_BASE_URL
)
from modules.mineru_processor import MinerUProcessor
from modules.document_parser import DocumentParser
from modules.image_classifier import ImageClassifier
from modules.structure_recognizer import StructureRecognizer
from modules.data_extractor import DataExtractor
from modules.entity_aligner import EntityAligner
from modules.dataset_builder import DatasetBuilder
from modules.quality_control import QualityController
from modules.paper_manager import PaperManager
from utils.logger import setup_logger

logger = setup_logger(__name__)

app = Flask(__name__)
CORS(app)

# 配置
UPLOAD_FOLDER = Path(PROCESSED_DIR) / "uploads"
DATA_STORAGE = Path(PROCESSED_DIR) / "web_data"
CONFIG_STORAGE = Path(PROCESSED_DIR) / "extraction_configs"
STATUS_STORAGE = Path(PROCESSED_DIR) / "status_cache"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
DATA_STORAGE.mkdir(parents=True, exist_ok=True)
CONFIG_STORAGE.mkdir(parents=True, exist_ok=True)
STATUS_STORAGE.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# 全局状态存储（用于进度跟踪）
processing_status = {}
processing_results = {}

# SMILES识别锁（确保串行处理，避免DECIMER服务器并发问题）
smiles_recognition_lock = threading.Lock()


def allowed_file(filename):
    """检查文件扩展名"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_paper_data(paper_id: str, data: dict):
    """保存论文数据到JSON文件"""
    file_path = DATA_STORAGE / f"{paper_id}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"已保存论文数据: {paper_id}")


def load_paper_data(paper_id: str) -> dict:
    """从JSON文件加载论文数据"""
    file_path = DATA_STORAGE / f"{paper_id}.json"
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_status(status_key: str, status: dict):
    """保存状态到文件系统"""
    status_file = STATUS_STORAGE / f"{status_key}.json"
    try:
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"保存状态失败: {e}")


def load_status(status_key: str) -> dict:
    """从文件系统加载状态"""
    status_file = STATUS_STORAGE / f"{status_key}.json"
    if status_file.exists():
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载状态失败: {e}")
    return None


def delete_status(status_key: str):
    """删除状态文件"""
    status_file = STATUS_STORAGE / f"{status_key}.json"
    if status_file.exists():
        try:
            status_file.unlink()
        except Exception as e:
            logger.error(f"删除状态文件失败: {e}")


def update_status(status_key: str, status: dict):
    """更新状态（同时更新内存和文件系统）"""
    processing_status[status_key] = status
    save_status(status_key, status)


def list_papers() -> list:
    """列出所有已处理的论文"""
    papers = []
    for file_path in DATA_STORAGE.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                papers.append({
                    'paper_id': data.get('paper_id', file_path.stem),
                    'title': data.get('title', '未知标题'),
                    'created_at': data.get('created_at', ''),
                    'photophysical_count': len(data.get('photophysical_data', [])),
                    'device_count': len(data.get('device_data', [])),
                    'molecular_figures_count': len(data.get('molecular_figures', [])),
                    'extraction_config': data.get('extraction_config', None)
                })
        except Exception as e:
            logger.error(f"加载论文数据失败 {file_path}: {e}")
    return sorted(papers, key=lambda x: x.get('created_at', ''), reverse=True)


def save_extraction_config(config_name: str, config_data: dict):
    """保存抽取配置"""
    file_path = CONFIG_STORAGE / f"{config_name}.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)
    logger.info(f"已保存抽取配置: {config_name}")


def load_extraction_config(config_name: str) -> dict:
    """加载抽取配置"""
    file_path = CONFIG_STORAGE / f"{config_name}.json"
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def list_extraction_configs() -> list:
    """列出所有抽取配置"""
    configs = []
    for file_path in CONFIG_STORAGE.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                configs.append({
                    'name': file_path.stem,
                    'description': data.get('description', ''),
                    'fields': data.get('fields', {})
                })
        except Exception as e:
            logger.error(f"加载配置失败 {file_path}: {e}")
    return configs


def process_pdf_background(paper_id: str, pdf_path: str, status_key: str, extraction_config: dict = None):
    """后台处理PDF"""
    try:
        initial_status = {'status': 'processing', 'progress': 0, 'message': '开始处理...', 'paper_id': paper_id}
        processing_status[status_key] = initial_status
        save_status(status_key, initial_status)
        
        # 初始化处理器
        mineru_processor = MinerUProcessor(MINERU_API_TOKEN, MINERU_BASE_URL)
        document_parser = DocumentParser()
        image_classifier = ImageClassifier()
        data_extractor = DataExtractor()
        
        # 使用自定义配置或默认配置
        if extraction_config:
            logger.info(f"使用自定义抽取配置: {extraction_config.get('name', 'unknown')}")
        
        # 步骤1: MinerU处理
        update_status(status_key, {'status': 'processing', 'progress': 10, 'message': '使用MinerU解析PDF...', 'paper_id': paper_id})
        logger.info(f"开始处理PDF: {pdf_path}, paper_id: {paper_id}")
        extracted_dirs = mineru_processor.parse_pdfs([pdf_path], str(MINERU_OUTPUT_DIR))
        
        if not extracted_dirs:
            logger.error(f"PDF处理失败: {pdf_path}")
            update_status(status_key, {'status': 'error', 'progress': 0, 'message': 'PDF处理失败', 'paper_id': paper_id})
            return
        
        extract_dir = extracted_dirs[0]
        logger.info(f"MinerU处理完成，输出目录: {extract_dir}")
        
        json_path = mineru_processor.get_json_path(extract_dir)
        images_dir = mineru_processor.get_images_dir(extract_dir)
        
        logger.info(f"JSON路径: {json_path}, 图片目录: {images_dir}")
        
        if not json_path:
            logger.error(f"未找到JSON文件，目录内容: {list(Path(extract_dir).iterdir()) if Path(extract_dir).exists() else '目录不存在'}")
            update_status(status_key, {'status': 'error', 'progress': 0, 'message': '未找到JSON文件', 'paper_id': paper_id})
            return
        
        # 步骤2: 文档解析
        update_status(status_key, {'status': 'processing', 'progress': 30, 'message': '解析文档结构...', 'paper_id': paper_id})
        logger.info(f"开始解析文档: {json_path}")
        try:
            document_parser.parse_mineru_json(json_path, paper_id, images_dir)
            logger.info("文档解析完成")
        except Exception as e:
            logger.error(f"文档解析失败: {e}", exc_info=True)
            update_status(status_key, {'status': 'error', 'progress': 0, 'message': f'文档解析失败: {str(e)}', 'paper_id': paper_id})
            return
        
        figures = document_parser.get_figures()
        tables = document_parser.get_tables()
        logger.info(f"解析完成: {len(figures)} 个图表, {len(tables)} 个表格")
        
        # 如果没有表格，记录警告但继续处理
        if not tables:
            logger.warning("未找到表格，将跳过数据抽取步骤")
        
        # 步骤3: 图像分类（使用多线程加速）
        update_status(status_key, {'status': 'processing', 'progress': 50, 'message': '分类图像（识别分子结构图）...', 'paper_id': paper_id})
        logger.info("开始图像分类...")
        image_paths = [f.image_path for f in figures if Path(f.image_path).exists()]
        classification_results = {}
        
        if image_paths:
            logger.info(f"准备分类 {len(image_paths)} 张图像")
            
            def classify_single_image(img_path):
                """分类单张图像"""
                try:
                    result = image_classifier.classify_image(img_path)
                    return img_path, result
                except Exception as e:
                    logger.error(f"分类图像失败 {img_path}: {e}")
                    return img_path, None
            
            # 尝试使用多线程，如果失败则回退到串行处理
            try:
                # 使用线程池并行处理（最多5个并发，避免API限流）
                max_workers = min(5, len(image_paths))
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 提交所有任务
                    future_to_path = {}
                    for img_path in image_paths[:20]:  # 限制最多处理20张
                        try:
                            future_to_path[executor.submit(classify_single_image, img_path)] = img_path
                        except RuntimeError as e:
                            if 'interpreter shutdown' in str(e) or 'cannot schedule new futures' in str(e):
                                logger.warning("检测到解释器关闭，回退到串行处理")
                                raise
                            raise
                    
                    # 收集结果
                    completed = 0
                    for future in as_completed(future_to_path):
                        try:
                            completed += 1
                            img_path, result = future.result()
                            if result:
                                classification_results[img_path] = result
                            
                            # 更新进度
                            if completed % 5 == 0:
                                progress = 50 + int(30 * completed / len(future_to_path))
                                update_status(status_key, {
                                    'status': 'processing', 
                                    'progress': progress, 
                                    'message': f'分类图像中... ({completed}/{len(future_to_path)})', 
                                    'paper_id': paper_id
                                })
                        except Exception as e:
                            logger.error(f"处理图像分类任务失败: {e}")
                
                logger.info(f"图像分类完成: {len(classification_results)} 张图像分类成功")
            except RuntimeError as e:
                if 'interpreter shutdown' in str(e) or 'cannot schedule new futures' in str(e):
                    # 解释器正在关闭，回退到串行处理
                    logger.warning("多线程不可用，使用串行处理图像分类...")
                    for img_path in image_paths[:20]:
                        try:
                            img_path, result = classify_single_image(img_path)
                            if result:
                                classification_results[img_path] = result
                        except Exception as ex:
                            logger.error(f"串行分类图像失败 {img_path}: {ex}")
                    logger.info(f"串行图像分类完成: {len(classification_results)} 张图像分类成功")
                else:
                    raise
        
        # 筛选分子结构图
        molecular_figures = []
        for fig in figures:
            if Path(fig.image_path).exists():
                img_path = fig.image_path
                if img_path in classification_results:
                    result = classification_results[img_path]
                    if result.get('is_molecular_structure'):
                        molecular_figures.append({
                            'figure_id': fig.figure_id,
                            'image_path': fig.image_path,
                            'caption': fig.caption,
                            'page': fig.page_index
                        })
        
        # 步骤4: 数据抽取（使用多线程加速）
        update_status(status_key, {'status': 'processing', 'progress': 70, 'message': '抽取数据...', 'paper_id': paper_id})
        logger.info("开始数据抽取...")
        photophysical_tables = document_parser.filter_tables_by_type("photophysical")
        device_tables = document_parser.filter_tables_by_type("device")
        logger.info(f"找到 {len(photophysical_tables)} 个光物性表格, {len(device_tables)} 个器件表格")
        
        photophysical_data = []
        device_data = []
        
        def extract_photophysical_table(table):
            """抽取光物性表格数据"""
            try:
                records = data_extractor.extract_photophysical_data(
                    table.caption,
                    table.markdown_table
                )
                for record in records:
                    record['table_id'] = table.table_id
                return records
            except Exception as e:
                logger.error(f"抽取光物性表格失败 {table.table_id}: {e}")
                return []
        
        def extract_device_table(table):
            """抽取器件表格数据"""
            try:
                records = data_extractor.extract_device_data(
                    table.caption,
                    table.markdown_table
                )
                for record in records:
                    record['table_id'] = table.table_id
                return records
            except Exception as e:
                logger.error(f"抽取器件表格失败 {table.table_id}: {e}")
                return []
        
        # 使用线程池并行抽取表格数据（如果解释器正在关闭，回退到串行处理）
        all_tables = list(photophysical_tables) + list(device_tables)
        if all_tables:
            logger.info(f"开始抽取 {len(all_tables)} 个表格...")
            try:
                # 尝试使用多线程
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = []
                    
                    # 提交光物性表格任务
                    for table in photophysical_tables:
                        try:
                            futures.append(('photophysical', executor.submit(extract_photophysical_table, table)))
                        except RuntimeError as e:
                            if 'interpreter shutdown' in str(e):
                                logger.warning("检测到解释器关闭，回退到串行处理")
                                raise
                            raise
                    
                    # 提交器件表格任务
                    for table in device_tables:
                        try:
                            futures.append(('device', executor.submit(extract_device_table, table)))
                        except RuntimeError as e:
                            if 'interpreter shutdown' in str(e):
                                logger.warning("检测到解释器关闭，回退到串行处理")
                                raise
                            raise
                    
                    # 收集结果
                    completed = 0
                    for table_type, future in futures:
                        try:
                            records = future.result()
                            completed += 1
                            if records:
                                if table_type == 'photophysical':
                                    photophysical_data.extend(records)
                                else:
                                    device_data.extend(records)
                            
                            # 更新进度
                            if completed % 2 == 0 or completed == len(futures):
                                progress = 70 + int(15 * completed / len(futures))
                                update_status(status_key, {
                                    'status': 'processing', 
                                    'progress': progress, 
                                    'message': f'抽取数据中... ({completed}/{len(futures)})', 
                                    'paper_id': paper_id
                                })
                        except Exception as e:
                            logger.error(f"处理表格任务失败: {e}")
            except RuntimeError as e:
                if 'interpreter shutdown' in str(e) or 'cannot schedule new futures' in str(e):
                    # 解释器正在关闭，回退到串行处理
                    logger.warning("多线程不可用，使用串行处理...")
                    for table in photophysical_tables:
                        records = extract_photophysical_table(table)
                        if records:
                            photophysical_data.extend(records)
                    for table in device_tables:
                        records = extract_device_table(table)
                        if records:
                            device_data.extend(records)
                else:
                    raise
        
        logger.info(f"数据抽取完成: {len(photophysical_data)} 条光物性记录, {len(device_data)} 条器件记录")
        
        # 步骤5: 实体对齐和数据入库（可选，失败不影响主流程）
        update_status(status_key, {'status': 'processing', 'progress': 85, 'message': '实体对齐和数据入库...', 'paper_id': paper_id})
        logger.info("开始实体对齐和数据入库...")
        
        try:
            # 初始化对齐器和数据集构建器
            entity_aligner = EntityAligner()
            dataset_builder = DatasetBuilder()
            quality_controller = QualityController()
            
            # 获取结构数据
            structure_data = []
            for fig in molecular_figures:
                structure_data.append({
                    'paper_id': paper_id,
                    'structure_figure_id': fig['figure_id'],
                    'image_path': fig['image_path'],
                    'pred_smiles': '',  # 可以后续识别
                    'status': 'pending'
                })
            
            logger.info(f"准备对齐: {len(structure_data)} 个结构, {len(photophysical_data)} 条光物性数据, {len(device_data)} 条器件数据")
            
            # 实体对齐
            entity_aligner.align_compounds(
                paper_id,
                structure_data,
                photophysical_data,
                device_data
            )
            logger.info("实体对齐完成")
            
            # 映射数据到compound_id
            phys_mapped, _ = entity_aligner.map_data_to_compounds(
                paper_id,
                photophysical_data,
                "photophysical"
            )
            logger.info(f"光物性数据映射完成: {len(phys_mapped)} 条")
            
            dev_mapped, _ = entity_aligner.map_data_to_compounds(
                paper_id,
                device_data,
                "device"
            )
            logger.info(f"器件数据映射完成: {len(dev_mapped)} 条")
            
            # 数据验证
            phys_validated = quality_controller.batch_validate_photophysical(phys_mapped) if phys_mapped else []
            dev_validated = quality_controller.batch_validate_device(dev_mapped) if dev_mapped else []
            logger.info(f"数据验证完成: {len(phys_validated)} 条光物性, {len(dev_validated)} 条器件")
            
            # 保存到数据库
            if phys_validated:
                logger.info(f"开始保存 {len(phys_validated)} 条光物性记录到数据库...")
                dataset_builder.insert_photophysics_records(phys_validated)
                logger.info("光物性记录保存完成")
            
            if dev_validated:
                logger.info(f"开始保存 {len(dev_validated)} 条器件记录到数据库...")
                dataset_builder.insert_device_records(dev_validated)
                logger.info("器件记录保存完成")
            
            logger.info(f"✅ 已保存 {len(phys_validated)} 条光物性记录和 {len(dev_validated)} 条器件记录到数据库")
        except Exception as e:
            logger.error(f"数据入库失败（不影响主流程）: {e}", exc_info=True)
            # 继续执行，不中断流程
        
        # 步骤6: 保存结果到JSON
        update_status(status_key, {'status': 'processing', 'progress': 95, 'message': '保存结果...', 'paper_id': paper_id})
        
        # 从extract_dir中查找PDF文件（MinerU输出的origin.pdf）
        mineru_pdf_path = None
        if extract_dir:
            extract_path = Path(extract_dir)
            # 查找 *_origin.pdf 文件
            pdf_files = list(extract_path.glob("*_origin.pdf"))
            if pdf_files:
                mineru_pdf_path = str(pdf_files[0])
                logger.info(f"在MinerU输出目录找到PDF: {mineru_pdf_path}")
            else:
                # 如果没有找到origin.pdf，尝试查找任何PDF文件
                pdf_files = list(extract_path.glob("*.pdf"))
                if pdf_files:
                    mineru_pdf_path = str(pdf_files[0])
                    logger.info(f"在MinerU输出目录找到PDF: {mineru_pdf_path}")
        
        # 优先使用MinerU输出的PDF，否则使用原始上传的PDF
        final_pdf_path = mineru_pdf_path if mineru_pdf_path else pdf_path
        
        result_data = {
            'paper_id': paper_id,
            'title': paper_id,  # 可以从PDF元数据提取
            'created_at': datetime.now().isoformat(),
            'pdf_path': final_pdf_path,  # 保存PDF路径（优先使用MinerU输出的PDF）
            'molecular_figures': molecular_figures,
            'photophysical_data': photophysical_data,
            'device_data': device_data,
            'extract_dir': extract_dir,
            'json_path': json_path,
            'figures_count': len(figures),
            'tables_count': len(tables),
            'tables': [{'table_id': t.table_id, 'caption': t.caption, 'markdown_table': t.markdown_table, 'page': t.page_index} for t in tables],
            'paragraphs': [{'para_id': p.para_id, 'text': p.text, 'section': p.section, 'page': p.page_index} for p in document_parser.get_paragraphs()],
            'extraction_config': extraction_config
        }
        
        logger.info("开始保存结果到JSON文件...")
        save_paper_data(paper_id, result_data)
        logger.info(f"论文数据已保存到JSON: {paper_id}")
        
        # 保存到papers.db
        try:
            paper_manager = PaperManager()
            paper_record = {
                'paper_id': paper_id,
                'title': result_data.get('title', paper_id),
                'created_at': result_data.get('created_at', datetime.now().isoformat()),
                'pdf_path': result_data.get('pdf_path', ''),
                'figures_count': result_data.get('figures_count', 0),
                'tables_count': result_data.get('tables_count', 0),
                'photophysical_count': len(result_data.get('photophysical_data', [])),
                'device_count': len(result_data.get('device_data', []))
            }
            paper_manager.add_paper(paper_record)
            logger.info(f"✅ 论文记录已保存到papers.db: {paper_id}")
        except Exception as e:
            logger.error(f"保存到papers.db失败: {e}", exc_info=True)
            # 不影响主流程
        
        processing_results[status_key] = result_data
        
        final_status = {'status': 'completed', 'progress': 100, 'message': '处理完成！', 'paper_id': paper_id}
        update_status(status_key, final_status)
        logger.info(f"✅ 处理完成: {paper_id}")
        
        # 任务完成后，延迟删除状态文件（保留一段时间以便查询）
        # 这里不立即删除，让前端有时间获取最终状态
        
    except Exception as e:
        logger.error(f"处理PDF出错: {e}", exc_info=True)
        update_status(status_key, {'status': 'error', 'progress': 0, 'message': f'处理失败: {str(e)}', 'paper_id': paper_id})


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/papers', methods=['GET'])
def get_papers():
    """获取所有论文列表"""
    papers = list_papers()
    return jsonify({'success': True, 'papers': papers})


@app.route('/api/papers/<paper_id>', methods=['GET'])
def get_paper(paper_id):
    """获取指定论文数据"""
    data = load_paper_data(paper_id)
    if data:
        return jsonify({'success': True, 'data': data})
    return jsonify({'success': False, 'message': '论文不存在'}), 404


@app.route('/api/papers/<paper_id>/source', methods=['GET'])
def get_paper_source(paper_id):
    """获取论文原文内容（PDF路径）"""
    try:
        data = load_paper_data(paper_id)
        if not data:
            logger.warning(f"论文不存在: {paper_id}")
            return jsonify({'success': False, 'message': '论文不存在'}), 404
        
        # 优先从extract_dir中查找PDF文件
        pdf_path = None
        extract_dir = data.get('extract_dir')
        
        if extract_dir:
            extract_path = Path(extract_dir)
            if extract_path.exists():
                # 查找 *_origin.pdf 文件
                pdf_files = list(extract_path.glob("*_origin.pdf"))
                if pdf_files:
                    pdf_path = pdf_files[0]
                    logger.info(f"从MinerU输出目录找到PDF: {pdf_path}")
                else:
                    # 如果没有找到origin.pdf，尝试查找任何PDF文件
                    pdf_files = list(extract_path.glob("*.pdf"))
                    if pdf_files:
                        pdf_path = pdf_files[0]
                        logger.info(f"从MinerU输出目录找到PDF: {pdf_path}")
        
        # 如果extract_dir中没有找到，使用保存的pdf_path
        if not pdf_path:
            pdf_path_str = data.get('pdf_path')
            if pdf_path_str:
                pdf_path = Path(pdf_path_str)
        
        if not pdf_path:
            logger.warning(f"论文 {paper_id} 没有PDF路径")
            return jsonify({
                'success': False,
                'message': '该论文暂无PDF文件'
            }), 404
        
        # 检查PDF文件是否存在
        if not pdf_path.exists():
            logger.warning(f"PDF文件不存在: {pdf_path}")
            return jsonify({
                'success': False,
                'message': 'PDF文件不存在'
            }), 404
        
        logger.info(f"返回论文 {paper_id} 的PDF路径: {pdf_path}")
        
        return jsonify({
            'success': True,
            'pdf_path': str(pdf_path),
            'pdf_url': f'/api/papers/{paper_id}/pdf'
        })
    except Exception as e:
        logger.error(f"获取论文原文失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'获取原文失败: {str(e)}'}), 500


@app.route('/api/papers/<paper_id>/pdf', methods=['GET'])
def get_paper_pdf(paper_id):
    """获取论文PDF文件"""
    try:
        data = load_paper_data(paper_id)
        if not data:
            return jsonify({'success': False, 'message': '论文不存在'}), 404
        
        # 优先从extract_dir中查找PDF文件
        pdf_path = None
        extract_dir = data.get('extract_dir')
        
        if extract_dir:
            extract_path = Path(extract_dir)
            if extract_path.exists():
                # 查找 *_origin.pdf 文件
                pdf_files = list(extract_path.glob("*_origin.pdf"))
                if pdf_files:
                    pdf_path = pdf_files[0]
                    logger.info(f"从MinerU输出目录找到PDF: {pdf_path}")
                else:
                    # 如果没有找到origin.pdf，尝试查找任何PDF文件
                    pdf_files = list(extract_path.glob("*.pdf"))
                    if pdf_files:
                        pdf_path = pdf_files[0]
                        logger.info(f"从MinerU输出目录找到PDF: {pdf_path}")
        
        # 如果extract_dir中没有找到，使用保存的pdf_path
        if not pdf_path:
            pdf_path_str = data.get('pdf_path')
            if pdf_path_str:
                pdf_path = Path(pdf_path_str)
        
        if not pdf_path:
            return jsonify({'success': False, 'message': 'PDF文件不存在'}), 404
        
        if not pdf_path.exists():
            return jsonify({'success': False, 'message': 'PDF文件不存在'}), 404
        
        logger.info(f"返回PDF文件: {pdf_path}")
        return send_file(str(pdf_path), mimetype='application/pdf')
    except Exception as e:
        logger.error(f"获取PDF文件失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'获取PDF失败: {str(e)}'}), 500


@app.route('/api/papers/<paper_id>', methods=['PUT'])
def update_paper(paper_id):
    """更新论文数据并同步到数据库"""
    try:
        data = request.json
        paper_data = load_paper_data(paper_id)
        if not paper_data:
            return jsonify({'success': False, 'message': '论文不存在'}), 404
        
        # 更新数据
        updated = False
        if 'photophysical_data' in data:
            paper_data['photophysical_data'] = data['photophysical_data']
            updated = True
        
        if 'device_data' in data:
            paper_data['device_data'] = data['device_data']
            updated = True
        
        if not updated:
            return jsonify({'success': False, 'message': '没有需要更新的数据'}), 400
        
        # 保存到JSON文件
        save_paper_data(paper_id, paper_data)
        logger.info(f"已更新论文 {paper_id} 的JSON数据")
        
        # 同步更新到数据库
        try:
            entity_aligner = EntityAligner()
            dataset_builder = DatasetBuilder()
            quality_controller = QualityController()
            
            # 获取更新后的数据
            photophysical_data = paper_data.get('photophysical_data', [])
            device_data = paper_data.get('device_data', [])
            structure_data = paper_data.get('molecular_figures', [])
            
            logger.info(f"开始同步论文 {paper_id} 的数据到数据库: {len(photophysical_data)} 条光物性记录, {len(device_data)} 条器件记录")
            
            # 首先确保实体对齐（创建compound记录）
            logger.info("步骤1: 执行实体对齐...")
            align_stats = entity_aligner.align_compounds(
                paper_id,
                structure_data,
                photophysical_data,
                device_data
            )
            logger.info(f"实体对齐完成: {align_stats}")
            
            # 映射数据到compound_id
            logger.info("步骤2: 映射数据到compound_id...")
            phys_mapped, phys_unmapped = entity_aligner.map_data_to_compounds(
                paper_id,
                photophysical_data,
                "photophysical"
            )
            logger.info(f"光物性数据映射: {len(phys_mapped)} 成功, {len(phys_unmapped)} 未映射")
            
            dev_mapped, dev_unmapped = entity_aligner.map_data_to_compounds(
                paper_id,
                device_data,
                "device"
            )
            logger.info(f"器件数据映射: {len(dev_mapped)} 成功, {len(dev_unmapped)} 未映射")
            
            # 对于未映射的记录，尝试从SMILES创建compound记录
            if phys_unmapped:
                logger.warning(f"有 {len(phys_unmapped)} 条光物性记录未映射到compound_id，尝试从SMILES创建")
                for record in phys_unmapped:
                    paper_local_id = record.get('paper_local_id')
                    smiles = record.get('smiles', '')
                    name = record.get('name', '')
                    
                    if paper_local_id:
                        # 如果没有SMILES，使用paper_local_id作为临时compound_id
                        if not smiles:
                            compound_id = f"{paper_id}_{paper_local_id}"
                            logger.info(f"记录 {paper_local_id} 没有SMILES，使用临时compound_id: {compound_id}")
                        else:
                            # 生成compound_id
                            compound_id = entity_aligner._generate_compound_id(smiles)
                            logger.info(f"记录 {paper_local_id} 从SMILES生成compound_id: {compound_id}")
                        
                        # 确保compound记录存在，如果存在则更新smiles
                        conn = sqlite3.connect(str(entity_aligner.db_path))
                        cursor = conn.cursor()
                        cursor.execute("SELECT compound_id, smiles FROM molecules WHERE compound_id = ?", (compound_id,))
                        existing = cursor.fetchone()
                        if not existing:
                            # 创建新记录
                            cursor.execute("""
                                INSERT INTO molecules (compound_id, paper_id, paper_local_id, name, smiles)
                                VALUES (?, ?, ?, ?, ?)
                            """, (compound_id, paper_id, paper_local_id, name, smiles or ''))
                            conn.commit()
                            logger.info(f"创建新的compound记录: {compound_id} with SMILES: {smiles[:50] if smiles else 'None'}...")
                        else:
                            # 如果记录已存在，更新smiles字段（如果新的smiles不为空）
                            if smiles and (not existing[1] or existing[1] != smiles):
                                cursor.execute("""
                                    UPDATE molecules 
                                    SET smiles = ?, paper_local_id = COALESCE(paper_local_id, ?), name = COALESCE(NULLIF(name, ''), ?)
                                    WHERE compound_id = ?
                                """, (smiles, paper_local_id, name, compound_id))
                                conn.commit()
                                logger.info(f"更新compound记录的SMILES: {compound_id} -> {smiles[:50]}...")
                        conn.close()
                        record['compound_id'] = compound_id
                        phys_mapped.append(record)
                    else:
                        logger.warning(f"记录缺少paper_local_id，跳过: {record}")
            
            if dev_unmapped:
                logger.warning(f"有 {len(dev_unmapped)} 条器件记录未映射到compound_id")
                # 器件数据需要emitter_compound_id，从emitter_name或paper_local_id查找
                for record in dev_unmapped:
                    paper_local_id = record.get('paper_local_id')
                    emitter_name = record.get('emitter_name', '')
                    if paper_local_id:
                        compound_id = entity_aligner.find_compound_by_paper_local_id(paper_id, paper_local_id)
                        if compound_id:
                            record['emitter_compound_id'] = compound_id
                            dev_mapped.append(record)
            
            # 为每条记录添加paper_id（如果缺失）
            for record in phys_mapped:
                if 'paper_id' not in record:
                    record['paper_id'] = paper_id
            
            for record in dev_mapped:
                if 'paper_id' not in record:
                    record['paper_id'] = paper_id
            
            # 同步更新molecules表中的smiles字段
            logger.info("步骤2.5: 同步更新molecules表中的SMILES...")
            conn = sqlite3.connect(str(entity_aligner.db_path))
            cursor = conn.cursor()
            
            # 更新已映射记录对应的molecules表中的smiles
            for record in phys_mapped:
                compound_id = record.get('compound_id')
                smiles = record.get('smiles', '')
                paper_local_id = record.get('paper_local_id', '')
                
                if compound_id and smiles:
                    # 更新molecules表中的smiles字段
                    cursor.execute("""
                        UPDATE molecules 
                        SET smiles = ? 
                        WHERE compound_id = ? AND (smiles IS NULL OR smiles = '' OR smiles != ?)
                    """, (smiles, compound_id, smiles))
                    if cursor.rowcount > 0:
                        logger.info(f"更新molecules表: {compound_id} -> {smiles[:50]}...")
            
            # 对于未映射但有SMILES的记录，也尝试更新
            for record in phys_unmapped:
                paper_local_id = record.get('paper_local_id')
                smiles = record.get('smiles', '')
                
                if paper_local_id and smiles:
                    # 查找对应的compound_id
                    cursor.execute("""
                        SELECT compound_id FROM molecules 
                        WHERE paper_id = ? AND paper_local_id = ?
                    """, (paper_id, paper_local_id))
                    row = cursor.fetchone()
                    if row:
                        compound_id = row[0]
                        cursor.execute("""
                            UPDATE molecules 
                            SET smiles = ? 
                            WHERE compound_id = ? AND (smiles IS NULL OR smiles = '' OR smiles != ?)
                        """, (smiles, compound_id, smiles))
                        if cursor.rowcount > 0:
                            logger.info(f"更新未映射记录的molecules表: {compound_id} -> {smiles[:50]}...")
            
            conn.commit()
            conn.close()
            logger.info("molecules表SMILES同步完成")
            
            # 数据验证（验证函数会返回所有记录，只是添加质量标记）
            logger.info("步骤3: 数据验证...")
            if phys_mapped:
                logger.info(f"验证 {len(phys_mapped)} 条光物性记录...")
                phys_validated = quality_controller.batch_validate_photophysical(phys_mapped)
                logger.info(f"验证完成，返回 {len(phys_validated)} 条记录")
            else:
                phys_validated = []
                logger.warning("没有光物性记录需要验证")
            
            if dev_mapped:
                logger.info(f"验证 {len(dev_mapped)} 条器件记录...")
                dev_validated = quality_controller.batch_validate_device(dev_mapped)
                logger.info(f"验证完成，返回 {len(dev_validated)} 条记录")
            else:
                dev_validated = []
                logger.warning("没有器件记录需要验证")
            
            # 保存到数据库（使用INSERT OR REPLACE，确保更新已存在的记录）
            logger.info("步骤4: 保存到数据库...")
            if phys_validated:
                logger.info(f"准备保存 {len(phys_validated)} 条光物性记录到数据库")
                logger.info(f"示例记录: {phys_validated[0] if phys_validated else 'None'}")
                dataset_builder.insert_photophysics_records(phys_validated)
            else:
                logger.warning("没有可保存的光物性记录")
                if phys_mapped:
                    logger.warning(f"有 {len(phys_mapped)} 条记录但验证后为空，可能验证失败")
            
            if dev_validated:
                logger.info(f"准备保存 {len(dev_validated)} 条器件记录到数据库")
                logger.info(f"示例记录: {dev_validated[0] if dev_validated else 'None'}")
                dataset_builder.insert_device_records(dev_validated)
            else:
                logger.warning("没有可保存的器件记录")
                if dev_mapped:
                    logger.warning(f"有 {len(dev_mapped)} 条记录但验证后为空，可能验证失败")
            
            logger.info(f"✅ 已同步更新到数据库: {len(phys_validated)} 条光物性记录, {len(dev_validated)} 条器件记录")
            
            return jsonify({
                'success': True, 
                'message': f'更新成功，已同步到数据库（{len(phys_validated)} 条光物性记录, {len(dev_validated)} 条器件记录）'
            })
        except Exception as e:
            logger.error(f"同步到数据库失败: {e}", exc_info=True)
            # 即使数据库同步失败，也返回成功（因为JSON已保存）
            return jsonify({
                'success': True, 
                'message': 'JSON数据已更新，但数据库同步失败: ' + str(e),
                'warning': True
            })
    except Exception as e:
        logger.error(f"更新论文数据失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    """上传PDF文件"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '文件名为空'}), 400
    
    if not allowed_file(file.filename) or file.filename.rsplit('.', 1)[1].lower() != 'pdf':
        return jsonify({'success': False, 'message': '仅支持PDF文件'}), 400
    
    # 生成论文ID
    paper_id = request.form.get('paper_id', file.filename.rsplit('.', 1)[0])
    paper_id = secure_filename(paper_id)
    
    # 获取抽取配置
    config_name = request.form.get('extraction_config', None)
    extraction_config = None
    if config_name:
        extraction_config = load_extraction_config(config_name)
        if extraction_config:
            extraction_config['name'] = config_name
    
    # 保存文件
    filename = f"{paper_id}_{int(time.time())}.pdf"
    file_path = Path(app.config['UPLOAD_FOLDER']) / filename
    file.save(str(file_path))
    
    # 生成状态键
    status_key = str(uuid.uuid4())
    
    # 启动后台处理
    # 启动后台处理线程（非daemon，确保任务完成）
    thread = threading.Thread(
        target=process_pdf_background,
        args=(paper_id, str(file_path), status_key, extraction_config),
        name=f"PDF-Process-{paper_id}"
    )
    thread.daemon = False  # 改为False，确保即使应用重启，任务也能完成
    thread.start()
    logger.info(f"已启动后台处理线程: {thread.name}, paper_id: {paper_id}")
    
    return jsonify({
        'success': True,
        'paper_id': paper_id,
        'status_key': status_key,
        'message': '上传成功，开始处理'
    })


@app.route('/api/status/<status_key>', methods=['GET'])
def get_status(status_key):
    """获取处理状态"""
    # 首先检查内存中的状态
    if status_key in processing_status:
        status = processing_status[status_key].copy()
        if status['status'] == 'completed' and status_key in processing_results:
            status['result'] = processing_results[status_key]
        return jsonify({'success': True, 'status': status})
    
    # 如果状态不在内存中（可能因为应用重启），尝试从文件系统加载
    logger.info(f"状态键 {status_key} 不在内存中，尝试从文件系统加载...")
    saved_status = load_status(status_key)
    
    if saved_status:
        # 恢复状态到内存
        processing_status[status_key] = saved_status
        
        # 如果状态是已完成，尝试加载结果
        if saved_status.get('status') == 'completed':
            paper_id = saved_status.get('paper_id')
            if paper_id:
                paper_data = load_paper_data(paper_id)
                if paper_data:
                    processing_results[status_key] = paper_data
                    saved_status['result'] = paper_data
        
        return jsonify({'success': True, 'status': saved_status})
    
    # 如果文件系统中也没有，返回过期提示
    logger.warning(f"状态键 {status_key} 在内存和文件系统中都不存在")
    return jsonify({
        'success': False, 
        'message': '状态不存在（可能已过期），请刷新页面查看已处理的论文',
        'suggestion': 'refresh',
        'status': {
            'status': 'expired',
            'progress': 0,
            'message': '状态已过期，请刷新页面'
        }
    }), 200  # 返回200而不是404，让前端可以处理


@app.route('/api/recognize', methods=['POST'])
def recognize_smiles():
    """识别SMILES（串行处理，避免DECIMER服务器并发问题）"""
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': '未上传图片'}), 400
    
    file = request.files['image']
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': '不支持的图片格式'}), 400
    
    # 保存临时图片
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    file.save(temp_file.name)
    temp_file.close()
    
    # 使用锁确保串行处理（避免DECIMER服务器并发问题）
    with smiles_recognition_lock:
        logger.info("开始识别SMILES（串行处理）")
        try:
            # 调用DECIMER API
            import requests as req_module
            with open(temp_file.name, 'rb') as f:
                files = {'image': f}
                response = req_module.post(
                    DECIMER_API_URL,
                    files=files,
                    timeout=60  # 增加超时时间，因为串行处理可能需要更长时间
                )
            
            # 清理临时文件
            Path(temp_file.name).unlink()
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info(f"SMILES识别成功: {result.get('smiles', '')[:50]}...")
                    return jsonify({
                        'success': True,
                        'smiles': result.get('smiles', ''),
                        'confidence': result.get('global_confidence', 0.0),
                        'method': result.get('method', 'unknown')
                    })
                else:
                    logger.warning(f"SMILES识别失败: {result.get('message', '未知错误')}")
            else:
                logger.error(f"DECIMER API返回错误: {response.status_code}, {response.text[:200]}")
            
            return jsonify({'success': False, 'message': '识别失败'}), 500
        
        except Exception as e:
            logger.error(f"识别SMILES出错: {e}", exc_info=True)
            if Path(temp_file.name).exists():
                Path(temp_file.name).unlink()
            return jsonify({'success': False, 'message': f'识别出错: {str(e)}'}), 500


@app.route('/api/images/<paper_id>/<path:image_path>', methods=['GET'])
def get_image(paper_id, image_path):
    """获取图片"""
    from urllib.parse import unquote
    image_path = unquote(image_path)
    
    # 安全处理路径 - 移除路径遍历攻击
    if '..' in image_path:
        return jsonify({'success': False, 'message': '无效路径'}), 400
    
    # 如果路径不以/开头但包含media，添加/
    if not image_path.startswith('/') and image_path.startswith('media/'):
        image_path = '/' + image_path
    
    # 从论文数据中获取extract_dir和图片路径信息
    paper_data = load_paper_data(paper_id)
    possible_paths = []
    
    if paper_data:
        # 首先尝试从molecular_figures中匹配
        for fig in paper_data.get('molecular_figures', []):
            fig_image_path = fig.get('image_path', '')
            if not fig_image_path:
                continue
            
            # 检查是否是匹配的图片（通过文件名或完整路径）
            fig_path_obj = Path(fig_image_path)
            image_path_obj = Path(image_path)
            
            # 匹配条件：完整路径相同、文件名相同、或路径结尾相同
            if (fig_image_path == image_path or 
                fig_image_path.endswith(image_path) or
                image_path.endswith(fig_image_path) or
                fig_path_obj.name == image_path_obj.name):
                
                # 如果fig_image_path是绝对路径且存在，直接使用
                if fig_path_obj.is_absolute() and fig_path_obj.exists():
                    possible_paths.insert(0, fig_path_obj)
                    logger.info(f"找到匹配的图片路径: {fig_path_obj}")
                    break  # 找到匹配的，优先使用
                
                # 尝试从extract_dir查找
                if 'extract_dir' in paper_data:
                    extract_dir = Path(paper_data['extract_dir'])
                    if extract_dir.exists():
                        # 尝试多种可能的路径组合
                        possible_paths.extend([
                            extract_dir / "images" / fig_path_obj.name,
                            extract_dir / "auto" / "images" / fig_path_obj.name,
                        ])
    
    # 尝试直接使用image_path（如果是绝对路径）
    direct_path = Path(image_path)
    if direct_path.is_absolute():
        if direct_path.exists():
            # 检查是否在允许的目录内
            allowed_dirs = [str(MINERU_OUTPUT_DIR), str(PROCESSED_DIR)]
            if any(str(direct_path).startswith(d) for d in allowed_dirs):
                possible_paths.insert(0, direct_path)
        else:
            # 路径不存在，但可能是正确的绝对路径，仍然尝试
            possible_paths.append(direct_path)
    
    # 如果路径不以/开头但包含media，添加/
    if not image_path.startswith('/') and image_path.startswith('media/'):
        abs_path = Path('/') / image_path
        if abs_path.exists():
            possible_paths.insert(0, abs_path)
            logger.info(f"通过添加/找到图片: {abs_path}")
    
    # 尝试从MINERU_OUTPUT_DIR查找（通过文件名）
    image_filename = Path(image_path).name
    if MINERU_OUTPUT_DIR.exists():
        # 递归查找文件
        for img_file in MINERU_OUTPUT_DIR.rglob(image_filename):
            if img_file.is_file():
                possible_paths.append(img_file)
                logger.info(f"在MINERU_OUTPUT_DIR找到图片: {img_file}")
                break
    
    # 如果paper_data中有molecular_figures，直接使用其中的绝对路径
    if paper_data:
        for fig in paper_data.get('molecular_figures', []):
            fig_path_str = fig.get('image_path', '')
            if fig_path_str and Path(fig_path_str).name == image_filename:
                fig_path = Path(fig_path_str)
                if fig_path.is_absolute() and fig_path.exists():
                    possible_paths.insert(0, fig_path)
                    logger.info(f"从molecular_figures找到图片: {fig_path}")
                    break
    
    # 去重并尝试加载
    possible_paths = list(set(possible_paths))
    
    for img_path in possible_paths:
        print(img_path)
        try:
            if img_path and img_path.exists() and img_path.is_file():
                logger.info(f"成功加载图片: {img_path}")
                return send_file(str(img_path))
        except Exception as e:
            logger.warning(f"尝试加载图片失败 {img_path}: {e}")
            continue
    
    logger.warning(f"图片不存在: {image_path}, 尝试的路径: {[str(p) for p in possible_paths]}")
    return jsonify({'success': False, 'message': '图片不存在'}), 404


@app.route('/api/papers/<paper_id>/delete', methods=['DELETE'])
def delete_paper(paper_id):
    """删除论文"""
    file_path = DATA_STORAGE / f"{paper_id}.json"
    if file_path.exists():
        file_path.unlink()
        return jsonify({'success': True, 'message': '删除成功'})
    return jsonify({'success': False, 'message': '论文不存在'}), 404


@app.route('/api/configs', methods=['GET', 'POST'])
def handle_configs():
    """处理配置列表的GET和POST请求"""
    if request.method == 'GET':
        """获取所有抽取配置"""
        try:
            configs = list_extraction_configs()
            logger.info(f"返回配置列表，共 {len(configs)} 个配置")
            return jsonify({'success': True, 'configs': configs})
        except Exception as e:
            logger.error(f"获取配置列表失败: {e}")
            return jsonify({'success': False, 'message': f'获取配置列表失败: {str(e)}'}), 500
    elif request.method == 'POST':
        """创建新配置"""
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'message': '请求数据为空'}), 400
            config_name = data.get('name')
            if not config_name:
                return jsonify({'success': False, 'message': '配置名称不能为空'}), 400
            
            config_name = secure_filename(config_name)
            save_extraction_config(config_name, data)
            logger.info(f"创建配置成功: {config_name}")
            return jsonify({'success': True, 'message': '配置创建成功'})
        except Exception as e:
            logger.error(f"创建配置失败: {e}")
            return jsonify({'success': False, 'message': f'创建配置失败: {str(e)}'}), 500


@app.route('/api/database/tables', methods=['GET'])
def get_database_tables():
    """获取数据库表列表"""
    try:
        tables = []
        
        # 检查各个数据库文件
        db_files = {
            'papers': DATABASE_DIR / 'papers.db',
            'molecules': DATABASE_DIR / 'molecules.db',
            'photophysics': DATABASE_DIR / 'photophysics.db',
            'devices': DATABASE_DIR / 'devices.db'
        }
        
        logger.info(f"检查数据库目录: {DATABASE_DIR}")
        logger.info(f"数据库目录存在: {DATABASE_DIR.exists()}")
        
        for table_name, db_path in db_files.items():
            logger.info(f"检查表 {table_name}: {db_path} (存在: {db_path.exists()})")
            if db_path.exists():
                try:
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    
                    # 获取表结构（使用参数化查询避免SQL注入）
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                    if cursor.fetchone():
                        # 获取记录数（表名已验证，安全）
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                        
                        tables.append({
                            'name': table_name,
                            'count': count,
                            'db_path': str(db_path)
                        })
                        logger.info(f"表 {table_name} 有 {count} 条记录")
                    else:
                        logger.warning(f"表 {table_name} 在数据库 {db_path} 中不存在")
                    
                    conn.close()
                except Exception as e:
                    logger.error(f"处理表 {table_name} 时出错: {e}")
                    continue
        
        logger.info(f"返回 {len(tables)} 个表")
        return jsonify({'success': True, 'tables': tables})
    except Exception as e:
        logger.error(f"获取数据库表列表失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'获取表列表失败: {str(e)}'}), 500


@app.route('/api/database/<table_name>', methods=['GET'])
def get_table_data(table_name):
    """获取表数据"""
    try:
        # 防止路由冲突：如果table_name是'tables'，应该由get_database_tables处理
        if table_name == 'tables':
            logger.warning("table_name是'tables'，这不应该发生，可能是路由问题")
            return jsonify({'success': False, 'message': '无效的表名'}), 400
        
        # 验证表名
        valid_tables = ['papers', 'molecules', 'photophysics', 'devices']
        if table_name not in valid_tables:
            logger.warning(f"无效的表名: {table_name}")
            return jsonify({'success': False, 'message': f'无效的表名: {table_name}'}), 400
        
        # 获取分页参数
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 50))
        except (ValueError, TypeError):
            page = 1
            per_page = 50
        
        search = request.args.get('search', '').strip()
        
        # 确定数据库文件
        db_files = {
            'papers': DATABASE_DIR / 'papers.db',
            'molecules': DATABASE_DIR / 'molecules.db',
            'photophysics': DATABASE_DIR / 'photophysics.db',
            'devices': DATABASE_DIR / 'devices.db'
        }
        
        db_path = db_files[table_name]
        logger.info(f"查询表 {table_name}，数据库路径: {db_path} (存在: {db_path.exists()})")
        
        if not db_path.exists():
            logger.error(f"数据库文件不存在: {db_path}")
            return jsonify({'success': False, 'message': f'数据库文件不存在: {db_path}'}), 404
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row  # 返回字典格式
        cursor = conn.cursor()
        
        # 首先检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            conn.close()
            logger.error(f"表 {table_name} 在数据库 {db_path} 中不存在")
            return jsonify({'success': False, 'message': f'表 {table_name} 不存在'}), 404
        
        # 构建查询
        where_clause = ""
        params = []
        
        if search:
            # 获取所有列名
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            
            # 构建搜索条件（在所有文本列中搜索，使用引号包裹列名）
            search_conditions = []
            for col in columns:
                # 列名来自PRAGMA，已验证，使用引号包裹更安全
                search_conditions.append(f'"{col}" LIKE ?')
                params.append(f"%{search}%")
            
            if search_conditions:
                where_clause = "WHERE " + " OR ".join(search_conditions)
        
        # 获取总数（表名已验证，安全）
        count_query = f"SELECT COUNT(*) FROM {table_name} {where_clause}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # 获取分页数据（表名已验证，安全）
        offset = (page - 1) * per_page
        query = f"SELECT * FROM {table_name} {where_clause} LIMIT ? OFFSET ?"
        cursor.execute(query, params + [per_page, offset])
        
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]
        
        # 获取列信息（表名已验证，安全）
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        columns = [{'name': col[1], 'type': col[2]} for col in columns_info]
        
        conn.close()
        
        logger.info(f"成功返回表 {table_name} 的数据: {len(data)} 条记录，共 {total} 条")
        
        return jsonify({
            'success': True,
            'data': data,
            'columns': columns,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page if total > 0 else 0
            }
        })
    except Exception as e:
        logger.error(f"获取表数据失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'获取数据失败: {str(e)}'}), 500


@app.route('/api/configs/<config_name>', methods=['GET', 'PUT', 'DELETE'])
def handle_config(config_name):
    """处理单个配置的GET、PUT、DELETE请求"""
    from urllib.parse import unquote
    config_name = unquote(config_name)
    config_name = secure_filename(config_name)
    
    if request.method == 'GET':
        """获取指定配置"""
        try:
            config = load_extraction_config(config_name)
            if config:
                config['name'] = config_name  # 确保名称正确
                return jsonify({'success': True, 'config': config})
            return jsonify({'success': False, 'message': '配置不存在'}), 404
        except Exception as e:
            logger.error(f"获取配置失败: {e}")
            return jsonify({'success': False, 'message': f'获取配置失败: {str(e)}'}), 500
    elif request.method == 'PUT':
        """更新配置"""
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'message': '请求数据为空'}), 400
            save_extraction_config(config_name, data)
            logger.info(f"更新配置成功: {config_name}")
            return jsonify({'success': True, 'message': '配置更新成功'})
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return jsonify({'success': False, 'message': f'更新配置失败: {str(e)}'}), 500
    elif request.method == 'DELETE':
        """删除配置"""
        try:
            file_path = CONFIG_STORAGE / f"{config_name}.json"
            if file_path.exists():
                file_path.unlink()
                logger.info(f"删除配置成功: {config_name}")
                return jsonify({'success': True, 'message': '配置删除成功'})
            return jsonify({'success': False, 'message': '配置不存在'}), 404
        except Exception as e:
            logger.error(f"删除配置失败: {e}")
            return jsonify({'success': False, 'message': f'删除配置失败: {str(e)}'}), 500




if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)

