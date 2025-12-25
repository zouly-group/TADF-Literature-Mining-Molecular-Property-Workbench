#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分子结构识别模块 - 使用DECIMER进行结构识别
"""

import json
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from utils.logger import setup_logger
from config import DECIMER_API_URL, DECIMER_TIMEOUT, SMILES_CONFIDENCE_THRESHOLD

logger = setup_logger(__name__)


class StructureRecognizer:
    """分子结构识别器 - 使用DECIMER"""
    
    def __init__(self, api_url: str = DECIMER_API_URL):
        """
        初始化结构识别器
        
        Args:
            api_url: DECIMER API URL
        """
        self.api_url = api_url
    
    def recognize_structure(self, image_path: str) -> Optional[Dict]:
        """
        识别单张结构图
        
        Args:
            image_path: 图片路径
            
        Returns:
            识别结果字典
        """
        if not Path(image_path).exists():
            logger.error(f"图片不存在: {image_path}")
            return None
        
        try:
            # 上传图片到DECIMER API
            with open(image_path, 'rb') as f:
                files = {'image': f}
                response = requests.post(
                    self.api_url,
                    files=files,
                    timeout=DECIMER_TIMEOUT
                )
            
            if response.status_code == 200:
                result = response.json()
                
                # 提取SMILES和置信度
                pred_smiles = result.get('smiles', '')
                token_confidences = result.get('token_confidences', [])
                
                # 计算全局置信度
                global_confidence = self._calculate_global_confidence(token_confidences)
                
                # 验证SMILES
                is_valid, error_msg = self._validate_smiles(pred_smiles)
                
                recognition_result = {
                    'pred_smiles': pred_smiles,
                    'global_confidence': global_confidence,
                    'token_confidences': token_confidences,
                    'is_valid': is_valid,
                    'error_msg': error_msg,
                    'status': self._determine_status(is_valid, global_confidence)
                }
                
                logger.info(f"✅ 结构识别成功: {Path(image_path).name} -> {pred_smiles[:50]}... (conf: {global_confidence:.3f})")
                return recognition_result
            else:
                logger.error(f"DECIMER API请求失败 ({response.status_code}): {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"结构识别出错: {e}")
            return None
    
    def _calculate_global_confidence(self, token_confidences: List) -> float:
        """
        计算全局置信度
        
        Args:
            token_confidences: token置信度列表
            
        Returns:
            全局置信度
        """
        if not token_confidences:
            return 0.0
        
        # 使用平均值作为全局置信度
        confidences = [tc.get('confidence', 0) if isinstance(tc, dict) else tc for tc in token_confidences]
        return sum(confidences) / len(confidences)
    
    def _validate_smiles(self, smiles: str) -> Tuple[bool, str]:
        """
        验证SMILES有效性
        
        Args:
            smiles: SMILES字符串
            
        Returns:
            (是否有效, 错误信息)
        """
        if not smiles:
            return False, "Empty SMILES"
        
        try:
            # 尝试使用RDKit验证
            from rdkit import Chem
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return False, "Invalid SMILES - cannot parse"
            
            # 检查是否有异常价态
            # （这里可以添加更多的化学合理性检查）
            return True, ""
            
        except ImportError:
            # 如果没有RDKit，进行基本的字符检查
            logger.warning("RDKit未安装，仅进行基本验证")
            if len(smiles) < 3:
                return False, "SMILES too short"
            return True, ""
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def _determine_status(self, is_valid: bool, confidence: float) -> str:
        """
        确定识别状态
        
        Args:
            is_valid: SMILES是否有效
            confidence: 置信度
            
        Returns:
            状态字符串
        """
        if not is_valid:
            return "parse_failed"
        elif confidence < SMILES_CONFIDENCE_THRESHOLD:
            return "low_confidence"
        else:
            return "ok"
    
    def recognize_batch(self, image_paths: List[str]) -> Dict[str, Dict]:
        """
        批量识别结构图
        
        Args:
            image_paths: 图片路径列表
            
        Returns:
            识别结果字典 {image_path: recognition_result}
        """
        results = {}
        total = len(image_paths)
        
        logger.info(f"开始批量识别 {total} 张结构图")
        
        for i, image_path in enumerate(image_paths, 1):
            logger.info(f"处理进度: {i}/{total}")
            result = self.recognize_structure(image_path)
            if result:
                results[image_path] = result
        
        # 统计
        ok_count = sum(1 for r in results.values() if r['status'] == 'ok')
        low_conf_count = sum(1 for r in results.values() if r['status'] == 'low_confidence')
        failed_count = sum(1 for r in results.values() if r['status'] == 'parse_failed')
        
        logger.info(f"✅ 批量识别完成: 成功={ok_count}, 低置信度={low_conf_count}, 失败={failed_count}")
        return results
    
    def save_results(self, results: Dict[str, Dict], output_path: str):
        """
        保存识别结果
        
        Args:
            results: 识别结果字典
            output_path: 输出文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ 识别结果已保存到 {output_path}")


class StructureDatabase:
    """结构数据库 - 管理识别后的结构数据"""
    
    def __init__(self):
        """初始化结构数据库"""
        self.structures = []
    
    def add_structure(self, paper_id: str, figure_id: str, image_path: str, 
                     recognition_result: Dict):
        """
        添加结构记录
        
        Args:
            paper_id: 论文ID
            figure_id: 图像ID
            image_path: 图片路径
            recognition_result: 识别结果
        """
        structure = {
            'paper_id': paper_id,
            'structure_figure_id': figure_id,
            'image_path': image_path,
            **recognition_result
        }
        self.structures.append(structure)
    
    def get_structures_by_paper(self, paper_id: str) -> List[Dict]:
        """
        获取指定论文的所有结构
        
        Args:
            paper_id: 论文ID
            
        Returns:
            结构列表
        """
        return [s for s in self.structures if s['paper_id'] == paper_id]
    
    def get_valid_structures(self) -> List[Dict]:
        """获取所有有效的结构"""
        return [s for s in self.structures if s['status'] == 'ok']
    
    def get_needs_review(self) -> List[Dict]:
        """获取需要人工审核的结构"""
        return [s for s in self.structures if s['status'] in ['low_confidence', 'parse_failed']]
    
    def export_to_json(self, output_path: str):
        """
        导出到JSON
        
        Args:
            output_path: 输出文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.structures, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ 导出 {len(self.structures)} 条结构记录到 {output_path}")

