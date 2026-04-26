#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""翻译模块 - 腾讯云翻译 API"""

import os
import sys
import json
import time
import hashlib
import urllib.request
import urllib.parse

def translate_to_chinese(text, source_lang='ja'):
    """翻译函数
    设置环境变量:
        SECRET_ID - 腾讯云 SecretId
        SECRET_KEY - 腾讯云 SecretKey
    """
    secret_id = os.environ.get('SecretId', '')
    secret_key = os.environ.get('SecretKey', '')

    if not secret_id or not secret_key:
        print("[翻译] 错误: 未配置环境变量 SecretId/SecretKey")
        return text

    try:
        # 构造请求参数
        source_code = 'ja' if source_lang == 'ja' else 'en'

        # 腾讯云翻译 API
        payload = json.dumps({
            'SourceText': text[:500],
            'Source': source_code,
            'Target': 'zh-CHS',
            'ProjectId': 0
        })

        # 生成签名
        timestamp = str(int(time.time() * 1000)
        nonce = str(int(time.time() * 1000)

        # 简化签名
        sign_str = f"{secret_id}{text[:50]}{timestamp}{nonce}{secret_key}"
        signature = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

        # 构造 URL
        params = {
            'SourceText': text[:500],
            'Source': source_code,
            'Target': 'zh-CHS',
            'ProjectId': 0,
            'SecretId': secret_id,
            'Timestamp': timestamp,
            'Nonce': nonce,
            'Signature': signature
        }

        query = urllib.parse.urlencode(params)
        url = f"https://tmt.cloud.tencent.com/translate?{query}"

        # 发送请求
        req = urllib.request.Request(url, method='GET')
        req.add_header('Content-Type', 'application/json; charset=utf-8')

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))

            if result.get('Response', {}).get('TargetText'):
                return result['Response']['TargetText']

        print(f"[翻译] 响应: {result}")
        return text

    except Exception as e:
        print(f"[翻译] 错误: {e}")
        return text

if __name__ == '__main__':
    # 测试
    os.environ['SecretId'] = 'YOUR_SECRET_ID'
    os.environ['SecretKey'] = 'YOUR_SECRET_KEY'

    test_text = 'Hello World'
    result = translate_to_chinese(test_text, 'en')
    print(f"翻译结果: {result}")
