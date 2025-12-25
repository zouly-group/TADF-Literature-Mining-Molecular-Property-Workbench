#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU PDF预处理模块
"""

import os
import time
import json
import zipfile
import requests
from pathlib import Path
from typing import List, Dict, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


class MinerUProcessor:
    """MinerU PDF处理器"""
    
    def __init__(self, token: str, base_url: str):
        """
        初始化MinerU处理器
        
        Args:
            token: API token
            base_url: API基础URL
        """
        self.token = token
        self.base_url = base_url
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
    
    def upload_file_with_retry(self, file_path: str, upload_url: str, max_retries: int = 3) -> bool:
        """
        带重试的文件上传
        
        Args:
            file_path: PDF文件路径
            upload_url: 上传URL
            max_retries: 最大重试次数
            
        Returns:
            是否上传成功
        """
        filename = Path(file_path).name
        for attempt in range(max_retries):
            try:
                with open(file_path, 'rb') as f:
                    response = requests.put(upload_url, data=f, timeout=(30, 300))
                if response.status_code == 200:
                    logger.info(f"✅ {filename} 上传成功")
                    return True
                else:
                    logger.warning(f"❌ {filename} 上传失败: {response.status_code}")
            except Exception as e:
                logger.error(f"上传错误 {filename}: {e}")
            
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 10
                logger.info(f"等待 {wait}s 后重试...")
                time.sleep(wait)
        
        return False
    
    def request_upload_urls(self, pdf_files: List[str]) -> Optional[Dict]:
        """
        申请上传链接
        
        Args:
            pdf_files: PDF文件路径列表
            
        Returns:
            上传信息字典（包含batch_id和file_urls）
        """
        files_data = [{
            "name": Path(f).name,
            "is_ocr": True,
            "data_id": f"batch_{i}_{int(time.time())}"
        } for i, f in enumerate(pdf_files)]
        
        data = {
            "enable_formula": True,
            "enable_table": True,
            "language": "auto",
            "model_version": "v2",
            "files": files_data
        }
        
        try:
            url = f"{self.base_url}/file-urls/batch"
            resp = requests.post(url, headers=self.headers, json=data, timeout=30)
            result = resp.json()
            if resp.status_code == 200 and result.get("code") == 0:
                logger.info(f"✅ 成功申请 {len(pdf_files)} 个文件的上传链接")
                return result["data"]
            else:
                logger.error(f"申请上传链接失败: {resp.text}")
                return None
        except Exception as e:
            logger.error(f"申请上传链接出错: {e}")
            return None
    
    def wait_for_batch_result(self, batch_id: str, max_wait: int = 3600) -> Optional[List[Dict]]:
        """
        等待批量任务完成
        
        Args:
            batch_id: 批次ID
            max_wait: 最大等待时间（秒）
            
        Returns:
            提取结果列表
        """
        url = f"{self.base_url}/extract-results/batch/{batch_id}"
        start = time.time()
        
        while time.time() - start < max_wait:
            try:
                resp = requests.get(url, headers=self.headers, timeout=30)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("code") == 0:
                        extract_results = result["data"]["extract_result"]
                        states = [f"{r['file_name']}={r['state']}" for r in extract_results]
                        logger.info(f"进度: {', '.join(states)}")
                        
                        if all(r['state'] in ['done', 'failed'] for r in extract_results):
                            success_count = sum(1 for r in extract_results if r['state'] == 'done')
                            logger.info(f"✅ 批次完成: {success_count}/{len(extract_results)} 成功")
                            return extract_results
                else:
                    logger.warning(f"查询失败: {resp.status_code}")
            except Exception as e:
                logger.error(f"查询出错: {e}")
            
            time.sleep(15)
        
        logger.error("等待超时")
        return None
    
    def download_and_extract(self, result: Dict, output_dir: str) -> Optional[str]:
        """
        下载并解压结果（含图片）
        
        Args:
            result: 提取结果字典
            output_dir: 输出目录
            
        Returns:
            解压后的目录路径
        """
        if result.get("state") != "done" or "full_zip_url" not in result:
            logger.warning(f"文件 {result.get('file_name')} 处理失败或无下载链接")
            return None
        
        zip_url = result["full_zip_url"]
        file_name = result.get("file_name", "result")
        
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # 下载ZIP文件
            logger.info(f"正在下载 {file_name}...")
            resp = requests.get(zip_url, stream=True, timeout=300)
            if resp.status_code != 200:
                logger.error(f"下载失败: {resp.status_code}")
                return None
            
            zip_path = Path(output_dir) / f"temp_{int(time.time())}.zip"
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            
            # 解压
            extract_dir = Path(output_dir) / Path(file_name).stem
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
            
            # 删除临时ZIP文件
            zip_path.unlink()
            
            logger.info(f"✅ 结果已保存到 {extract_dir}")
            return str(extract_dir)
            
        except Exception as e:
            logger.error(f"下载解压失败: {e}")
            return None
    
    def parse_pdfs(self, pdf_files: List[str], output_dir: str) -> List[str]:
        """
        处理多个PDF文件
        
        Args:
            pdf_files: PDF文件路径列表
            output_dir: 输出目录
            
        Returns:
            成功解压的目录列表
        """
        if not pdf_files:
            logger.warning("未找到PDF文件")
            return []
        
        logger.info(f"准备处理 {len(pdf_files)} 个文件")
        
        # 1. 申请上传链接
        upload_info = self.request_upload_urls(pdf_files)
        if not upload_info:
            return []
        
        batch_id = upload_info["batch_id"]
        upload_urls = upload_info["file_urls"]
        
        # 2. 上传文件
        logger.info("开始上传文件...")
        for pdf, url in zip(pdf_files, upload_urls):
            if not self.upload_file_with_retry(pdf, url):
                logger.warning(f"文件 {pdf} 上传失败")
        
        # 3. 等待结果
        logger.info(f"等待批次 {batch_id} 处理完成...")
        results = self.wait_for_batch_result(batch_id)
        if not results:
            return []
        
        # 4. 下载并解压
        logger.info("下载并解压结果...")
        extracted_dirs = []
        for r in results:
            extract_dir = self.download_and_extract(r, output_dir)
            if extract_dir:
                extracted_dirs.append(extract_dir)
        
        logger.info(f"✅ 完成处理，成功 {len(extracted_dirs)}/{len(pdf_files)} 个文件")
        return extracted_dirs
    
    def get_json_path(self, extract_dir: str) -> Optional[str]:
        """
        获取解压目录中的JSON文件路径
        
        Args:
            extract_dir: 解压后的目录
            
        Returns:
            JSON文件路径
        """
        extract_path = Path(extract_dir)
        
        if not extract_path.exists():
            logger.error(f"目录不存在: {extract_dir}")
            return None
        
        # 优先查找layout.json（MinerU的标准输出）
        layout_json = extract_path / "layout.json"
        if layout_json.exists():
            logger.info(f"找到layout.json: {layout_json}")
            return str(layout_json)
        
        # 查找auto目录下的JSON文件
        auto_dir = extract_path / "auto"
        if auto_dir.exists():
            json_files = list(auto_dir.glob("*.json"))
            if json_files:
                logger.info(f"在auto目录找到JSON: {json_files[0]}")
                return str(json_files[0])
        
        # 直接在根目录查找所有JSON文件
        json_files = list(extract_path.glob("*.json"))
        if json_files:
            # 优先选择layout.json或model.json
            for json_file in json_files:
                if json_file.name in ['layout.json', 'model.json']:
                    logger.info(f"找到JSON文件: {json_file}")
                    return str(json_file)
            # 否则返回第一个
            logger.info(f"找到JSON文件: {json_files[0]}")
            return str(json_files[0])
        
        logger.warning(f"未在 {extract_dir} 中找到JSON文件，目录内容: {[f.name for f in extract_path.iterdir()]}")
        return None
    
    def get_images_dir(self, extract_dir: str) -> Optional[str]:
        """
        获取解压目录中的图片目录
        
        Args:
            extract_dir: 解压后的目录
            
        Returns:
            图片目录路径
        """
        extract_path = Path(extract_dir)
        
        # 查找auto目录下的images目录
        auto_images = extract_path / "auto" / "images"
        if auto_images.exists() and auto_images.is_dir():
            return str(auto_images)
        
        # 查找根目录下的images目录
        images_dir = extract_path / "images"
        if images_dir.exists() and images_dir.is_dir():
            return str(images_dir)
        
        logger.warning(f"未在 {extract_dir} 中找到images目录")
        return None

