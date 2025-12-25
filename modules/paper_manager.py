#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文献管理模块
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from utils.logger import setup_logger
from config import DATABASE_DIR, PAPERS_SCHEMA

logger = setup_logger(__name__)


class PaperManager:
    """文献管理器"""
    
    def __init__(self, db_path: Path = DATABASE_DIR / "papers.db"):
        """
        初始化文献管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建papers表
        fields = ", ".join([f"{k} {v}" for k, v in PAPERS_SCHEMA.items()])
        cursor.execute(f"CREATE TABLE IF NOT EXISTS papers ({fields})")
        
        conn.commit()
        conn.close()
        logger.info(f"数据库已初始化: {self.db_path}")
    
    def add_paper(self, paper_data: Dict) -> str:
        """
        添加论文记录
        
        Args:
            paper_data: 论文数据字典
            
        Returns:
            paper_id
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 生成paper_id
        if "paper_id" not in paper_data:
            # 使用DOI或时间戳生成ID
            if "doi" in paper_data and paper_data["doi"]:
                paper_id = paper_data["doi"].replace("/", "_").replace(".", "_")
            else:
                paper_id = f"paper_{int(datetime.now().timestamp())}"
            paper_data["paper_id"] = paper_id
        
        # 插入数据
        fields = list(paper_data.keys())
        placeholders = ", ".join(["?" for _ in fields])
        field_names = ", ".join(fields)
        values = [paper_data[f] for f in fields]
        
        try:
            cursor.execute(
                f"INSERT OR REPLACE INTO papers ({field_names}) VALUES ({placeholders})",
                values
            )
            conn.commit()
            logger.info(f"✅ 添加论文: {paper_data['paper_id']}")
        except Exception as e:
            logger.error(f"添加论文失败: {e}")
            conn.rollback()
        finally:
            conn.close()
        
        return paper_data["paper_id"]
    
    def get_paper(self, paper_id: str) -> Optional[Dict]:
        """
        获取论文记录
        
        Args:
            paper_id: 论文ID
            
        Returns:
            论文数据字典
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def list_papers(self) -> List[Dict]:
        """
        列出所有论文
        
        Returns:
            论文数据列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM papers ORDER BY year DESC, paper_id")
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_paper(self, paper_id: str, updates: Dict):
        """
        更新论文记录
        
        Args:
            paper_id: 论文ID
            updates: 更新字段字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [paper_id]
        
        try:
            cursor.execute(
                f"UPDATE papers SET {set_clause} WHERE paper_id = ?",
                values
            )
            conn.commit()
            logger.info(f"✅ 更新论文: {paper_id}")
        except Exception as e:
            logger.error(f"更新论文失败: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def delete_paper(self, paper_id: str):
        """
        删除论文记录
        
        Args:
            paper_id: 论文ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM papers WHERE paper_id = ?", (paper_id,))
            conn.commit()
            logger.info(f"✅ 删除论文: {paper_id}")
        except Exception as e:
            logger.error(f"删除论文失败: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def export_to_json(self, output_path: str):
        """
        导出论文数据到JSON
        
        Args:
            output_path: 输出文件路径
        """
        papers = self.list_papers()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(papers, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ 导出 {len(papers)} 篇论文到 {output_path}")

