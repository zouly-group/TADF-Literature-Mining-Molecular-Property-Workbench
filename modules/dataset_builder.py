#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据集构建与导出模块
"""

import json
import sqlite3
import csv
from pathlib import Path
from typing import Dict, List, Optional
from utils.logger import setup_logger
from config import DATABASE_DIR, PHOTOPHYSICS_SCHEMA, DEVICES_SCHEMA

logger = setup_logger(__name__)


class DatasetBuilder:
    """数据集构建器"""
    
    def __init__(self, db_dir: Path = DATABASE_DIR):
        """
        初始化数据集构建器
        
        Args:
            db_dir: 数据库目录
        """
        self.db_dir = db_dir
        self.photophysics_db = db_dir / "photophysics.db"
        self.devices_db = db_dir / "devices.db"
        self.molecules_db = db_dir / "molecules.db"
        
        self._init_databases()
    
    def _init_databases(self):
        """初始化数据库"""
        # 光物性数据库
        conn = sqlite3.connect(self.photophysics_db)
        cursor = conn.cursor()
        fields = ", ".join([f"{k} {v}" for k, v in PHOTOPHYSICS_SCHEMA.items()])
        cursor.execute(f"CREATE TABLE IF NOT EXISTS photophysics ({fields})")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_compound ON photophysics(compound_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paper ON photophysics(paper_id)")
        conn.commit()
        conn.close()
        
        # 器件数据库
        conn = sqlite3.connect(self.devices_db)
        cursor = conn.cursor()
        fields = ", ".join([f"{k} {v}" for k, v in DEVICES_SCHEMA.items()])
        cursor.execute(f"CREATE TABLE IF NOT EXISTS devices ({fields})")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_compound ON devices(emitter_compound_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paper ON devices(paper_id)")
        conn.commit()
        conn.close()
        
        logger.info("数据集数据库已初始化")
    
    def insert_photophysics_records(self, records: List[Dict]):
        """
        插入光物性记录
        
        Args:
            records: 记录列表
        """
        if not records:
            logger.warning("insert_photophysics_records: 记录列表为空")
            return
        
        logger.info(f"开始插入 {len(records)} 条光物性记录到数据库")
        conn = sqlite3.connect(str(self.photophysics_db))
        cursor = conn.cursor()
        
        inserted = 0
        updated = 0
        errors = 0
        
        for idx, record in enumerate(records):
            try:
                # 生成record_id（使用paper_id和paper_local_id确保唯一性）
                if 'record_id' not in record:
                    paper_id = record.get('paper_id', 'unknown')
                    paper_local_id = record.get('paper_local_id', 'unknown')
                    compound_id = record.get('compound_id', 'unknown')
                    record['record_id'] = f"{paper_id}_{paper_local_id}_{compound_id}"
                
                # 确保paper_id存在
                if 'paper_id' not in record:
                    logger.warning(f"记录 {idx} 缺少paper_id，跳过")
                    errors += 1
                    continue
                
                # 准备插入数据
                fields = [k for k in PHOTOPHYSICS_SCHEMA.keys() if k in record]
                if not fields:
                    logger.warning(f"记录 {idx} 没有有效字段，跳过")
                    errors += 1
                    continue
                
                placeholders = ", ".join(["?" for _ in fields])
                field_names = ", ".join(fields)
                values = [record[f] for f in fields]
                
                # 检查记录是否已存在
                cursor.execute("SELECT record_id FROM photophysics WHERE record_id = ?", (record['record_id'],))
                exists = cursor.fetchone()
                
                cursor.execute(
                    f"INSERT OR REPLACE INTO photophysics ({field_names}) VALUES ({placeholders})",
                    values
                )
                if exists:
                    updated += 1
                else:
                    inserted += 1
                    
            except Exception as e:
                errors += 1
                logger.error(f"插入光物性记录失败 (记录 {idx}): {e}")
                logger.error(f"记录ID: {record.get('record_id', 'unknown')}")
                logger.error(f"字段数: {len(fields) if 'fields' in locals() else 0}")
                import traceback
                logger.error(traceback.format_exc())
        
        conn.commit()
        conn.close()
        
        if errors > 0:
            logger.warning(f"插入过程中有 {errors} 条记录失败")
        if updated > 0:
            logger.info(f"✅ 插入 {inserted} 条新记录，更新 {updated} 条已有记录到光物性数据库")
        else:
            logger.info(f"✅ 插入 {inserted} 条光物性记录")
    
    def insert_device_records(self, records: List[Dict]):
        """
        插入器件记录
        
        Args:
            records: 记录列表
        """
        if not records:
            logger.warning("insert_device_records: 记录列表为空")
            return
        
        logger.info(f"开始插入 {len(records)} 条器件记录到数据库")
        conn = sqlite3.connect(str(self.devices_db))
        cursor = conn.cursor()
        
        inserted = 0
        updated = 0
        errors = 0
        
        for idx, record in enumerate(records):
            try:
                # 生成device_id（使用paper_id和paper_local_id确保唯一性）
                if 'device_id' not in record:
                    paper_id = record.get('paper_id', 'unknown')
                    paper_local_id = record.get('paper_local_id', 'unknown')
                    emitter_compound_id = record.get('emitter_compound_id', 'unknown')
                    record['device_id'] = f"{paper_id}_{paper_local_id}_{emitter_compound_id}"
                
                # 确保paper_id存在
                if 'paper_id' not in record:
                    logger.warning(f"记录 {idx} 缺少paper_id，跳过")
                    errors += 1
                    continue
                
                # 准备插入数据
                fields = [k for k in DEVICES_SCHEMA.keys() if k in record]
                if not fields:
                    logger.warning(f"记录 {idx} 没有有效字段，跳过")
                    errors += 1
                    continue
                
                placeholders = ", ".join(["?" for _ in fields])
                field_names = ", ".join(fields)
                values = [record[f] for f in fields]
                
                # 检查记录是否已存在
                cursor.execute("SELECT device_id FROM devices WHERE device_id = ?", (record['device_id'],))
                exists = cursor.fetchone()
                
                cursor.execute(
                    f"INSERT OR REPLACE INTO devices ({field_names}) VALUES ({placeholders})",
                    values
                )
                if exists:
                    updated += 1
                else:
                    inserted += 1
                    
            except Exception as e:
                errors += 1
                logger.error(f"插入器件记录失败 (记录 {idx}): {e}")
                logger.error(f"记录ID: {record.get('device_id', 'unknown')}")
                logger.error(f"字段数: {len(fields) if 'fields' in locals() else 0}")
                import traceback
                logger.error(traceback.format_exc())
        
        conn.commit()
        conn.close()
        
        if errors > 0:
            logger.warning(f"插入过程中有 {errors} 条记录失败")
        if updated > 0:
            logger.info(f"✅ 插入 {inserted} 条新记录，更新 {updated} 条已有记录到器件数据库")
        else:
            logger.info(f"✅ 插入 {inserted} 条器件记录")
    
    def export_ml_dataset_delta_est(self, output_path: str, quality_filter: str = "valid"):
        """
        导出ΔE_ST回归数据集
        
        Args:
            output_path: 输出文件路径
            quality_filter: 质量过滤标准
        """
        logger.info("构建ΔE_ST回归数据集")
        
        # 连接数据库
        conn_phys = sqlite3.connect(self.photophysics_db)
        conn_mol = sqlite3.connect(self.molecules_db)
        
        conn_phys.row_factory = sqlite3.Row
        conn_mol.row_factory = sqlite3.Row
        
        cursor_phys = conn_phys.cursor()
        cursor_mol = conn_mol.cursor()
        
        # 查询有效的ΔE_ST数据
        query = """
            SELECT * FROM photophysics 
            WHERE Delta_EST_eV IS NOT NULL 
            AND quality_flag = ?
        """
        cursor_phys.execute(query, (quality_filter,))
        records = cursor_phys.fetchall()
        
        # 构建数据集
        dataset = []
        for record in records:
            compound_id = record['compound_id']
            
            # 获取分子信息
            cursor_mol.execute("SELECT * FROM molecules WHERE compound_id = ?", (compound_id,))
            mol_row = cursor_mol.fetchone()
            
            if mol_row and mol_row['smiles']:
                data_point = {
                    'compound_id': compound_id,
                    'smiles': mol_row['smiles'],
                    'Delta_EST_eV': record['Delta_EST_eV'],
                    'environment_type': record['environment_type'],
                    'temperature_K': record['temperature_K'],
                    'paper_id': record['paper_id']
                }
                dataset.append(data_point)
        
        # 导出
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        conn_phys.close()
        conn_mol.close()
        
        logger.info(f"✅ 导出ΔE_ST数据集: {len(dataset)} 条记录到 {output_path}")
    
    def export_ml_dataset_fwhm(self, output_path: str, quality_filter: str = "valid"):
        """
        导出FWHM回归数据集
        
        Args:
            output_path: 输出文件路径
            quality_filter: 质量过滤标准
        """
        logger.info("构建FWHM回归数据集")
        
        conn_phys = sqlite3.connect(self.photophysics_db)
        conn_mol = sqlite3.connect(self.molecules_db)
        
        conn_phys.row_factory = sqlite3.Row
        conn_mol.row_factory = sqlite3.Row
        
        cursor_phys = conn_phys.cursor()
        cursor_mol = conn_mol.cursor()
        
        # 查询有效的FWHM数据
        query = """
            SELECT * FROM photophysics 
            WHERE FWHM_nm IS NOT NULL 
            AND quality_flag = ?
        """
        cursor_phys.execute(query, (quality_filter,))
        records = cursor_phys.fetchall()
        
        # 构建数据集
        dataset = []
        for record in records:
            compound_id = record['compound_id']
            
            cursor_mol.execute("SELECT * FROM molecules WHERE compound_id = ?", (compound_id,))
            mol_row = cursor_mol.fetchone()
            
            if mol_row and mol_row['smiles']:
                data_point = {
                    'compound_id': compound_id,
                    'smiles': mol_row['smiles'],
                    'FWHM_nm': record['FWHM_nm'],
                    'lambda_PL_nm': record['lambda_PL_nm'],
                    'environment_type': record['environment_type'],
                    'paper_id': record['paper_id']
                }
                dataset.append(data_point)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        conn_phys.close()
        conn_mol.close()
        
        logger.info(f"✅ 导出FWHM数据集: {len(dataset)} 条记录到 {output_path}")
    
    def export_ml_dataset_eqe(self, output_path: str, quality_filter: str = "valid"):
        """
        导出EQE预测数据集
        
        Args:
            output_path: 输出文件路径
            quality_filter: 质量过滤标准
        """
        logger.info("构建EQE预测数据集")
        
        conn_dev = sqlite3.connect(self.devices_db)
        conn_mol = sqlite3.connect(self.molecules_db)
        
        conn_dev.row_factory = sqlite3.Row
        conn_mol.row_factory = sqlite3.Row
        
        cursor_dev = conn_dev.cursor()
        cursor_mol = conn_mol.cursor()
        
        # 查询有效的EQE数据
        query = """
            SELECT * FROM devices 
            WHERE EQE_max_percent IS NOT NULL 
            AND quality_flag = ?
        """
        cursor_dev.execute(query, (quality_filter,))
        records = cursor_dev.fetchall()
        
        # 构建数据集
        dataset = []
        for record in records:
            compound_id = record['emitter_compound_id']
            
            cursor_mol.execute("SELECT * FROM molecules WHERE compound_id = ?", (compound_id,))
            mol_row = cursor_mol.fetchone()
            
            if mol_row and mol_row['smiles']:
                data_point = {
                    'compound_id': compound_id,
                    'smiles': mol_row['smiles'],
                    'EQE_max_percent': record['EQE_max_percent'],
                    'host': record['host'],
                    'doping_wt_percent': record['doping_wt_percent'],
                    'lambda_EL_nm': record['lambda_EL_nm'],
                    'paper_id': record['paper_id']
                }
                dataset.append(data_point)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        conn_dev.close()
        conn_mol.close()
        
        logger.info(f"✅ 导出EQE数据集: {len(dataset)} 条记录到 {output_path}")
    
    def export_full_database_to_csv(self, output_dir: str):
        """
        导出完整数据库到CSV
        
        Args:
            output_dir: 输出目录
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 导出光物性数据
        self._export_table_to_csv(
            self.photophysics_db,
            "photophysics",
            output_path / "photophysics.csv"
        )
        
        # 导出器件数据
        self._export_table_to_csv(
            self.devices_db,
            "devices",
            output_path / "devices.csv"
        )
        
        # 导出分子数据
        self._export_table_to_csv(
            self.molecules_db,
            "molecules",
            output_path / "molecules.csv"
        )
        
        logger.info(f"✅ 完整数据库已导出到 {output_dir}")
    
    def _export_table_to_csv(self, db_path: Path, table_name: str, output_path: Path):
        """导出表格到CSV"""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        if rows:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))
            
            logger.info(f"✅ 导出 {table_name}: {len(rows)} 条记录到 {output_path}")
        else:
            logger.warning(f"表 {table_name} 为空")
        
        conn.close()
    
    def get_statistics(self) -> Dict:
        """
        获取数据集统计信息
        
        Returns:
            统计信息字典
        """
        stats = {}
        
        # 光物性统计
        conn = sqlite3.connect(self.photophysics_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM photophysics")
        stats['photophysics_total'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM photophysics WHERE quality_flag = 'valid'")
        stats['photophysics_valid'] = cursor.fetchone()[0]
        conn.close()
        
        # 器件统计
        conn = sqlite3.connect(self.devices_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM devices")
        stats['devices_total'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM devices WHERE quality_flag = 'valid'")
        stats['devices_valid'] = cursor.fetchone()[0]
        conn.close()
        
        # 分子统计
        conn = sqlite3.connect(self.molecules_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM molecules")
        stats['molecules_total'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM molecules WHERE smiles IS NOT NULL")
        stats['molecules_with_smiles'] = cursor.fetchone()[0]
        conn.close()
        
        logger.info(f"数据集统计: {stats}")
        return stats
    
    def export_statistics(self, output_path: str):
        """
        导出统计信息
        
        Args:
            output_path: 输出文件路径
        """
        stats = self.get_statistics()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ 统计信息已保存到 {output_path}")

