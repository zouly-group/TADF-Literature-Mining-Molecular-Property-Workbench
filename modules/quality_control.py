#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
质量控制与校验模块
"""

import json
import time
import requests
from typing import Dict, List, Tuple
from utils.logger import setup_logger
from config import (
    LAMBDA_RANGE,
    FWHM_RANGE,
    DELTA_EST_RANGE,
    PHI_PL_RANGE,
    EQE_RANGE,
    DASHSCOPE_API_KEY,
    QWEN_CHAT_ENDPOINT,
    MODEL_NAME,
    TEMPERATURE,
    MAX_RETRY,
    SLEEP_BETWEEN,
    TIMEOUT_SEC
)

logger = setup_logger(__name__)


class QualityController:
    """质量控制器 - 自动规则校验"""
    
    def __init__(self):
        """初始化质量控制器"""
        self.validation_rules = self._build_validation_rules()
    
    def _build_validation_rules(self) -> Dict:
        """构建验证规则"""
        return {
            "lambda_PL_nm": {
                "range": LAMBDA_RANGE,
                "type": "float",
                "nullable": True
            },
            "lambda_em_nm": {
                "range": LAMBDA_RANGE,
                "type": "float",
                "nullable": True
            },
            "FWHM_nm": {
                "range": FWHM_RANGE,
                "type": "float",
                "nullable": True
            },
            "Delta_EST_eV": {
                "range": DELTA_EST_RANGE,
                "type": "float",
                "nullable": True,
                "warning_threshold": 1.0  # >1.0标记为可疑
            },
            "Phi_PL": {
                "range": PHI_PL_RANGE,
                "type": "float",
                "nullable": True
            },
            "EQE_max_percent": {
                "range": EQE_RANGE,
                "type": "float",
                "nullable": True
            }
        }
    
    def validate_photophysical_record(self, record: Dict) -> Tuple[str, List[str]]:
        """
        验证光物性记录
        
        Args:
            record: 光物性数据记录
            
        Returns:
            (质量标记, 问题列表)
        """
        issues = []
        
        # 检查波长
        lambda_pl = record.get("lambda_PL_nm")
        if lambda_pl is not None:
            if not (LAMBDA_RANGE[0] <= lambda_pl <= LAMBDA_RANGE[1]):
                issues.append(f"lambda_PL_nm={lambda_pl} 超出合理范围 {LAMBDA_RANGE}")
        
        lambda_em = record.get("lambda_em_nm")
        if lambda_em is not None:
            if not (LAMBDA_RANGE[0] <= lambda_em <= LAMBDA_RANGE[1]):
                issues.append(f"lambda_em_nm={lambda_em} 超出合理范围 {LAMBDA_RANGE}")
        
        # 检查FWHM
        fwhm = record.get("FWHM_nm")
        if fwhm is not None:
            if not (FWHM_RANGE[0] <= fwhm <= FWHM_RANGE[1]):
                issues.append(f"FWHM_nm={fwhm} 超出合理范围 {FWHM_RANGE}")
        
        # 检查ΔE_ST
        delta_est = record.get("Delta_EST_eV")
        if delta_est is not None:
            if delta_est < 0:
                issues.append(f"Delta_EST_eV={delta_est} 为负值，不合理")
            elif delta_est > 1.0:
                issues.append(f"Delta_EST_eV={delta_est} > 1.0 eV，可能不是TADF材料，需确认")
        
        # 检查量子产率
        phi_pl = record.get("Phi_PL")
        if phi_pl is not None:
            if not (PHI_PL_RANGE[0] <= phi_pl <= PHI_PL_RANGE[1]):
                issues.append(f"Phi_PL={phi_pl} 超出范围 {PHI_PL_RANGE}")
        
        # 检查寿命数值是否合理
        tau_prompt = record.get("tau_prompt_ns")
        if tau_prompt is not None and tau_prompt < 0:
            issues.append(f"tau_prompt_ns={tau_prompt} 为负值")
        
        tau_delayed = record.get("tau_delayed_us")
        if tau_delayed is not None and tau_delayed < 0:
            issues.append(f"tau_delayed_us={tau_delayed} 为负值")
        
        # 确定质量标记
        if len(issues) == 0:
            quality_flag = "valid"
        elif any("超出" in issue or "为负值" in issue for issue in issues):
            quality_flag = "invalid"
        else:
            quality_flag = "suspect"
        
        return quality_flag, issues
    
    def validate_device_record(self, record: Dict) -> Tuple[str, List[str]]:
        """
        验证器件记录
        
        Args:
            record: 器件数据记录
            
        Returns:
            (质量标记, 问题列表)
        """
        issues = []
        
        # 检查EL波长
        lambda_el = record.get("lambda_EL_nm")
        if lambda_el is not None:
            if not (LAMBDA_RANGE[0] <= lambda_el <= LAMBDA_RANGE[1]):
                issues.append(f"lambda_EL_nm={lambda_el} 超出合理范围 {LAMBDA_RANGE}")
        
        # 检查EQE
        eqe_max = record.get("EQE_max_percent")
        if eqe_max is not None:
            if not (EQE_RANGE[0] <= eqe_max <= EQE_RANGE[1]):
                issues.append(f"EQE_max_percent={eqe_max} 超出范围 {EQE_RANGE}")
        
        # 检查CIE坐标
        cie_x = record.get("CIE_x")
        cie_y = record.get("CIE_y")
        if cie_x is not None and not (0 <= cie_x <= 1):
            issues.append(f"CIE_x={cie_x} 超出范围 [0, 1]")
        if cie_y is not None and not (0 <= cie_y <= 1):
            issues.append(f"CIE_y={cie_y} 超出范围 [0, 1]")
        
        # 检查亮度
        l_max = record.get("L_max_cd_m2")
        if l_max is not None and l_max < 0:
            issues.append(f"L_max_cd_m2={l_max} 为负值")
        
        # 确定质量标记
        if len(issues) == 0:
            quality_flag = "valid"
        elif any("超出" in issue or "为负值" in issue for issue in issues):
            quality_flag = "invalid"
        else:
            quality_flag = "suspect"
        
        return quality_flag, issues
    
    def validate_smiles(self, smiles: str) -> Tuple[bool, str]:
        """
        验证SMILES结构合理性
        
        Args:
            smiles: SMILES字符串
            
        Returns:
            (是否有效, 错误信息)
        """
        if not smiles:
            return False, "Empty SMILES"
        
        try:
            from rdkit import Chem
            from rdkit.Chem import Descriptors
            
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return False, "Cannot parse SMILES"
            
            # 检查分子量（TADF材料通常不会太小或太大）
            mw = Descriptors.MolWt(mol)
            if mw < 100:
                return False, f"Molecular weight too small: {mw:.1f}"
            elif mw > 2000:
                return False, f"Molecular weight too large: {mw:.1f}"
            
            # 检查原子数
            num_atoms = mol.GetNumAtoms()
            if num_atoms < 10:
                return False, f"Too few atoms: {num_atoms}"
            
            return True, ""
            
        except ImportError:
            logger.warning("RDKit未安装，跳过详细验证")
            return True, ""
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def batch_validate_photophysical(self, records: List[Dict]) -> List[Dict]:
        """
        批量验证光物性记录
        
        Args:
            records: 记录列表
            
        Returns:
            添加了质量标记的记录列表
        """
        logger.info(f"开始批量验证 {len(records)} 条光物性记录")
        
        valid_count = 0
        suspect_count = 0
        invalid_count = 0
        
        for record in records:
            quality_flag, issues = self.validate_photophysical_record(record)
            record['quality_flag'] = quality_flag
            record['quality_issues'] = issues
            
            if quality_flag == "valid":
                valid_count += 1
            elif quality_flag == "suspect":
                suspect_count += 1
            else:
                invalid_count += 1
        
        logger.info(f"✅ 验证完成: 有效={valid_count}, 可疑={suspect_count}, 无效={invalid_count}")
        return records
    
    def batch_validate_device(self, records: List[Dict]) -> List[Dict]:
        """
        批量验证器件记录
        
        Args:
            records: 记录列表
            
        Returns:
            添加了质量标记的记录列表
        """
        logger.info(f"开始批量验证 {len(records)} 条器件记录")
        
        valid_count = 0
        suspect_count = 0
        invalid_count = 0
        
        for record in records:
            quality_flag, issues = self.validate_device_record(record)
            record['quality_flag'] = quality_flag
            record['quality_issues'] = issues
            
            if quality_flag == "valid":
                valid_count += 1
            elif quality_flag == "suspect":
                suspect_count += 1
            else:
                invalid_count += 1
        
        logger.info(f"✅ 验证完成: 有效={valid_count}, 可疑={suspect_count}, 无效={invalid_count}")
        return records


class LLMReviewer:
    """LLM审核器 - 使用LLM审核抽取结果"""
    
    def __init__(self, api_key: str = DASHSCOPE_API_KEY):
        """
        初始化LLM审核器
        
        Args:
            api_key: API密钥
        """
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def _call_llm(self, system_prompt: str, user_message: str) -> str:
        """调用LLM"""
        for attempt in range(MAX_RETRY):
            try:
                payload = {
                    "model": MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": TEMPERATURE,
                }
                
                response = requests.post(
                    QWEN_CHAT_ENDPOINT,
                    headers=self.headers,
                    json=payload,
                    timeout=TIMEOUT_SEC
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return content
                    
            except Exception as e:
                logger.error(f"调用LLM出错 (尝试 {attempt+1}/{MAX_RETRY}): {e}")
            
            if attempt < MAX_RETRY - 1:
                time.sleep(SLEEP_BETWEEN)
        
        return ""
    
    def review_extraction(self, extracted_data: Dict, source_table: str) -> Dict:
        """
        审核抽取结果
        
        Args:
            extracted_data: 抽取的数据
            source_table: 原始表格内容
            
        Returns:
            审核结果
        """
        system_prompt = """你是一个严谨的科学数据审核专家。请审核从表格中抽取的数据是否准确。

审核要点：
1. 数据是否与表格内容一致
2. 是否存在列错位或数据混淆
3. 单位是否正确转换
4. 是否有明显错误

输出JSON格式：
{
    "status": "ok" 或 "needs_review",
    "issues": ["问题描述1", "问题描述2", ...],
    "confidence": 0.0-1.0
}"""
        
        user_message = f"""原始表格：
{source_table}

抽取的数据：
{json.dumps(extracted_data, indent=2, ensure_ascii=False)}

请审核以上抽取结果的准确性。"""
        
        response = self._call_llm(system_prompt, user_message)
        
        try:
            review_result = json.loads(response)
            return review_result
        except:
            # 解析失败，返回默认结果
            return {"status": "needs_review", "issues": ["无法解析审核结果"], "confidence": 0.0}
    
    def batch_review(self, data_records: List[Dict], source_tables: List[str]) -> List[Dict]:
        """
        批量审核
        
        Args:
            data_records: 数据记录列表
            source_tables: 对应的原始表格列表
            
        Returns:
            添加了审核结果的记录列表
        """
        logger.info(f"开始LLM审核 {len(data_records)} 条记录")
        
        for i, (record, table) in enumerate(zip(data_records, source_tables), 1):
            if i % 10 == 0:
                logger.info(f"审核进度: {i}/{len(data_records)}")
            
            review = self.review_extraction(record, table)
            record['llm_review'] = review
            
            # 避免请求过快
            time.sleep(0.5)
        
        logger.info("✅ LLM审核完成")
        return data_records


class QualityReport:
    """质量报告生成器"""
    
    def __init__(self):
        """初始化质量报告生成器"""
        pass
    
    def generate_report(self, photophysical_data: List[Dict], 
                       device_data: List[Dict],
                       structure_data: List[Dict]) -> Dict:
        """
        生成质量报告
        
        Args:
            photophysical_data: 光物性数据
            device_data: 器件数据
            structure_data: 结构数据
            
        Returns:
            质量报告字典
        """
        report = {
            "photophysical": self._analyze_quality(photophysical_data),
            "device": self._analyze_quality(device_data),
            "structure": self._analyze_structure_quality(structure_data)
        }
        
        logger.info(f"✅ 质量报告生成完成")
        return report
    
    def _analyze_quality(self, data: List[Dict]) -> Dict:
        """分析数据质量"""
        total = len(data)
        if total == 0:
            return {"total": 0}
        
        valid = sum(1 for r in data if r.get('quality_flag') == 'valid')
        suspect = sum(1 for r in data if r.get('quality_flag') == 'suspect')
        invalid = sum(1 for r in data if r.get('quality_flag') == 'invalid')
        
        return {
            "total": total,
            "valid": valid,
            "suspect": suspect,
            "invalid": invalid,
            "valid_rate": valid / total if total > 0 else 0
        }
    
    def _analyze_structure_quality(self, data: List[Dict]) -> Dict:
        """分析结构质量"""
        total = len(data)
        if total == 0:
            return {"total": 0}
        
        ok = sum(1 for r in data if r.get('status') == 'ok')
        low_conf = sum(1 for r in data if r.get('status') == 'low_confidence')
        failed = sum(1 for r in data if r.get('status') == 'parse_failed')
        
        return {
            "total": total,
            "ok": ok,
            "low_confidence": low_conf,
            "parse_failed": failed,
            "success_rate": ok / total if total > 0 else 0
        }
    
    def save_report(self, report: Dict, output_path: str):
        """保存质量报告"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ 质量报告已保存到 {output_path}")

