#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体对齐与统一ID模块
"""

import hashlib
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from utils.logger import setup_logger
from config import DATABASE_DIR, MOLECULES_SCHEMA

logger = setup_logger(__name__)


class EntityAligner:
    """实体对齐器 - 建立化合物统一ID体系"""
    
    def __init__(self, db_path: Path = DATABASE_DIR / "molecules.db"):
        """
        初始化实体对齐器
        
        Args:
            db_path: 分子数据库路径
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建molecules表
        fields = ", ".join([f"{k} {v}" for k, v in MOLECULES_SCHEMA.items()])
        cursor.execute(f"CREATE TABLE IF NOT EXISTS molecules ({fields})")
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paper_local ON molecules(paper_id, paper_local_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_smiles ON molecules(smiles)")
        
        conn.commit()
        conn.close()
        logger.info(f"分子数据库已初始化: {self.db_path}")
    
    def align_compounds(self, paper_id: str, structure_data: List[Dict],
                       photophysical_data: List[Dict], device_data: List[Dict],
                       compound_mapping: Optional[Dict[str, str]] = None) -> Dict:
        """
        对齐化合物信息
        
        Args:
            paper_id: 论文ID
            structure_data: 结构识别数据
            photophysical_data: 光物性数据
            device_data: 器件数据
            compound_mapping: 化合物标签到名称的映射
            
        Returns:
            对齐统计信息
        """
        logger.info(f"开始对齐论文 {paper_id} 的化合物数据")
        
        # 1. 收集所有化合物标签
        all_labels = set()
        
        # 从结构数据中获取标签（需要从figure caption中解析）
        structure_labels = self._extract_labels_from_structures(structure_data)
        all_labels.update(structure_labels)
        
        # 从光物性数据中获取标签
        for record in photophysical_data:
            if 'paper_local_id' in record and record['paper_local_id']:
                all_labels.add(record['paper_local_id'])
        
        # 从器件数据中获取标签
        for record in device_data:
            if 'paper_local_id' in record and record['paper_local_id']:
                all_labels.add(record['paper_local_id'])
        
        logger.info(f"找到 {len(all_labels)} 个化合物标签: {sorted(all_labels)}")
        
        # 2. 为每个标签创建compound记录
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        aligned_count = 0
        unaligned_count = 0
        
        for label in all_labels:
            # 查找对应的结构
            smiles = self._find_smiles_for_label(label, structure_data, compound_mapping)
            
            # 查找名称
            name = compound_mapping.get(label, "") if compound_mapping else ""
            
            # 生成compound_id
            if smiles:
                compound_id = self._generate_compound_id(smiles)
            else:
                compound_id = f"{paper_id}_{label}"
                unaligned_count += 1
            
            # 查找或创建记录
            cursor.execute("SELECT compound_id FROM molecules WHERE compound_id = ?", (compound_id,))
            existing = cursor.fetchone()
            
            if not existing:
                # 插入新记录
                cursor.execute("""
                    INSERT INTO molecules (compound_id, paper_id, paper_local_id, name, smiles, class, 
                                         structure_figure_id, global_confidence, source_info)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (compound_id, paper_id, label, name, smiles, None, None, None, None))
                aligned_count += 1
            else:
                # 更新记录（添加新的paper来源）
                cursor.execute("""
                    UPDATE molecules 
                    SET source_info = COALESCE(source_info, '') || '; ' || ?
                    WHERE compound_id = ?
                """, (f"{paper_id}:{label}", compound_id))
        
        conn.commit()
        conn.close()
        
        stats = {
            "paper_id": paper_id,
            "total_labels": len(all_labels),
            "aligned": aligned_count,
            "unaligned": unaligned_count
        }
        
        logger.info(f"✅ 对齐完成: {stats}")
        return stats
    
    def _extract_labels_from_structures(self, structure_data: List[Dict]) -> List[str]:
        """
        从结构数据中提取化合物标签
        
        Args:
            structure_data: 结构识别数据
            
        Returns:
            标签列表
        """
        # 这里需要从figure caption或其他元数据中解析标签
        # 简化处理：假设structure_figure_id包含标签信息
        labels = []
        for struct in structure_data:
            # 实际应用中需要更复杂的解析逻辑
            figure_id = struct.get('structure_figure_id', '')
            # 简单示例：假设figure_id格式为 paper_fig_1
            # 实际需要从caption中提取
            pass
        return labels
    
    def _find_smiles_for_label(self, label: str, structure_data: List[Dict],
                               compound_mapping: Optional[Dict] = None) -> Optional[str]:
        """
        为标签查找对应的SMILES
        
        Args:
            label: 化合物标签
            structure_data: 结构数据
            compound_mapping: 标签映射
            
        Returns:
            SMILES字符串
        """
        # 简化处理：根据索引匹配
        # 实际应用中需要更复杂的匹配逻辑
        for struct in structure_data:
            # 这里需要实现标签与结构的匹配逻辑
            # 可能需要从caption或其他元数据中获取对应关系
            pass
        
        return None
    
    def _generate_compound_id(self, smiles: str) -> str:
        """
        根据SMILES生成全局compound_id
        
        Args:
            smiles: 标准化的SMILES
            
        Returns:
            compound_id
        """
        # 使用SMILES的哈希作为ID
        smiles_normalized = self._normalize_smiles(smiles)
        hash_value = hashlib.md5(smiles_normalized.encode()).hexdigest()[:12]
        return f"cmp_{hash_value}"
    
    def _normalize_smiles(self, smiles: str) -> str:
        """
        标准化SMILES
        
        Args:
            smiles: 原始SMILES
            
        Returns:
            标准化的SMILES
        """
        try:
            from rdkit import Chem
            mol = Chem.MolFromSmiles(smiles)
            if mol:
                return Chem.MolToSmiles(mol, canonical=True)
        except ImportError:
            logger.warning("RDKit未安装，使用原始SMILES")
        except Exception as e:
            logger.error(f"SMILES标准化失败: {e}")
        
        return smiles
    
    def get_compound_by_id(self, compound_id: str) -> Optional[Dict]:
        """
        根据ID获取化合物信息
        
        Args:
            compound_id: 化合物ID
            
        Returns:
            化合物信息字典
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM molecules WHERE compound_id = ?", (compound_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def find_compound_by_paper_local_id(self, paper_id: str, paper_local_id: str) -> Optional[str]:
        """
        根据论文内部ID查找全局compound_id
        
        Args:
            paper_id: 论文ID
            paper_local_id: 论文内部标签
            
        Returns:
            compound_id
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT compound_id FROM molecules WHERE paper_id = ? AND paper_local_id = ?",
            (paper_id, paper_local_id)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row[0]
        return None
    
    def map_data_to_compounds(self, paper_id: str, data_records: List[Dict],
                             data_type: str) -> Tuple[List[Dict], List[Dict]]:
        """
        将数据记录映射到compound_id
        
        Args:
            paper_id: 论文ID
            data_records: 数据记录列表
            data_type: 数据类型（photophysical/device）
            
        Returns:
            (已映射的记录列表, 未映射的记录列表)
        """
        mapped = []
        unmapped = []
        
        for record in data_records:
            paper_local_id = record.get('paper_local_id')
            if not paper_local_id:
                unmapped.append(record)
                continue
            
            compound_id = self.find_compound_by_paper_local_id(paper_id, paper_local_id)
            if compound_id:
                record['compound_id'] = compound_id
                mapped.append(record)
            else:
                unmapped.append(record)
        
        logger.info(f"{data_type} 数据映射: {len(mapped)} 成功, {len(unmapped)} 失败")
        return mapped, unmapped
    
    def export_compounds_to_json(self, output_path: str):
        """
        导出所有化合物到JSON
        
        Args:
            output_path: 输出文件路径
        """
        import json
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM molecules ORDER BY compound_id")
        rows = cursor.fetchall()
        conn.close()
        
        compounds = [dict(row) for row in rows]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(compounds, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ 导出 {len(compounds)} 个化合物到 {output_path}")


class CompoundMatcher:
    """化合物匹配器 - 使用LLM辅助匹配"""
    
    def __init__(self, api_key: str):
        """
        初始化化合物匹配器
        
        Args:
            api_key: API密钥
        """
        self.api_key = api_key
        # 可以添加LLM调用逻辑来辅助匹配
    
    def match_label_to_structure(self, label: str, caption: str, 
                                available_structures: List[Dict]) -> Optional[str]:
        """
        使用LLM匹配标签到结构
        
        Args:
            label: 化合物标签
            caption: 图注文字
            available_structures: 可用的结构列表
            
        Returns:
            匹配的structure_figure_id
        """
        # 这里可以使用LLM来智能匹配
        # 简化实现：基于规则匹配
        
        # 如果caption中明确提到了标签和图的对应关系
        # 例如："Chemical structures of compounds 1-4"
        # 可以通过正则表达式或LLM来解析
        
        return None

