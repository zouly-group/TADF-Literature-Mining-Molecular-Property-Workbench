#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速开始示例
演示如何使用TADF数据抽取系统的各个模块
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.paper_manager import PaperManager
from modules.document_parser import DocumentParser
from modules.image_classifier import ImageClassifier
from modules.structure_recognizer import StructureRecognizer
from modules.data_extractor import DataExtractor
from utils.logger import setup_logger

logger = setup_logger("quickstart")


def example_1_paper_management():
    """示例1：文献管理"""
    logger.info("=" * 60)
    logger.info("示例1：文献管理")
    logger.info("=" * 60)
    
    pm = PaperManager()
    
    # 添加论文
    paper_id = pm.add_paper({
        "doi": "10.1039/c9sc01234a",
        "title": "Example TADF Paper",
        "journal": "Chemical Science",
        "year": 2024,
        "first_author": "Zhang",
        "pdf_main_path": "/path/to/paper.pdf"
    })
    
    logger.info(f"已添加论文: {paper_id}")
    
    # 查询论文
    paper = pm.get_paper(paper_id)
    logger.info(f"论文信息: {paper}")
    
    # 列出所有论文
    papers = pm.list_papers()
    logger.info(f"共有 {len(papers)} 篇论文")


def example_2_document_parsing(json_path: str, images_dir: str):
    """示例2：文档解析"""
    logger.info("=" * 60)
    logger.info("示例2：文档解析")
    logger.info("=" * 60)
    
    parser = DocumentParser()
    
    # 解析JSON
    stats = parser.parse_mineru_json(json_path, "paper_001", images_dir)
    logger.info(f"解析统计: {stats}")
    
    # 获取表格
    tables = parser.get_tables()
    logger.info(f"找到 {len(tables)} 个表格")
    if tables:
        logger.info(f"第一个表格标题: {tables[0].caption}")
    
    # 获取图像
    figures = parser.get_figures()
    logger.info(f"找到 {len(figures)} 个图像")
    
    # 过滤光物性表格
    phys_tables = parser.filter_tables_by_type("photophysical")
    logger.info(f"找到 {len(phys_tables)} 个光物性表格")


def example_3_image_classification(image_path: str):
    """示例3：图像分类"""
    logger.info("=" * 60)
    logger.info("示例3：图像分类（Qwen-VL）")
    logger.info("=" * 60)
    
    classifier = ImageClassifier()
    
    # 分类单张图片
    result = classifier.classify_image(image_path)
    if result:
        logger.info(f"图像类型: {result['figure_type']}")
        logger.info(f"是否为分子结构: {result['is_molecular_structure']}")
        logger.info(f"理由: {result['reason']}")


def example_4_structure_recognition(image_path: str):
    """示例4：结构识别"""
    logger.info("=" * 60)
    logger.info("示例4：结构识别（DECIMER）")
    logger.info("=" * 60)
    
    recognizer = StructureRecognizer()
    
    # 识别结构
    result = recognizer.recognize_structure(image_path)
    if result:
        logger.info(f"SMILES: {result['pred_smiles']}")
        logger.info(f"置信度: {result['global_confidence']:.3f}")
        logger.info(f"状态: {result['status']}")


def example_5_data_extraction():
    """示例5：数据抽取"""
    logger.info("=" * 60)
    logger.info("示例5：数据抽取（LLM）")
    logger.info("=" * 60)
    
    extractor = DataExtractor()
    
    # 示例表格
    caption = "Photophysical properties of compounds 1-3 in toluene"
    markdown_table = """
| Compound | λPL (nm) | FWHM (nm) | ΦPL (%) | ΔE_ST (eV) |
|----------|----------|-----------|---------|------------|
| 1        | 475      | 28        | 92      | 0.08       |
| 2        | 490      | 35        | 85      | 0.12       |
| 3        | 510      | 42        | 78      | 0.15       |
"""
    
    # 抽取光物性数据
    records = extractor.extract_photophysical_data(caption, markdown_table)
    logger.info(f"抽取到 {len(records)} 条记录")
    for i, record in enumerate(records, 1):
        logger.info(f"记录{i}: {record}")


def example_6_quality_control():
    """示例6：质量控制"""
    logger.info("=" * 60)
    logger.info("示例6：质量控制")
    logger.info("=" * 60)
    
    from modules.quality_control import QualityController
    
    qc = QualityController()
    
    # 示例数据
    record = {
        "compound_id": "cmp_123",
        "lambda_PL_nm": 475.0,
        "FWHM_nm": 28.0,
        "Phi_PL": 0.92,
        "Delta_EST_eV": 0.08
    }
    
    # 验证
    quality_flag, issues = qc.validate_photophysical_record(record)
    logger.info(f"质量标记: {quality_flag}")
    logger.info(f"问题: {issues if issues else '无'}")


def main():
    """主函数"""
    logger.info("TADF数据抽取系统 - 快速开始示例")
    logger.info("")
    
    # 运行各个示例
    example_1_paper_management()
    
    # 注意：以下示例需要实际的文件路径
    # example_2_document_parsing("/path/to/result.json", "/path/to/images/")
    # example_3_image_classification("/path/to/structure.png")
    # example_4_structure_recognition("/path/to/structure.png")
    
    example_5_data_extraction()
    example_6_quality_control()
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("所有示例完成！")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

