#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen API 测试脚本
测试DashScope API密钥和账户状态
"""

import json
import base64
import requests
from pathlib import Path
from config import DASHSCOPE_API_KEY, QWEN_CHAT_ENDPOINT, MODEL_NAME


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_text_api():
    """测试Qwen文本API（qwen-plus）"""
    print_section("测试 1: Qwen 文本API")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "你是一个专业的AI助手。"
            },
            {
                "role": "user",
                "content": "请用一句话介绍TADF（热活化延迟荧光）材料。"
            }
        ],
        "temperature": 0.7,
        "max_tokens": 200
    }
    
    print(f"\n📡 请求信息:")
    print(f"   URL: {QWEN_CHAT_ENDPOINT}")
    print(f"   模型: {MODEL_NAME}")
    print(f"   API Key: {DASHSCOPE_API_KEY[:20]}...{DASHSCOPE_API_KEY[-10:]}")
    
    try:
        print(f"\n⏳ 发送请求...")
        response = requests.post(
            QWEN_CHAT_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"\n📥 响应状态: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            print(f"✅ 成功！")
            print(f"\n💬 AI回复:")
            print(f"   {content}")
            
            # 显示使用量
            usage = result.get("usage", {})
            if usage:
                print(f"\n📊 Token使用:")
                print(f"   输入: {usage.get('prompt_tokens', 0)}")
                print(f"   输出: {usage.get('completion_tokens', 0)}")
                print(f"   总计: {usage.get('total_tokens', 0)}")
            
            return True
        else:
            print(f"❌ 失败！")
            error_data = response.json()
            print(f"\n错误详情:")
            print(json.dumps(error_data, indent=2, ensure_ascii=False))
            
            # 解析常见错误
            error_code = error_data.get("error", {}).get("code", "")
            if error_code == "Arrearage":
                print(f"\n⚠️  错误类型: 账户欠费")
                print(f"   解决方案:")
                print(f"   1. 访问阿里云控制台充值: https://home.console.aliyun.com/")
                print(f"   2. 查看DashScope账单: https://dashscope.console.aliyun.com/")
            elif error_code == "InvalidApiKey":
                print(f"\n⚠️  错误类型: API密钥无效")
                print(f"   解决方案:")
                print(f"   1. 检查config.py中的DASHSCOPE_API_KEY是否正确")
                print(f"   2. 重新生成API Key: https://dashscope.console.aliyun.com/apiKey")
            
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时（>30秒）")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ 网络连接失败")
        print(f"   请检查网络连接")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_vl_api():
    """测试Qwen-VL多模态API"""
    print_section("测试 2: Qwen-VL 多模态API")
    
    # 创建一个简单的测试图片
    test_image_path = Path("test_image.png")
    
    if not test_image_path.exists():
        print(f"\n📝 创建测试图片...")
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # 创建一个简单的测试图片
            img = Image.new('RGB', (400, 200), color='white')
            draw = ImageDraw.Draw(img)
            
            # 画一些文字
            draw.text((50, 80), "Test Image for Qwen-VL", fill='black')
            draw.rectangle([50, 50, 350, 150], outline='blue', width=2)
            
            img.save(test_image_path)
            print(f"✅ 测试图片已创建: {test_image_path}")
        except ImportError:
            print(f"⚠️  Pillow未安装，跳过VL测试")
            print(f"   安装: pip install pillow")
            return None
        except Exception as e:
            print(f"⚠️  创建测试图片失败: {e}")
            return None
    
    # 编码图片为base64
    try:
        with open(test_image_path, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f"❌ 读取图片失败: {e}")
        return False
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}"
    }
    
    payload = {
        "model": "qwen-vl-plus",  # 或 qwen-vl-max
        "messages": [
            {
                "role": "system",
                "content": "你是一个视觉识别专家。"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "请描述这张图片的内容。"
                    }
                ]
            }
        ],
        "temperature": 0.1
    }
    
    print(f"\n📡 请求信息:")
    print(f"   URL: {QWEN_CHAT_ENDPOINT}")
    print(f"   模型: qwen-vl-plus")
    print(f"   图片: {test_image_path}")
    
    try:
        print(f"\n⏳ 发送请求...")
        response = requests.post(
            QWEN_CHAT_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        print(f"\n📥 响应状态: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            print(f"✅ 成功！")
            print(f"\n💬 AI回复:")
            print(f"   {content}")
            
            return True
        else:
            print(f"❌ 失败！")
            error_data = response.json()
            print(f"\n错误详情:")
            print(json.dumps(error_data, indent=2, ensure_ascii=False))
            return False
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_api_info():
    """显示API配置信息"""
    print_section("当前API配置")
    
    print(f"\n📋 配置信息:")
    print(f"   API Key: {DASHSCOPE_API_KEY[:20]}...{DASHSCOPE_API_KEY[-10:]}")
    print(f"   端点: {QWEN_CHAT_ENDPOINT}")
    print(f"   默认模型: {MODEL_NAME}")
    
    print(f"\n🔗 相关链接:")
    print(f"   DashScope控制台: https://dashscope.console.aliyun.com/")
    print(f"   API Key管理: https://dashscope.console.aliyun.com/apiKey")
    print(f"   账单查询: https://usercenter2.aliyun.com/finance/expense-bill/overview")
    print(f"   文档: https://help.aliyun.com/zh/model-studio/")


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "Qwen API 测试工具" + " " * 30 + "║")
    print("╚" + "=" * 68 + "╝")
    
    # 显示配置信息
    test_api_info()
    
    # 检查API Key
    if not DASHSCOPE_API_KEY or DASHSCOPE_API_KEY == "你的API key":
        print("\n" + "=" * 70)
        print("❌ 错误: API Key未配置")
        print("=" * 70)
        print("\n请在 config.py 中设置 DASHSCOPE_API_KEY")
        print("获取API Key: https://dashscope.console.aliyun.com/apiKey")
        return
    
    # 运行测试
    results = []
    
    # 测试1: 文本API
    text_result = test_text_api()
    results.append(("文本API (qwen-plus)", text_result))
    
    # 测试2: 多模态API
    if text_result:  # 只有在文本API成功时才测试VL
        print("\n⏸️  按Enter继续测试Qwen-VL，或Ctrl+C跳过...")
        try:
            input()
            vl_result = test_vl_api()
            if vl_result is not None:
                results.append(("多模态API (qwen-vl-plus)", vl_result))
        except KeyboardInterrupt:
            print("\n跳过VL测试")
    
    # 总结
    print_section("测试总结")
    
    print("\n测试结果:")
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {name}: {status}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\n🎉 所有测试通过！API工作正常")
        print("\n✅ 您可以运行完整的数据抽取流程:")
        print("   python main.py --mode single --paper-id test --pdf-path data/raw_pdfs/paper.pdf")
    else:
        print("\n⚠️  部分测试失败，请根据上述错误信息解决问题")
        
        if not results[0][1]:  # 文本API失败
            print("\n💡 建议:")
            print("   1. 检查API Key是否正确")
            print("   2. 确认账户余额充足")
            print("   3. 访问DashScope控制台查看详情")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  测试已取消")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

