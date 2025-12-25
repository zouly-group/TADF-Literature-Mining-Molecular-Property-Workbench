#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DECIMER服务端测试脚本
"""

import sys
import time
import requests
from pathlib import Path

# 测试配置
API_URL = "http://localhost:8000"
TIMEOUT = 30


def test_health_check():
    """测试健康检查端点"""
    print("=" * 60)
    print("测试1: 健康检查")
    print("=" * 60)
    
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 服务状态: {data.get('status')}")
            print(f"   模式: {data.get('mode')}")
            print(f"   Python包可用: {data.get('python_available')}")
            return True
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到服务 {API_URL}")
        print("   请确保服务已启动: python server.py")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_service_info():
    """测试服务信息端点"""
    print("\n" + "=" * 60)
    print("测试2: 服务信息")
    print("=" * 60)
    
    try:
        response = requests.get(f"{API_URL}/", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 服务名称: {data.get('service')}")
            print(f"   版本: {data.get('version')}")
            print(f"   模式: {data.get('mode')}")
            print("   端点:")
            for endpoint, desc in data.get('endpoints', {}).items():
                print(f"     {endpoint}: {desc}")
            return True
        else:
            print(f"❌ 获取服务信息失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_predict_with_file(image_path: str):
    """测试文件上传识别"""
    print("\n" + "=" * 60)
    print("测试3: 分子结构识别")
    print("=" * 60)
    
    if not Path(image_path).exists():
        print(f"❌ 图片文件不存在: {image_path}")
        return False
    
    print(f"上传文件: {image_path}")
    
    try:
        with open(image_path, 'rb') as f:
            files = {'image': f}
            
            start_time = time.time()
            response = requests.post(
                f"{API_URL}/predict",
                files=files,
                timeout=TIMEOUT
            )
            elapsed = time.time() - start_time
        
        print(f"响应状态码: {response.status_code}")
        print(f"耗时: {elapsed:.2f}秒")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                smiles = data.get('smiles', '')
                print(f"✅ 识别成功!")
                print(f"   SMILES: {smiles}")
                print(f"   方法: {data.get('method')}")
                print(f"   服务器耗时: {data.get('elapsed_time', 0):.2f}秒")
                
                if 'token_confidences' in data:
                    token_confs = data.get('token_confidences', [])
                    print(f"   Token置信度数量: {len(token_confs)}")
                
                return True
            else:
                print(f"❌ 识别失败: {data.get('error')}")
                return False
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时 (>{TIMEOUT}秒)")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_error_handling():
    """测试错误处理"""
    print("\n" + "=" * 60)
    print("测试4: 错误处理")
    print("=" * 60)
    
    # 测试1: 缺少文件
    print("\n4.1 测试缺少文件...")
    try:
        response = requests.post(f"{API_URL}/predict", timeout=5)
        if response.status_code == 400:
            print("✅ 正确返回400错误")
        else:
            print(f"⚠️  期望400，实际{response.status_code}")
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    # 测试2: 空文件名
    print("\n4.2 测试空文件名...")
    try:
        files = {'image': ('', b'')}
        response = requests.post(f"{API_URL}/predict", files=files, timeout=5)
        if response.status_code == 400:
            print("✅ 正确返回400错误")
        else:
            print(f"⚠️  期望400，实际{response.status_code}")
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    # 测试3: 不支持的文件类型
    print("\n4.3 测试不支持的文件类型...")
    try:
        files = {'image': ('test.txt', b'test content')}
        response = requests.post(f"{API_URL}/predict", files=files, timeout=5)
        if response.status_code == 400:
            print("✅ 正确返回400错误")
        else:
            print(f"⚠️  期望400，实际{response.status_code}")
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    return True


def create_test_image():
    """创建一个简单的测试图片（如果没有真实图片）"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # 创建一个简单的测试图片
        img = Image.new('RGB', (400, 200), color='white')
        draw = ImageDraw.Draw(img)
        
        # 画一个简单的苯环示意
        draw.ellipse([100, 50, 200, 150], outline='black', width=2)
        draw.text((150, 170), "Test Structure", fill='black')
        
        test_path = Path("test_structure.png")
        img.save(test_path)
        
        print(f"✅ 已创建测试图片: {test_path}")
        return str(test_path)
        
    except ImportError:
        print("⚠️  Pillow未安装，无法创建测试图片")
        return None


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "DECIMER服务端测试" + " " * 25 + "║")
    print("╚" + "=" * 58 + "╝")
    print(f"\nAPI地址: {API_URL}")
    print(f"超时设置: {TIMEOUT}秒\n")
    
    # 统计结果
    tests_passed = 0
    tests_total = 0
    
    # 测试1: 健康检查
    tests_total += 1
    if test_health_check():
        tests_passed += 1
    
    # 测试2: 服务信息
    tests_total += 1
    if test_service_info():
        tests_passed += 1
    
    # 测试3: 文件上传识别（需要提供图片）
    test_image = None
    
    # 尝试从命令行参数获取图片路径
    if len(sys.argv) > 1:
        test_image = sys.argv[1]
    else:
        # 尝试查找项目中的示例图片
        possible_paths = [
            "image2.png",
            "image1.png",
            "image2.png"
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                test_image = path
                break
        
        # 如果没有图片，尝试创建一个
        if not test_image:
            print("\n⚠️  未找到测试图片，尝试创建...")
            test_image = create_test_image()
    
    if test_image:
        tests_total += 1
        if test_predict_with_file(test_image):
            tests_passed += 1
    else:
        print("\n⚠️  跳过文件上传测试（无可用图片）")
        print("   提示: python test_decimer_server.py <image_path>")
    
    # 测试4: 错误处理
    tests_total += 1
    if test_error_handling():
        tests_passed += 1
    
    # 输出总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"总测试数: {tests_total}")
    print(f"通过: {tests_passed}")
    print(f"失败: {tests_total - tests_passed}")
    print(f"通过率: {tests_passed/tests_total*100:.1f}%")
    print("=" * 60)
    
    if tests_passed == tests_total:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print("\n⚠️  部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())

