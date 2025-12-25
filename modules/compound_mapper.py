#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
化合物映射模块 - 建立图片分割区域与化合物编号的对应关系
"""

import re
import json
from typing import Dict, List, Optional, Tuple
from utils.logger import setup_logger

logger = setup_logger(__name__)


class CompoundMapper:
    """化合物映射器 - 解析图注并建立映射关系"""
    
    def __init__(self):
        """初始化化合物映射器"""
        pass
    
    def parse_caption_for_compounds(self, caption: str) -> List[str]:
        """
        从图注中提取化合物编号
        
        Args:
            caption: 图注文字
            
        Returns:
            化合物编号列表（如['1', '2a', '2b', '3']）
        """
        if not caption:
            return []
        
        compounds = []
        
        # 模式1: "compounds 1-4" 或 "compounds 1, 2, 3"
        patterns = [
            r'compounds?\s+(\d+(?:[a-z])?(?:\s*[-,]\s*\d+(?:[a-z])?)*)',
            r'molecules?\s+(\d+(?:[a-z])?(?:\s*[-,]\s*\d+(?:[a-z])?)*)',
            r'structures?\s+of\s+(\d+(?:[a-z])?(?:\s*[-,]\s*\d+(?:[a-z])?)*)',
            r'\b(\d+[a-z]?)\s*(?:and|,)\s*(\d+[a-z]?)\b',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, caption.lower())
            for match in matches:
                text = match.group(1)
                
                # 解析范围（如"1-4"）
                if '-' in text and ',' not in text:
                    parts = text.split('-')
                    if len(parts) == 2:
                        try:
                            start = int(re.sub(r'[a-z]', '', parts[0].strip()))
                            end = int(re.sub(r'[a-z]', '', parts[1].strip()))
                            compounds.extend([str(i) for i in range(start, end + 1)])
                        except:
                            pass
                
                # 解析列表（如"1, 2, 3"或"1a, 1b, 2"）
                elif ',' in text:
                    items = [item.strip() for item in text.split(',')]
                    compounds.extend(items)
                
                # 单个化合物
                else:
                    compounds.append(text.strip())
        
        # 去重并排序
        compounds = list(set(compounds))
        compounds.sort(key=lambda x: (int(re.sub(r'[a-z]', '', x)), x))
        
        if compounds:
            logger.info(f"从图注中提取到化合物: {compounds}")
        
        return compounds
    
    def map_regions_to_compounds(self, 
                                split_info: List[Dict], 
                                caption: str) -> Dict[str, str]:
        """
        将分割区域映射到化合物编号
        
        Args:
            split_info: 图片分割信息
            caption: 图注
            
        Returns:
            映射字典 {region_id: compound_label}
        """
        # 从图注中提取化合物
        compounds = self.parse_caption_for_compounds(caption)
        
        if not compounds:
            logger.warning("图注中未找到化合物编号")
            return {}
        
        # 简单映射：按顺序对应
        mapping = {}
        
        for i, info in enumerate(split_info):
            region_id = info.get('region_id', i + 1)
            
            if i < len(compounds):
                compound_label = compounds[i]
                mapping[str(region_id)] = compound_label
                logger.info(f"映射: 区域{region_id} -> 化合物{compound_label}")
            else:
                logger.warning(f"区域{region_id}没有对应的化合物编号")
        
        return mapping
    
    def create_compound_structure_mapping(self,
                                        figure_id: str,
                                        original_image: str,
                                        split_info: List[Dict],
                                        caption: str,
                                        recognition_results: Optional[Dict[str, Dict]] = None) -> List[Dict]:
        """
        创建完整的化合物-结构映射
        
        Args:
            figure_id: 图片ID
            original_image: 原始图片路径
            split_info: 分割信息
            caption: 图注
            recognition_results: DECIMER识别结果（可选）
            
        Returns:
            映射记录列表
        """
        # 建立区域到化合物的映射
        region_mapping = self.map_regions_to_compounds(split_info, caption)
        
        records = []
        
        for info in split_info:
            region_id = str(info.get('region_id'))
            compound_label = region_mapping.get(region_id, f"unknown_{region_id}")
            split_path = info.get('split_path')
            
            # 获取SMILES（如果有识别结果）
            smiles = None
            confidence = None
            
            if recognition_results and split_path in recognition_results:
                result = recognition_results[split_path]
                smiles = result.get('pred_smiles')
                confidence = result.get('global_confidence')
            
            record = {
                'figure_id': figure_id,
                'original_image': original_image,
                'split_image': split_path,
                'region_id': region_id,
                'compound_label': compound_label,
                'smiles': smiles,
                'confidence': confidence,
                'caption': caption
            }
            
            records.append(record)
        
        return records
    
    def save_mapping(self, mapping_records: List[Dict], output_path: str):
        """
        保存映射结果
        
        Args:
            mapping_records: 映射记录
            output_path: 输出文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(mapping_records, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ 映射结果已保存: {output_path}")


def test_mapper():
    """测试化合物映射器"""
    print("=" * 60)
    print("化合物映射测试")
    print("=" * 60)
    
    mapper = CompoundMapper()
    
    # 测试用例
    test_cases = [
        "Chemical structures of compounds 1-4",
        "Molecular structures of 1a, 1b, and 2",
        "Scheme 1. Structures of p-Cz-BNCz, BNCz, and m-Cz-BNCz",
        "Figure 2. Chemical structures of molecules 5a-c and 6",
    ]
    
    for caption in test_cases:
        print(f"\n图注: {caption}")
        compounds = mapper.parse_caption_for_compounds(caption)
        print(f"提取: {compounds}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_mapper()

