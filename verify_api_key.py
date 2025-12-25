#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速验证Qwen API Key
"""

import os
import sys
import requests

def verify_api_key(api_key=None):
    """验证API Key是否有效"""
    
    if not api_key:
        # 从环境变量或用户输入获取
        api_key = os.getenv("DASHSCOPE_API_KEY")
        
        if not api_key:
            print("请输入您的DashScope API Key:")
            api_key = input().strip()
    
    if not api_key or api_key == "你的API key":
        print("❌ API Key为空或未设置")
        return False
    
    print(f"\n🔍 验证API Key: {api_key[:20]}...{api_key[-10:]}")
    
    # 发送测试请求
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": "qwen-plus",
        "messages": [
            {"role": "user", "content": "Hello"}
        ],
        "max_tokens": 10
    }
    
    try:
        print("⏳ 发送测试请求...")
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        print(f"📥 响应状态: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ API Key有效！账户状态正常")
            
            # 显示如何设置
            print("\n💡 如何使用这个API Key:")
            print("\n方法1: 环境变量（推荐）")
            print(f'   export DASHSCOPE_API_KEY="{api_key}"')
            
            print("\n方法2: 修改config.py")
            print(f'   DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "{api_key}")')
            
            return True
            
        elif response.status_code == 401:
            print("❌ API Key无效")
            error = response.json().get("error", {})
            print(f"   错误: {error.get('message', '未知错误')}")
            print("\n📝 解决方案:")
            print("   1. 访问 https://dashscope.console.aliyun.com/apiKey")
            print("   2. 创建新的API Key")
            print("   3. 重新运行此脚本验证")
            return False
            
        elif response.status_code == 400:
            error = response.json().get("error", {})
            error_code = error.get("code", "")
            
            if error_code == "Arrearage":
                print("❌ 账户欠费")
                print(f"   错误: {error.get('message', '')}")
                print("\n📝 解决方案:")
                print("   1. 访问 https://home.console.aliyun.com/")
                print("   2. 充值或开通免费试用")
                return False
            else:
                print(f"❌ 请求失败: {error.get('message', '未知错误')}")
                return False
        else:
            print(f"❌ 未知错误: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("  DashScope API Key 验证工具")
    print("="*60 + "\n")
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    else:
        api_key = None
    
    result = verify_api_key(api_key)
    
    print("\n" + "="*60)
    if result:
        print("✅ 验证成功！可以使用API了")
        print("\n下一步:")
        print("   python test_qwen_api.py  # 运行完整测试")
    else:
        print("❌ 验证失败，请检查API Key")
        print("\n获取API Key:")
        print("   https://dashscope.console.aliyun.com/apiKey")
    print("="*60 + "\n")
    
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())

