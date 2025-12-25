#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图像分类模块 - 使用Qwen-VL进行图像分类
"""

import json
import time
import base64
import requests
from pathlib import Path
from typing import Dict, Optional
from utils.logger import setup_logger
from config import (
    DASHSCOPE_API_KEY,
    QWEN_CHAT_ENDPOINT,
    TEMPERATURE,
    MAX_RETRY,
    SLEEP_BETWEEN,
    TIMEOUT_SEC,
    FIGURE_TYPES
)

logger = setup_logger(__name__)


class ImageClassifier:
    """图像分类器 - 使用Qwen-VL"""
    
    def __init__(self, api_key: str = DASHSCOPE_API_KEY):
        """
        初始化图像分类器
        
        Args:
            api_key: API密钥
        """
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return f"""你是一个专业的科学文献图像分类专家。你的任务是对TADF（热活化延迟荧光）相关科学论文中的图像进行分类。

图像类别定义：
1. molecular_structure: 二维分子结构图，显示化合物的化学结构式
2. energy_level_diagram: 能级图或Jablonski图，显示S₀, S₁, T₁, HOMO/LUMO, ΔE_ST等能级信息
3. device_structure: OLED器件堆栈结构图，显示ITO/TAPC/EML等多层矩形结构
4. photophysical_scheme: 光物理机理流程示意图，显示RISC、TADF等过程的箭头示意
5. spectrum_or_curve: 光谱或曲线图，如PL光谱、EL光谱、吸收光谱、衰减曲线等
6. table_or_flowchart: 表格截图或流程图、框架图
7. other: 其他内容，如照片、logo等

判断规则：
- 只要主要内容是分子结构式，就归类为molecular_structure
- 如果同时包含多种内容，选择占主导地位的内容类型
- 必须从上述7个类别中选择一个

输出格式（严格JSON）：
{{
    "figure_type": "类别名称",
    "is_molecular_structure": true/false,
    "reason": "简短的判断理由（中英文均可）"
}}"""
    
    def _encode_image(self, image_path: str) -> Optional[str]:
        """
        将图片编码为base64
        
        Args:
            image_path: 图片路径
            
        Returns:
            base64编码的图片数据
        """
        try:
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"图片编码失败 {image_path}: {e}")
            return None
    
    def classify_image(self, image_path: str) -> Optional[Dict]:
        """
        分类单张图片
        
        Args:
            image_path: 图片路径
            
        Returns:
            分类结果字典
        """
        if not Path(image_path).exists():
            logger.error(f"图片不存在: {image_path}")
            return None
        
        # 对于Qwen-VL，我们使用multimodal API
        # 注意：实际使用时需要根据具体的API格式调整
        image_base64 = self._encode_image(image_path)
        if not image_base64:
            return None
        
        user_message = "请对这张图片进行分类，并按照指定的JSON格式输出结果。"
        
        for attempt in range(MAX_RETRY):
            try:
                # 构建请求数据 - 适配Qwen多模态格式
                payload = {
                    "model": "qwen-vl-plus",  # 或 qwen-vl-max
                    "messages": [
                        {
                            "role": "system",
                            "content": self.system_prompt
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_base64}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": user_message
                                }
                            ]
                        }
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
                    
                    # 提取回复内容
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    # 解析JSON
                    classification = self._parse_response(content)
                    if classification:
                        logger.info(f"✅ 图片分类成功: {Path(image_path).name} -> {classification['figure_type']}")
                        return classification
                    else:
                        logger.warning(f"无法解析分类结果: {content}")
                else:
                    logger.warning(f"API请求失败 ({response.status_code}): {response.text}")
                
            except Exception as e:
                logger.error(f"分类图片出错 (尝试 {attempt+1}/{MAX_RETRY}): {e}")
            
            if attempt < MAX_RETRY - 1:
                time.sleep(SLEEP_BETWEEN)
        
        logger.error(f"图片分类失败: {image_path}")
        return None
    
    def _parse_response(self, content: str) -> Optional[Dict]:
        """
        解析LLM响应内容
        
        Args:
            content: 响应内容
            
        Returns:
            解析后的分类结果
        """
        try:
            # 尝试直接解析JSON
            result = json.loads(content)
            
            # 验证必需字段
            if "figure_type" in result and "is_molecular_structure" in result:
                # 确保figure_type在有效列表中
                if result["figure_type"] not in FIGURE_TYPES:
                    logger.warning(f"无效的figure_type: {result['figure_type']}")
                    return None
                return result
        except json.JSONDecodeError:
            # 尝试提取JSON代码块
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                    if "figure_type" in result and "is_molecular_structure" in result:
                        return result
                except:
                    pass
        
        return None
    
    def classify_batch(self, image_paths: list) -> Dict[str, Dict]:
        """
        批量分类图片
        
        Args:
            image_paths: 图片路径列表
            
        Returns:
            分类结果字典 {image_path: classification_result}
        """
        results = {}
        total = len(image_paths)
        
        logger.info(f"开始批量分类 {total} 张图片")
        
        for i, image_path in enumerate(image_paths, 1):
            logger.info(f"处理进度: {i}/{total}")
            result = self.classify_image(image_path)
            if result:
                results[image_path] = result
            
            # 避免请求过快
            if i < total:
                time.sleep(0.5)
        
        logger.info(f"✅ 批量分类完成: {len(results)}/{total} 成功")
        return results
    
    def save_results(self, results: Dict[str, Dict], output_path: str):
        """
        保存分类结果
        
        Args:
            results: 分类结果字典
            output_path: 输出文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ 分类结果已保存到 {output_path}")

