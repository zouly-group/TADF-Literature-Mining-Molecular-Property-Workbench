#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TADF数据抽取系统 - Streamlit Web应用
支持PDF上传、数据抽取、可视化，以及人工辅助的SMILES识别
"""

import streamlit as st
import json
import base64
import io
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import requests
from PIL import Image
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入项目模块
from config import (
    RAW_PDFS_DIR,
    MINERU_OUTPUT_DIR,
    PROCESSED_DIR,
    DECIMER_API_URL,
    DASHSCOPE_API_KEY,
    MINERU_API_TOKEN,
    MINERU_BASE_URL
)
from modules.mineru_processor import MinerUProcessor
from modules.document_parser import DocumentParser
from modules.image_classifier import ImageClassifier
from modules.structure_recognizer import StructureRecognizer
from modules.data_extractor import DataExtractor
from utils.logger import setup_logger

logger = setup_logger(__name__)

# 页面配置
st.set_page_config(
    page_title="TADF数据抽取系统",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化session state
if 'paper_data' not in st.session_state:
    st.session_state.paper_data = None
if 'extracted_data' not in st.session_state:
    st.session_state.extracted_data = {
        'photophysical': [],
        'device': [],
        'structures': []
    }
if 'molecular_figures' not in st.session_state:
    st.session_state.molecular_figures = []


def init_processors():
    """初始化处理器"""
    if 'mineru_processor' not in st.session_state:
        st.session_state.mineru_processor = MinerUProcessor(MINERU_API_TOKEN, MINERU_BASE_URL)
    if 'document_parser' not in st.session_state:
        st.session_state.document_parser = DocumentParser()
    if 'image_classifier' not in st.session_state:
        st.session_state.image_classifier = ImageClassifier()
    if 'structure_recognizer' not in st.session_state:
        st.session_state.structure_recognizer = StructureRecognizer()
    if 'data_extractor' not in st.session_state:
        st.session_state.data_extractor = DataExtractor()


def process_pdf(pdf_file, paper_id: str):
    """处理PDF文件"""
    try:
        # 保存PDF到临时目录
        temp_dir = Path(tempfile.mkdtemp())
        pdf_path = temp_dir / pdf_file.name
        with open(pdf_path, 'wb') as f:
            f.write(pdf_file.getbuffer())
        
        # 使用MinerU处理
        with st.spinner("正在使用MinerU处理PDF..."):
            extracted_dirs = st.session_state.mineru_processor.parse_pdfs(
                [str(pdf_path)], 
                str(MINERU_OUTPUT_DIR)
            )
        
        if not extracted_dirs:
            st.error("PDF处理失败")
            return None
        
        extract_dir = extracted_dirs[0]
        json_path = st.session_state.mineru_processor.get_json_path(extract_dir)
        images_dir = st.session_state.mineru_processor.get_images_dir(extract_dir)
        
        if not json_path:
            st.error("未找到JSON文件")
            return None
        
        # 解析文档
        with st.spinner("正在解析文档结构..."):
            st.session_state.document_parser.parse_mineru_json(
                json_path, paper_id, images_dir
            )
        
        # 获取所有图像
        figures = st.session_state.document_parser.get_figures()
        
        # 分类图像（识别分子结构图）
        with st.spinner("正在分类图像..."):
            image_paths = [f.image_path for f in figures if Path(f.image_path).exists()]
            if image_paths:
                classification_results = st.session_state.image_classifier.classify_batch(image_paths[:10])  # 限制前10张
        
        # 筛选分子结构图
        molecular_figures = []
        for fig in figures:
            if Path(fig.image_path).exists():
                img_path = fig.image_path
                if img_path in classification_results:
                    result = classification_results[img_path]
                    if result.get('is_molecular_structure'):
                        molecular_figures.append({
                            'figure_id': fig.figure_id,
                            'image_path': fig.image_path,
                            'caption': fig.caption,
                            'page': fig.page_index
                        })
        
        # 抽取数据
        with st.spinner("正在抽取数据..."):
            tables = st.session_state.document_parser.get_tables()
            photophysical_tables = st.session_state.document_parser.filter_tables_by_type("photophysical")
            device_tables = st.session_state.document_parser.filter_tables_by_type("device")
            
            photophysical_data = []
            for table in photophysical_tables:
                records = st.session_state.data_extractor.extract_photophysical_data(
                    table.caption,
                    table.markdown_table
                )
                for record in records:
                    record['table_id'] = table.table_id
                    photophysical_data.append(record)
            
            device_data = []
            for table in device_tables:
                records = st.session_state.data_extractor.extract_device_data(
                    table.caption,
                    table.markdown_table
                )
                for record in records:
                    record['table_id'] = table.table_id
                    device_data.append(record)
        
        return {
            'paper_id': paper_id,
            'figures': figures,
            'molecular_figures': molecular_figures,
            'tables': tables,
            'photophysical_data': photophysical_data,
            'device_data': device_data,
            'extract_dir': extract_dir
        }
    
    except Exception as e:
        logger.error(f"处理PDF出错: {e}")
        st.error(f"处理失败: {str(e)}")
        return None


def recognize_smiles_from_image(image_data: bytes) -> Optional[Dict]:
    """使用DECIMER识别SMILES"""
    try:
        # 保存临时图片
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        temp_file.write(image_data)
        temp_file.close()
        
        # 调用DECIMER API
        with open(temp_file.name, 'rb') as f:
            files = {'image': f}
            response = requests.post(
                DECIMER_API_URL,
                files=files,
                timeout=30
            )
        
        # 清理临时文件
        Path(temp_file.name).unlink()
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                return {
                    'smiles': result.get('smiles', ''),
                    'confidence': result.get('global_confidence', 0.0),
                    'method': result.get('method', 'unknown')
                }
        
        return None
    
    except Exception as e:
        logger.error(f"识别SMILES出错: {e}")
        return None


def display_molecular_figures(figures: List[Dict]):
    """显示分子结构图片"""
    if not figures:
        st.info("未找到分子结构图片")
        return
    
    st.subheader("📸 论文中的分子结构图片（可截图使用）")
    
    # 按页面分组显示
    pages = {}
    for fig in figures:
        page = fig.get('page', 0)
        if page not in pages:
            pages[page] = []
        pages[page].append(fig)
    
    for page_num in sorted(pages.keys()):
        with st.expander(f"第 {page_num} 页", expanded=True):
            cols = st.columns(min(3, len(pages[page_num])))
            for idx, fig in enumerate(pages[page_num]):
                col = cols[idx % len(cols)]
                with col:
                    try:
                        img_path = fig['image_path']
                        if Path(img_path).exists():
                            img = Image.open(img_path)
                            st.image(img, caption=f"图 {fig['figure_id']}", use_container_width=True)
                            if fig.get('caption'):
                                st.caption(fig['caption'][:100] + "..." if len(fig['caption']) > 100 else fig['caption'])
                    except Exception as e:
                        st.error(f"加载图片失败: {e}")


def main():
    """主函数"""
    st.title("🔬 TADF数据抽取系统")
    st.markdown("---")
    
    # 初始化处理器
    init_processors()
    
    # 侧边栏
    with st.sidebar:
        st.header("📋 功能导航")
        page = st.radio(
            "选择功能",
            ["PDF上传与处理", "数据查看与编辑", "SMILES识别助手"]
        )
        st.markdown("---")
        st.info("💡 提示：\n- 上传PDF后会自动抽取数据\n- 可在数据查看页面编辑SMILES\n- 使用识别助手辅助填写SMILES")
    
    # 主页面
    if page == "PDF上传与处理":
        st.header("📄 PDF上传与处理")
        
        uploaded_file = st.file_uploader(
            "上传PDF文件",
            type=['pdf'],
            help="上传TADF相关论文PDF文件"
        )
        
        if uploaded_file:
            paper_id = st.text_input(
                "论文ID",
                value=uploaded_file.name.replace('.pdf', ''),
                help="输入论文的唯一标识符"
            )
            
            if st.button("🚀 开始处理", type="primary"):
                with st.spinner("正在处理PDF，请稍候..."):
                    result = process_pdf(uploaded_file, paper_id)
                    
                    if result:
                        st.session_state.paper_data = result
                        st.session_state.extracted_data['photophysical'] = result['photophysical_data']
                        st.session_state.extracted_data['device'] = result['device_data']
                        st.session_state.molecular_figures = result['molecular_figures']
                        
                        st.success("✅ PDF处理完成！")
                        st.balloons()
                        
                        # 显示统计信息
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("分子结构图", len(result['molecular_figures']))
                        with col2:
                            st.metric("光物性数据", len(result['photophysical_data']))
                        with col3:
                            st.metric("器件数据", len(result['device_data']))
                        with col4:
                            st.metric("表格总数", len(result['tables']))
                        
                        # 显示分子结构图
                        display_molecular_figures(result['molecular_figures'])
    
    elif page == "数据查看与编辑":
        st.header("📊 数据查看与编辑")
        
        if st.session_state.paper_data is None:
            st.warning("⚠️ 请先上传并处理PDF文件")
            return
        
        # 选择数据类型
        data_type = st.radio(
            "选择数据类型",
            ["光物性数据", "器件数据"],
            horizontal=True
        )
        
        if data_type == "光物性数据":
            data = st.session_state.extracted_data['photophysical']
            if not data:
                st.info("暂无光物性数据")
                return
            
            # 转换为DataFrame
            df = pd.DataFrame(data)
            
            # 编辑模式
            st.subheader("编辑数据")
            
            # 构建列配置
            column_config = {}
            if "paper_local_id" in df.columns:
                column_config["paper_local_id"] = st.column_config.TextColumn("化合物编号", width="small")
            if "smiles" in df.columns:
                column_config["smiles"] = st.column_config.TextColumn("SMILES编码", width="large")
            if "lambda_PL_nm" in df.columns:
                column_config["lambda_PL_nm"] = st.column_config.NumberColumn("PL波长(nm)", width="small")
            if "FWHM_nm" in df.columns:
                column_config["FWHM_nm"] = st.column_config.NumberColumn("半峰宽(nm)", width="small")
            if "Phi_PL" in df.columns:
                column_config["Phi_PL"] = st.column_config.NumberColumn("PL量子产率", width="small", format="%.3f")
            if "Delta_EST_eV" in df.columns:
                column_config["Delta_EST_eV"] = st.column_config.NumberColumn("ΔE_ST(eV)", width="small", format="%.3f")
            
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                num_rows="dynamic",
                column_config=column_config,
                hide_index=True
            )
            
            if st.button("💾 保存修改", key="save_photophysical"):
                st.session_state.extracted_data['photophysical'] = edited_df.to_dict('records')
                st.success("✅ 数据已保存")
        
        else:  # 器件数据
            data = st.session_state.extracted_data['device']
            if not data:
                st.info("暂无器件数据")
                return
            
            df = pd.DataFrame(data)
            
            # 构建列配置
            column_config = {}
            if "paper_local_id" in df.columns:
                column_config["paper_local_id"] = st.column_config.TextColumn("化合物编号", width="small")
            if "emitter_name" in df.columns:
                column_config["emitter_name"] = st.column_config.TextColumn("发光材料", width="medium")
            if "EQE_max_percent" in df.columns:
                column_config["EQE_max_percent"] = st.column_config.NumberColumn("最大EQE(%)", width="small", format="%.2f")
            if "lambda_EL_nm" in df.columns:
                column_config["lambda_EL_nm"] = st.column_config.NumberColumn("EL波长(nm)", width="small")
            
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                num_rows="dynamic",
                column_config=column_config,
                hide_index=True
            )
            
            if st.button("💾 保存修改", key="save_device"):
                st.session_state.extracted_data['device'] = edited_df.to_dict('records')
                st.success("✅ 数据已保存")
        
        # 导出功能
        st.markdown("---")
        if st.button("📥 导出JSON"):
            output = {
                'paper_id': st.session_state.paper_data['paper_id'],
                'photophysical': st.session_state.extracted_data['photophysical'],
                'device': st.session_state.extracted_data['device']
            }
            json_str = json.dumps(output, indent=2, ensure_ascii=False)
            st.download_button(
                "下载JSON文件",
                json_str,
                file_name=f"{st.session_state.paper_data['paper_id']}_extracted_data.json",
                mime="application/json"
            )
    
    elif page == "SMILES识别助手":
        st.header("🔍 SMILES识别助手")
        st.markdown("支持通过粘贴或上传图片识别分子结构SMILES编码")
        
        # 显示论文中的分子结构图
        if st.session_state.molecular_figures:
            st.subheader("📸 论文中的分子结构图（可截图使用）")
            display_molecular_figures(st.session_state.molecular_figures)
            st.markdown("---")
        
        # 图片输入方式选择
        input_method = st.radio(
            "选择输入方式",
            ["上传图片", "粘贴图片"],
            horizontal=True
        )
        
        if input_method == "上传图片":
            uploaded_image = st.file_uploader(
                "上传分子结构图片",
                type=['png', 'jpg', 'jpeg'],
                help="上传包含分子结构式的图片"
            )
            
            if uploaded_image:
                image_data = uploaded_image.read()
                img = Image.open(io.BytesIO(image_data))
                st.image(img, caption="上传的图片", use_container_width=True)
                
                if st.button("🔍 识别SMILES", type="primary"):
                    with st.spinner("正在识别..."):
                        result = recognize_smiles_from_image(image_data)
                        
                        if result:
                            st.success("✅ 识别成功！")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.text_area(
                                    "SMILES编码",
                                    value=result['smiles'],
                                    height=100,
                                    key="recognized_smiles"
                                )
                            with col2:
                                st.metric("置信度", f"{result['confidence']:.3f}" if result.get('confidence') else "N/A")
                                st.caption(f"识别方法: {result.get('method', 'unknown')}")
                            
                            # 复制按钮
                            st.code(result['smiles'], language=None)
                            
                            # 填充到数据
                            if st.session_state.extracted_data['photophysical']:
                                st.subheader("填充到数据")
                                compound_options = [r.get('paper_local_id', '未知') for r in st.session_state.extracted_data['photophysical']]
                                compound_id = st.selectbox(
                                    "选择要填充的化合物",
                                    options=compound_options,
                                    key="select_compound_upload"
                                )
                                if st.button("📝 填充SMILES", key="fill_upload"):
                                    for record in st.session_state.extracted_data['photophysical']:
                                        if record.get('paper_local_id') == compound_id:
                                            record['smiles'] = result['smiles']
                                            st.success(f"✅ 已填充到化合物 {compound_id}")
                                            st.rerun()
                                            break
                        else:
                            st.error("❌ 识别失败，请重试")
        
        else:  # 粘贴图片
            st.info("💡 提示：使用截图工具截图后，通过文件上传方式上传图片")
            st.markdown("**或者** 使用以下方式粘贴图片：")
            
            # 使用文件上传作为替代方案（更可靠）
            pasted_file = st.file_uploader(
                "粘贴或上传图片",
                type=['png', 'jpg', 'jpeg'],
                help="截图后保存为图片文件上传，或直接拖拽图片文件",
                key="paste_upload"
            )
            
            if pasted_file:
                image_data = pasted_file.read()
                img = Image.open(io.BytesIO(image_data))
                st.image(img, caption="粘贴的图片", use_container_width=True)
                
                if st.button("🔍 识别SMILES", type="primary", key="recognize_paste"):
                    with st.spinner("正在识别..."):
                        result = recognize_smiles_from_image(image_data)
                        
                        if result:
                            st.success("✅ 识别成功！")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.text_area(
                                    "SMILES编码",
                                    value=result['smiles'],
                                    height=100,
                                    key="recognized_smiles_paste"
                                )
                            with col2:
                                st.metric("置信度", f"{result['confidence']:.3f}" if result.get('confidence') else "N/A")
                                st.caption(f"识别方法: {result.get('method', 'unknown')}")
                            
                            st.code(result['smiles'], language=None)
                            
                            # 填充到数据
                            if st.session_state.extracted_data['photophysical']:
                                st.subheader("填充到数据")
                                compound_options = [r.get('paper_local_id', '未知') for r in st.session_state.extracted_data['photophysical']]
                                compound_id = st.selectbox(
                                    "选择要填充的化合物",
                                    options=compound_options,
                                    key="select_compound_paste"
                                )
                                if st.button("📝 填充SMILES", key="fill_paste"):
                                    for record in st.session_state.extracted_data['photophysical']:
                                        if record.get('paper_local_id') == compound_id:
                                            record['smiles'] = result['smiles']
                                            st.success(f"✅ 已填充到化合物 {compound_id}")
                                            st.rerun()
                                            break
                        else:
                            st.error("❌ 识别失败，请重试")


if __name__ == "__main__":
    main()

