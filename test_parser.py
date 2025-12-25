#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试文档解析器
"""

from modules.document_parser import DocumentParser
from pathlib import Path

def main():
    print("=" * 60)
    print("测试MinerU输出解析")
    print("=" * 60)
    
    parser = DocumentParser()
    
    # 解析
    json_path = 'data/mineru_output/paper/layout.json'
    images_dir = 'data/mineru_output/paper/images'
    
    stats = parser.parse_mineru_json(json_path, 'paper_001', images_dir)
    
    print(f"\n✅ 解析统计:")
    print(f"   表格: {stats['tables']}")
    print(f"   图片: {stats['figures']}")
    print(f"   段落: {stats['paragraphs']}")
    
    # 显示表格信息
    if parser.get_tables():
        print(f"\n📊 表格详情:")
        for i, table in enumerate(parser.get_tables(), 1):
            print(f"\n  表格 {i}:")
            print(f"    ID: {table.table_id}")
            print(f"    页码: {table.page_index}")
            print(f"    标题: {table.caption[:80]}...")
            print(f"    Markdown (前150字符):")
            print(f"    {table.markdown_table[:150]}...")
    
    # 显示图片信息
    if parser.get_figures():
        print(f"\n🖼️  图片详情:")
        for i, fig in enumerate(parser.get_figures(), 1):
            print(f"\n  图片 {i}:")
            print(f"    ID: {fig.figure_id}")
            print(f"    页码: {fig.page_index}")
            print(f"    路径: {Path(fig.image_path).name}")
            print(f"    标题: {fig.caption[:80]}...")
    
    # 显示部分段落
    if parser.get_paragraphs():
        print(f"\n📝 段落示例 (前3个):")
        for i, para in enumerate(parser.get_paragraphs()[:3], 1):
            print(f"\n  段落 {i}:")
            print(f"    ID: {para.para_id}")
            print(f"    页码: {para.page_index}")
            print(f"    内容 (前100字符): {para.text[:100]}...")
    
    print(f"\n" + "=" * 60)
    print("✅ 测试完成！文档解析器工作正常")
    print("=" * 60)

if __name__ == "__main__":
    main()

