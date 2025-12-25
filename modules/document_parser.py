#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档结构解析与分块模块
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class Table:
    """表格数据类"""
    table_id: str
    paper_id: str
    caption: str
    markdown_table: str
    section: str
    page_index: int
    html_table: Optional[str] = None
    raw_data: Optional[Dict] = None


@dataclass
class Figure:
    """图像数据类"""
    figure_id: str
    paper_id: str
    image_path: str
    caption: str
    section: str
    page_index: int
    raw_data: Optional[Dict] = None


@dataclass
class Paragraph:
    """段落数据类"""
    para_id: str
    paper_id: str
    text: str
    section: str
    page_index: int
    raw_data: Optional[Dict] = None


class DocumentParser:
    """文档解析器"""
    
    def __init__(self):
        """初始化文档解析器"""
        self.tables: List[Table] = []
        self.figures: List[Figure] = []
        self.paragraphs: List[Paragraph] = []
    
    def parse_mineru_json(self, json_path: str, paper_id: str, images_dir: Optional[str] = None) -> Dict:
        """
        解析MinerU输出的JSON文件
        
        Args:
            json_path: JSON文件路径（优先使用content_list.json）
            paper_id: 论文ID
            images_dir: 图片目录路径
            
        Returns:
            解析统计信息
        """
        logger.info(f"开始解析 {json_path}")
        
        # 清空之前的数据
        self.tables.clear()
        self.figures.clear()
        self.paragraphs.clear()
        
        # 1. 优先尝试使用content_list.json（MinerU v2格式）
        json_dir = Path(json_path).parent
        content_list_files = list(json_dir.glob("*_content_list.json"))
        
        if content_list_files:
            # 使用content_list.json格式
            logger.info(f"使用content_list.json格式: {content_list_files[0]}")
            stats = self._parse_content_list(str(content_list_files[0]), paper_id, images_dir)
        else:
            # 使用layout.json格式（兼容旧版本）
            logger.info("使用layout.json格式")
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                logger.error(f"读取JSON失败: {e}")
                return {}
            
            # 解析不同类型的内容
            table_count = self._parse_tables(data, paper_id)
            figure_count = self._parse_figures(data, paper_id, images_dir)
            para_count = self._parse_paragraphs(data, paper_id)
            
            stats = {
                "paper_id": paper_id,
                "tables": table_count,
                "figures": figure_count,
                "paragraphs": para_count
            }
        
        logger.info(f"✅ 解析完成: {stats}")
        return stats
    
    def _parse_content_list(self, content_list_path: str, paper_id: str, images_dir: Optional[str]) -> Dict:
        """
        解析MinerU的content_list.json格式
        
        Args:
            content_list_path: content_list.json文件路径
            paper_id: 论文ID
            images_dir: 图片目录路径
            
        Returns:
            解析统计信息
        """
        try:
            with open(content_list_path, 'r', encoding='utf-8') as f:
                content_list = json.load(f)
        except Exception as e:
            logger.error(f"读取content_list.json失败: {e}")
            return {}
        
        if not isinstance(content_list, list):
            logger.error("content_list格式错误，应为数组")
            return {}
        
        table_count = 0
        figure_count = 0
        para_count = 0
        
        # 获取图片基础目录
        base_dir = Path(content_list_path).parent
        if images_dir:
            images_base = Path(images_dir)
        else:
            images_base = base_dir / "images"
        
        # 遍历所有内容项
        for idx, item in enumerate(content_list):
            item_type = item.get("type", "")
            page_idx = item.get("page_idx", 0)
            
            # 解析表格
            if item_type == "table":
                table_id = f"{paper_id}_table_{table_count + 1}"
                
                # 提取表格内容 - 优先使用table_body
                table_html = item.get("table_body", "") or item.get("table_html", "")
                
                # 提取表格标题
                table_caption = item.get("table_caption", "")
                if isinstance(table_caption, list) and table_caption:
                    table_caption = " ".join(table_caption)
                
                # 提取表格脚注
                table_footnote = item.get("table_footnote", "")
                if isinstance(table_footnote, list) and table_footnote:
                    table_footnote = " ".join(table_footnote)
                
                # 合并标题和脚注到caption
                full_caption = str(table_caption)
                if table_footnote:
                    full_caption += f"\n\nFootnote: {table_footnote}"
                
                # 尝试从HTML转换为Markdown
                markdown_table = self._html_to_markdown(table_html)
                
                table = Table(
                    table_id=table_id,
                    paper_id=paper_id,
                    caption=full_caption,
                    markdown_table=markdown_table,
                    section="Unknown",
                    page_index=page_idx + 1,
                    html_table=table_html,
                    raw_data=item
                )
                
                self.tables.append(table)
                table_count += 1
            
            # 解析图像
            elif item_type == "image":
                figure_id = f"{paper_id}_fig_{figure_count + 1}"
                
                # 提取图像信息
                img_path = item.get("img_path", "")
                image_caption = item.get("image_caption", [])
                if isinstance(image_caption, list):
                    caption = " ".join(image_caption)
                else:
                    caption = str(image_caption)
                
                # 构建完整图片路径
                if img_path:
                    full_image_path = str(base_dir / img_path)
                else:
                    full_image_path = ""
                
                figure = Figure(
                    figure_id=figure_id,
                    paper_id=paper_id,
                    image_path=full_image_path,
                    caption=caption,
                    section="Unknown",
                    page_index=page_idx + 1,
                    raw_data=item
                )
                
                self.figures.append(figure)
                figure_count += 1
            
            # 解析文本段落
            elif item_type == "text":
                text = item.get("text", "").strip()
                
                # 过滤太短的段落和标题
                if len(text) < 20:
                    continue
                
                para_id = f"{paper_id}_para_{para_count + 1}"
                
                # 尝试从text_level判断是否为标题
                text_level = item.get("text_level", 0)
                if text_level > 0:
                    section = text  # 这是一个标题
                else:
                    section = "Unknown"
                
                paragraph = Paragraph(
                    para_id=para_id,
                    paper_id=paper_id,
                    text=text,
                    section=section,
                    page_index=page_idx + 1,
                    raw_data=item
                )
                
                self.paragraphs.append(paragraph)
                para_count += 1
        
        logger.info(f"解析到 {table_count} 个表格")
        logger.info(f"解析到 {figure_count} 个图像")
        logger.info(f"解析到 {para_count} 个段落")
        
        return {
            "paper_id": paper_id,
            "tables": table_count,
            "figures": figure_count,
            "paragraphs": para_count
        }
    
    def _html_to_markdown(self, html: str) -> str:
        """
        HTML表格转Markdown
        
        Args:
            html: HTML表格字符串
            
        Returns:
            Markdown格式的表格
        """
        if not html:
            return ""
        
        try:
            import re
            
            # 解析HTML表格
            rows = []
            
            # 提取所有<tr>标签
            tr_pattern = r'<tr>(.*?)</tr>'
            trs = re.findall(tr_pattern, html, re.DOTALL)
            
            for tr in trs:
                # 提取<td>或<th>标签
                cell_pattern = r'<t[dh]>(.*?)</t[dh]>'
                cells = re.findall(cell_pattern, tr, re.DOTALL)
                
                # 清理单元格内容
                cleaned_cells = []
                for cell in cells:
                    # 移除HTML标签
                    cell = re.sub(r'<[^>]+>', '', cell)
                    # 清理空格
                    cell = cell.strip().replace('\n', ' ')
                    cleaned_cells.append(cell)
                
                if cleaned_cells:
                    rows.append(cleaned_cells)
            
            if not rows:
                return ""
            
            # 构建Markdown表格
            markdown_lines = []
            
            # 表头
            if rows:
                header = rows[0]
                markdown_lines.append('| ' + ' | '.join(header) + ' |')
                # 分隔线
                markdown_lines.append('|' + '|'.join(['---'] * len(header)) + '|')
                
                # 表体
                for row in rows[1:]:
                    # 补齐列数
                    while len(row) < len(header):
                        row.append('')
                    markdown_lines.append('| ' + ' | '.join(row[:len(header)]) + ' |')
            
            return '\n'.join(markdown_lines)
            
        except Exception as e:
            logger.warning(f"HTML转Markdown失败: {e}")
            # 降级：移除所有HTML标签
            import re
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
    
    def _parse_tables(self, data: Dict, paper_id: str) -> int:
        """
        解析表格
        
        Args:
            data: MinerU JSON数据
            paper_id: 论文ID
            
        Returns:
            解析的表格数量
        """
        count = 0
        
        # MinerU v2格式通常有一个页面列表
        pages = data.get("pages", [])
        
        for page_idx, page in enumerate(pages):
            page_content = page.get("content", [])
            
            for item in page_content:
                if item.get("type") == "table":
                    table_id = f"{paper_id}_table_{count+1}"
                    
                    # 提取表格信息
                    caption = item.get("caption", "")
                    markdown_table = item.get("markdown", "")
                    html_table = item.get("html", "")
                    section = self._extract_section(page_content, item)
                    
                    table = Table(
                        table_id=table_id,
                        paper_id=paper_id,
                        caption=caption,
                        markdown_table=markdown_table,
                        section=section,
                        page_index=page_idx + 1,
                        html_table=html_table,
                        raw_data=item
                    )
                    
                    self.tables.append(table)
                    count += 1
        
        logger.info(f"解析到 {count} 个表格")
        return count
    
    def _parse_figures(self, data: Dict, paper_id: str, images_dir: Optional[str]) -> int:
        """
        解析图像
        
        Args:
            data: MinerU JSON数据
            paper_id: 论文ID
            images_dir: 图片目录路径
            
        Returns:
            解析的图像数量
        """
        count = 0
        images_path = Path(images_dir) if images_dir else None
        
        pages = data.get("pages", [])
        
        for page_idx, page in enumerate(pages):
            page_content = page.get("content", [])
            
            for item in page_content:
                if item.get("type") == "image":
                    figure_id = f"{paper_id}_fig_{count+1}"
                    
                    # 提取图像信息
                    caption = item.get("caption", "")
                    image_filename = item.get("image_path", "") or item.get("path", "")
                    
                    # 构建完整图片路径
                    if images_path and image_filename:
                        image_path = str(images_path / image_filename)
                    else:
                        image_path = image_filename
                    
                    section = self._extract_section(page_content, item)
                    
                    figure = Figure(
                        figure_id=figure_id,
                        paper_id=paper_id,
                        image_path=image_path,
                        caption=caption,
                        section=section,
                        page_index=page_idx + 1,
                        raw_data=item
                    )
                    
                    self.figures.append(figure)
                    count += 1
        
        logger.info(f"解析到 {count} 个图像")
        return count
    
    def _parse_paragraphs(self, data: Dict, paper_id: str) -> int:
        """
        解析段落
        
        Args:
            data: MinerU JSON数据
            paper_id: 论文ID
            
        Returns:
            解析的段落数量
        """
        count = 0
        
        pages = data.get("pages", [])
        
        for page_idx, page in enumerate(pages):
            page_content = page.get("content", [])
            
            for item in page_content:
                if item.get("type") in ["text", "paragraph"]:
                    text = item.get("text", "").strip()
                    
                    # 过滤太短的段落
                    if len(text) < 20:
                        continue
                    
                    para_id = f"{paper_id}_para_{count+1}"
                    section = self._extract_section(page_content, item)
                    
                    paragraph = Paragraph(
                        para_id=para_id,
                        paper_id=paper_id,
                        text=text,
                        section=section,
                        page_index=page_idx + 1,
                        raw_data=item
                    )
                    
                    self.paragraphs.append(paragraph)
                    count += 1
        
        logger.info(f"解析到 {count} 个段落")
        return count
    
    def _extract_section(self, page_content: List[Dict], current_item: Dict) -> str:
        """
        提取当前项目所属的节标题
        
        Args:
            page_content: 页面内容列表
            current_item: 当前项目
            
        Returns:
            节标题
        """
        # 简单策略：向前查找最近的标题
        current_idx = -1
        for i, item in enumerate(page_content):
            if item == current_item:
                current_idx = i
                break
        
        if current_idx == -1:
            return "Unknown"
        
        # 向前查找标题
        for i in range(current_idx - 1, -1, -1):
            item = page_content[i]
            if item.get("type") in ["heading", "title"]:
                return item.get("text", "Unknown")
        
        return "Unknown"
    
    def get_tables(self) -> List[Table]:
        """获取所有表格"""
        return self.tables
    
    def get_figures(self) -> List[Figure]:
        """获取所有图像"""
        return self.figures
    
    def get_paragraphs(self) -> List[Paragraph]:
        """获取所有段落"""
        return self.paragraphs
    
    def export_to_json(self, output_dir: str, paper_id: str):
        """
        导出解析结果到JSON文件
        
        Args:
            output_dir: 输出目录
            paper_id: 论文ID
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 导出表格
        tables_file = output_path / f"{paper_id}_tables.json"
        with open(tables_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(t) for t in self.tables], f, indent=2, ensure_ascii=False)
        
        # 导出图像
        figures_file = output_path / f"{paper_id}_figures.json"
        with open(figures_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(f) for f in self.figures], f, indent=2, ensure_ascii=False)
        
        # 导出段落
        paragraphs_file = output_path / f"{paper_id}_paragraphs.json"
        with open(paragraphs_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(p) for p in self.paragraphs], f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ 已导出解析结果到 {output_path}")
    
    def filter_tables_by_type(self, table_type: str) -> List[Table]:
        """
        根据类型过滤表格
        
        Args:
            table_type: 表格类型 (photophysical, device, computational, other)
            
        Returns:
            过滤后的表格列表
        """
        keywords_map = {
            "photophysical": ["photophysical", "optical", "luminescence", "PL", "emission", "FWHM", "PLQY"],
            "device": ["device", "OLED", "EQE", "EL", "current efficiency", "brightness"],
            "computational": ["calculated", "DFT", "TD-DFT", "computation", "HOMO", "LUMO"]
        }
        
        keywords = keywords_map.get(table_type.lower(), [])
        if not keywords:
            return []
        
        filtered = []
        for table in self.tables:
            caption_lower = table.caption.lower()
            if any(kw.lower() in caption_lower for kw in keywords):
                filtered.append(table)
        
        logger.info(f"找到 {len(filtered)} 个 {table_type} 类型的表格")
        return filtered

