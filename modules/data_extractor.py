#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据抽取模块 - 使用LLM从表格和文本中抽取数据
"""

import json
import time
import requests
from typing import Dict, List, Optional
from utils.logger import setup_logger
from config import (
    DASHSCOPE_API_KEY,
    QWEN_CHAT_ENDPOINT,
    MODEL_NAME,
    TEMPERATURE,
    MAX_RETRY,
    SLEEP_BETWEEN,
    TIMEOUT_SEC
)

logger = setup_logger(__name__)


class DataExtractor:
    """数据抽取器 - 使用LLM抽取光物性和器件数据"""
    
    def __init__(self, api_key: str = DASHSCOPE_API_KEY):
        """
        初始化数据抽取器
        
        Args:
            api_key: API密钥
        """
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def _call_llm(self, system_prompt: str, user_message: str) -> Optional[str]:
        """
        调用LLM
        
        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            
        Returns:
            LLM响应内容
        """
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
                else:
                    logger.warning(f"LLM API请求失败 ({response.status_code}): {response.text}")
                    
            except Exception as e:
                logger.error(f"调用LLM出错 (尝试 {attempt+1}/{MAX_RETRY}): {e}")
            
            if attempt < MAX_RETRY - 1:
                time.sleep(SLEEP_BETWEEN)
        
        return None
    
    def _parse_json_response(self, content: str) -> Optional[List[Dict]]:
        """
        解析LLM的JSON响应
        
        Args:
            content: LLM响应内容
            
        Returns:
            解析后的数据列表
        """
        try:
            # 尝试直接解析
            data = json.loads(content)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
        except json.JSONDecodeError:
            # 尝试提取JSON代码块
            import re
            json_match = re.search(r'```json\s*(\[.*?\]|\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return [data]
                except:
                    pass
        
        logger.warning(f"无法解析JSON响应: {content[:200]}...")
        return None
    
    def extract_photophysical_data(self, table_caption: str, markdown_table: str, 
                                   context_paragraphs: Optional[List[str]] = None) -> List[Dict]:
        """
        抽取光物性数据
        
        Args:
            table_caption: 表格标题
            markdown_table: Markdown格式的表格
            context_paragraphs: 相关段落列表
            
        Returns:
            光物性数据列表
        """
        system_prompt = """你是一个专业的科学数据抽取专家，专门从TADF（热活化延迟荧光）相关文献的表格中抽取光物性数据。

目标JSON Schema:
{
    "paper_local_id": "化合物在论文中的编号（如1, 2a, 3b等）",
    "name": "化合物名称（如果有）",
    "environment_type": "测量环境类型（solution/doped_film/neat_film/crystal/device）",
    "environment_detail": "环境详细信息（如溶剂、浓度等）",
    "host": "主体材料（如果是掺杂膜）",
    "doping_wt_percent": "掺杂浓度（wt%）",
    "temperature_K": "测量温度（K）",
    "lambda_PL_nm": "PL发射峰波长（nm）",
    "lambda_em_nm": "发射波长（nm）",
    "FWHM_nm": "半峰宽（nm）",
    "Phi_PL": "PL量子产率（0-1）",
    "Delta_EST_eV": "单三线态能级差（eV）",
    "tau_prompt_ns": "瞬态寿命（ns）",
    "tau_delayed_us": "延迟寿命（μs）",
    "k_r": "辐射速率常数",
    "k_ISC": "系间窜越速率常数",
    "k_RISC": "反向系间窜越速率常数"
}

抽取规则：
1. 严格按照表格内容抽取，不要猜测或编造数据
2. 缺失的字段用null表示
3. 注意单位转换：
   - 百分比转为0-1的小数（如90% -> 0.90）
   - 波长统一为nm
   - 能量统一为eV
   - 温度统一为K
4. 如果表格中有多行数据，输出JSON数组
5. 如果提供了相关段落，可用于补充环境条件信息

输出严格的JSON格式（数组），不要添加其他说明文字。"""
        
        # 构建用户消息
        user_message = f"表格标题：{table_caption}\n\n表格内容：\n{markdown_table}"
        
        if context_paragraphs:
            user_message += f"\n\n相关段落：\n" + "\n".join(context_paragraphs[:3])
        
        # 调用LLM
        response = self._call_llm(system_prompt, user_message)
        if not response:
            return []
        
        # 解析响应
        data = self._parse_json_response(response)
        if data:
            logger.info(f"✅ 抽取光物性数据 {len(data)} 条")
            return data
        
        return []
    
    def extract_device_data(self, table_caption: str, markdown_table: str,
                           context_paragraphs: Optional[List[str]] = None) -> List[Dict]:
        """
        抽取器件性能数据
        
        Args:
            table_caption: 表格标题
            markdown_table: Markdown格式的表格
            context_paragraphs: 相关段落列表
            
        Returns:
            器件数据列表
        """
        system_prompt = """你是一个专业的科学数据抽取专家，专门从TADF相关文献的表格中抽取OLED器件性能数据。

目标JSON Schema:
{
    "paper_local_id": "发光材料在论文中的编号（如1, 2a等）",
    "emitter_name": "发光材料名称",
    "device_structure": "器件结构（如ITO/TAPC/EML/TmPyPB/LiF/Al）",
    "host": "主体材料",
    "doping_wt_percent": "掺杂浓度（wt%）",
    "lambda_EL_nm": "电致发光峰波长（nm）",
    "CIE_x": "CIE色坐标x",
    "CIE_y": "CIE色坐标y",
    "EQE_max_percent": "最大外量子效率（%）",
    "EQE_100_cd_m2": "100 cd/m²时的EQE（%）",
    "EQE_1000_cd_m2": "1000 cd/m²时的EQE（%）",
    "L_max_cd_m2": "最大亮度（cd/m²）",
    "Von_V": "开启电压（V）",
    "current_efficiency": "电流效率（cd/A）",
    "power_efficiency": "功率效率（lm/W）"
}

抽取规则：
1. 严格按照表格内容抽取，不要猜测
2. 缺失字段用null
3. EQE保持百分比数值（如25.3表示25.3%）
4. 亮度单位为cd/m²
5. 如果表格有多行，输出JSON数组

输出严格的JSON格式（数组），不要添加其他说明文字。"""
        
        user_message = f"表格标题：{table_caption}\n\n表格内容：\n{markdown_table}"
        
        if context_paragraphs:
            user_message += f"\n\n相关段落：\n" + "\n".join(context_paragraphs[:3])
        
        response = self._call_llm(system_prompt, user_message)
        if not response:
            return []
        
        data = self._parse_json_response(response)
        if data:
            logger.info(f"✅ 抽取器件数据 {len(data)} 条")
            return data
        
        return []
    
    def extract_computational_data(self, table_caption: str, markdown_table: str) -> List[Dict]:
        """
        抽取计算化学数据
        
        Args:
            table_caption: 表格标题
            markdown_table: Markdown格式的表格
            
        Returns:
            计算数据列表
        """
        system_prompt = """你是一个专业的科学数据抽取专家，专门从TADF相关文献的表格中抽取DFT/TD-DFT计算数据。

目标JSON Schema:
{
    "paper_local_id": "化合物编号",
    "name": "化合物名称",
    "calculation_method": "计算方法（如B3LYP/6-31G(d)）",
    "HOMO_eV": "HOMO能级（eV）",
    "LUMO_eV": "LUMO能级（eV）",
    "S1_eV": "第一单重激发态能量（eV）",
    "T1_eV": "第一三重激发态能量（eV）",
    "Delta_EST_calc_eV": "计算的ΔE_ST（eV）",
    "f_osc": "振子强度",
    "dipole_moment": "偶极矩（Debye）"
}

抽取规则：
1. 严格按照表格内容抽取
2. 缺失字段用null
3. 能量统一为eV
4. 输出JSON数组

输出严格的JSON格式（数组），不要添加其他说明文字。"""
        
        user_message = f"表格标题：{table_caption}\n\n表格内容：\n{markdown_table}"
        
        response = self._call_llm(system_prompt, user_message)
        if not response:
            return []
        
        data = self._parse_json_response(response)
        if data:
            logger.info(f"✅ 抽取计算数据 {len(data)} 条")
            return data
        
        return []
    
    def extract_compound_info_from_caption(self, caption: str, figure_labels: List[str]) -> Dict[str, str]:
        """
        从图注中提取化合物信息
        
        Args:
            caption: 图注文字
            figure_labels: 化合物标签列表（如['1', '2a', '2b']）
            
        Returns:
            标签到名称的映射 {label: name}
        """
        system_prompt = """你是一个专业的科学文献信息抽取专家。从图注中提取化合物标签与名称的对应关系。

输出JSON格式：
{
    "1": "化合物1的名称",
    "2a": "化合物2a的名称",
    ...
}

规则：
1. 只抽取明确提到的对应关系
2. 如果没有名称，值为null
3. 输出严格JSON格式"""
        
        user_message = f"图注：{caption}\n\n化合物标签：{', '.join(figure_labels)}"
        
        response = self._call_llm(system_prompt, user_message)
        if not response:
            return {}
        
        try:
            data = json.loads(response)
            if isinstance(data, dict):
                logger.info(f"✅ 抽取化合物信息 {len(data)} 个")
                return data
        except:
            pass
        
        return {}


class ExtractionDatabase:
    """抽取数据库 - 管理抽取的数据"""
    
    def __init__(self):
        """初始化抽取数据库"""
        self.photophysical_data = []
        self.device_data = []
        self.computational_data = []
    
    def add_photophysical_records(self, paper_id: str, table_id: str, records: List[Dict]):
        """添加光物性记录"""
        for record in records:
            record['paper_id'] = paper_id
            record['table_id'] = table_id
            self.photophysical_data.append(record)
    
    def add_device_records(self, paper_id: str, table_id: str, records: List[Dict]):
        """添加器件记录"""
        for record in records:
            record['paper_id'] = paper_id
            record['table_id'] = table_id
            self.device_data.append(record)
    
    def add_computational_records(self, paper_id: str, table_id: str, records: List[Dict]):
        """添加计算记录"""
        for record in records:
            record['paper_id'] = paper_id
            record['table_id'] = table_id
            self.computational_data.append(record)
    
    def get_photophysical_by_paper(self, paper_id: str) -> List[Dict]:
        """获取指定论文的光物性数据"""
        return [r for r in self.photophysical_data if r['paper_id'] == paper_id]
    
    def get_device_by_paper(self, paper_id: str) -> List[Dict]:
        """获取指定论文的器件数据"""
        return [r for r in self.device_data if r['paper_id'] == paper_id]
    
    def export_to_json(self, output_dir: str):
        """导出所有数据"""
        from pathlib import Path
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        with open(output_path / "photophysical_raw.json", 'w', encoding='utf-8') as f:
            json.dump(self.photophysical_data, f, indent=2, ensure_ascii=False)
        
        with open(output_path / "device_raw.json", 'w', encoding='utf-8') as f:
            json.dump(self.device_data, f, indent=2, ensure_ascii=False)
        
        with open(output_path / "computational_raw.json", 'w', encoding='utf-8') as f:
            json.dump(self.computational_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ 已导出所有抽取数据到 {output_dir}")

