#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TADF数据抽取系统 - 主流程
"""

import argparse
from pathlib import Path
from utils.logger import setup_logger
from config import (
    RAW_PDFS_DIR,
    MINERU_OUTPUT_DIR,
    PROCESSED_DIR,
    MINERU_API_TOKEN,
    MINERU_BASE_URL
)
from modules.mineru_processor import MinerUProcessor
from modules.paper_manager import PaperManager
from modules.document_parser import DocumentParser
from modules.image_classifier import ImageClassifier
from modules.structure_recognizer import StructureRecognizer, StructureDatabase
from modules.data_extractor import DataExtractor, ExtractionDatabase
from modules.entity_aligner import EntityAligner
from modules.quality_control import QualityController, QualityReport
from modules.dataset_builder import DatasetBuilder

logger = setup_logger(__name__)


class TADFExtractionPipeline:
    """TADF数据抽取流水线"""
    
    def __init__(self):
        """初始化流水线"""
        self.paper_manager = PaperManager()
        self.mineru_processor = MinerUProcessor(MINERU_API_TOKEN, MINERU_BASE_URL)
        self.document_parser = DocumentParser()
        self.image_classifier = ImageClassifier()
        self.structure_recognizer = StructureRecognizer()
        self.data_extractor = DataExtractor()
        self.entity_aligner = EntityAligner()
        self.quality_controller = QualityController()
        self.dataset_builder = DatasetBuilder()
        
        # 中间数据存储
        self.structure_db = StructureDatabase()
        self.extraction_db = ExtractionDatabase()
    
    def run_full_pipeline(self, paper_id: str, pdf_path: str):
        """
        运行完整流水线
        
        Args:
            paper_id: 论文ID
            pdf_path: PDF文件路径
        """
        logger.info(f"=" * 80)
        logger.info(f"开始处理论文: {paper_id}")
        logger.info(f"=" * 80)
        
        # 1. 添加论文记录
        logger.info("步骤 1/8: 添加论文记录")
        self.paper_manager.add_paper({
            "paper_id": paper_id,
            "pdf_main_path": pdf_path
        })
        
        # 2. MinerU预处理
        logger.info("步骤 2/8: MinerU PDF预处理")
        extracted_dirs = self.mineru_processor.parse_pdfs([pdf_path], str(MINERU_OUTPUT_DIR))
        if not extracted_dirs:
            logger.error("MinerU处理失败")
            return
        
        extract_dir = extracted_dirs[0]
        json_path = self.mineru_processor.get_json_path(extract_dir)
        images_dir = self.mineru_processor.get_images_dir(extract_dir)
        
        # 3. 文档结构解析
        logger.info("步骤 3/8: 文档结构解析与分块")
        self.document_parser.parse_mineru_json(json_path, paper_id, images_dir)
        
        tables = self.document_parser.get_tables()
        figures = self.document_parser.get_figures()
        paragraphs = self.document_parser.get_paragraphs()
        
        # 导出解析结果
        parse_output_dir = PROCESSED_DIR / paper_id / "parsed"
        self.document_parser.export_to_json(str(parse_output_dir), paper_id)
        
        # 4. 图像分类
        logger.info("步骤 4/8: 图像分类（Qwen-VL）")
        image_paths = [fig.image_path for fig in figures if Path(fig.image_path).exists()]
        classification_results = self.image_classifier.classify_batch(image_paths)
        
        # 保存分类结果
        self.image_classifier.save_results(
            classification_results,
            str(PROCESSED_DIR / paper_id / "image_classification.json")
        )
        
        # 5. 分子结构识别
        logger.info("步骤 5/8: 分子结构识别（DECIMER）")
        structure_images = [
            path for path, result in classification_results.items()
            if result.get('is_molecular_structure')
        ]
        
        if structure_images:
            recognition_results = self.structure_recognizer.recognize_batch(structure_images)
            
            # 添加到结构数据库
            for img_path, result in recognition_results.items():
                # 找到对应的figure
                figure = next((f for f in figures if f.image_path == img_path), None)
                if figure:
                    self.structure_db.add_structure(
                        paper_id,
                        figure.figure_id,
                        img_path,
                        result
                    )
            
            # 保存识别结果
            self.structure_db.export_to_json(
                str(PROCESSED_DIR / paper_id / "structures.json")
            )
        
        # 6. 文本与表格数据抽取
        logger.info("步骤 6/8: 文本与表格数据抽取（LLM）")
        
        # 分类表格
        photophysical_tables = self.document_parser.filter_tables_by_type("photophysical")
        device_tables = self.document_parser.filter_tables_by_type("device")
        
        # 抽取光物性数据
        for table in photophysical_tables:
            records = self.data_extractor.extract_photophysical_data(
                table.caption,
                table.markdown_table
            )
            self.extraction_db.add_photophysical_records(paper_id, table.table_id, records)
        
        # 抽取器件数据
        for table in device_tables:
            records = self.data_extractor.extract_device_data(
                table.caption,
                table.markdown_table
            )
            self.extraction_db.add_device_records(paper_id, table.table_id, records)
        
        # 导出抽取数据
        extraction_output_dir = PROCESSED_DIR / paper_id / "extracted"
        self.extraction_db.export_to_json(str(extraction_output_dir))
        
        # 7. 实体对齐
        logger.info("步骤 7/8: 实体对齐与统一ID")
        self.entity_aligner.align_compounds(
            paper_id,
            self.structure_db.get_structures_by_paper(paper_id),
            self.extraction_db.get_photophysical_by_paper(paper_id),
            self.extraction_db.get_device_by_paper(paper_id)
        )
        
        # 映射数据到compound_id
        phys_mapped, phys_unmapped = self.entity_aligner.map_data_to_compounds(
            paper_id,
            self.extraction_db.get_photophysical_by_paper(paper_id),
            "photophysical"
        )
        
        dev_mapped, dev_unmapped = self.entity_aligner.map_data_to_compounds(
            paper_id,
            self.extraction_db.get_device_by_paper(paper_id),
            "device"
        )
        
        # 8. 质量控制
        logger.info("步骤 8/8: 质量控制与数据入库")
        
        # 验证数据
        phys_validated = self.quality_controller.batch_validate_photophysical(phys_mapped)
        dev_validated = self.quality_controller.batch_validate_device(dev_mapped)
        
        # 入库
        self.dataset_builder.insert_photophysics_records(phys_validated)
        self.dataset_builder.insert_device_records(dev_validated)
        
        # 生成质量报告
        report_gen = QualityReport()
        report = report_gen.generate_report(
            phys_validated,
            dev_validated,
            self.structure_db.get_structures_by_paper(paper_id)
        )
        report_gen.save_report(report, str(PROCESSED_DIR / paper_id / "quality_report.json"))
        
        logger.info(f"✅ 论文 {paper_id} 处理完成")
        logger.info(f"=" * 80)
    
    def export_ml_datasets(self, output_dir: str):
        """
        导出机器学习数据集
        
        Args:
            output_dir: 输出目录
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info("导出机器学习数据集...")
        
        # 导出ΔE_ST数据集
        self.dataset_builder.export_ml_dataset_delta_est(
            str(output_path / "dataset_delta_est.json")
        )
        
        # 导出FWHM数据集
        self.dataset_builder.export_ml_dataset_fwhm(
            str(output_path / "dataset_fwhm.json")
        )
        
        # 导出EQE数据集
        self.dataset_builder.export_ml_dataset_eqe(
            str(output_path / "dataset_eqe.json")
        )
        
        # 导出完整数据库
        self.dataset_builder.export_full_database_to_csv(str(output_path / "full_database"))
        
        # 导出统计信息
        self.dataset_builder.export_statistics(str(output_path / "statistics.json"))
        
        logger.info(f"✅ 所有数据集已导出到 {output_dir}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="TADF数据抽取系统")
    parser.add_argument("--mode", choices=["single", "batch", "export"], required=True,
                       help="运行模式: single-处理单个PDF, batch-批量处理, export-导出数据集")
    parser.add_argument("--paper-id", help="论文ID（single模式必需）")
    parser.add_argument("--pdf-path", help="PDF文件路径（single模式必需）")
    parser.add_argument("--pdf-dir", help="PDF目录路径（batch模式必需）")
    parser.add_argument("--output-dir", help="输出目录（export模式必需）")
    
    args = parser.parse_args()
    
    pipeline = TADFExtractionPipeline()
    
    if args.mode == "single":
        if not args.paper_id or not args.pdf_path:
            logger.error("single模式需要提供 --paper-id 和 --pdf-path")
            return
        
        pipeline.run_full_pipeline(args.paper_id, args.pdf_path)
    
    elif args.mode == "batch":
        if not args.pdf_dir:
            logger.error("batch模式需要提供 --pdf-dir")
            return
        
        pdf_dir = Path(args.pdf_dir)
        pdf_files = list(pdf_dir.glob("*.pdf"))
        
        logger.info(f"找到 {len(pdf_files)} 个PDF文件")
        
        for i, pdf_path in enumerate(pdf_files, 1):
            paper_id = pdf_path.stem
            logger.info(f"\n处理进度: {i}/{len(pdf_files)}")
            
            try:
                pipeline.run_full_pipeline(paper_id, str(pdf_path))
            except Exception as e:
                logger.error(f"处理 {paper_id} 时出错: {e}")
                continue
    
    elif args.mode == "export":
        if not args.output_dir:
            logger.error("export模式需要提供 --output-dir")
            return
        
        pipeline.export_ml_datasets(args.output_dir)
    
    logger.info("所有任务完成")


if __name__ == "__main__":
    main()

