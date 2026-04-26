# 翻译模块 - 简化版
import os
import json
import time
import hashlib
import urllib.request

# 测试代码
def test_translate():
    # 测试翻译
    SECRET_ID = os.environ.get('SecretId', 'your_secret_id')
    SECRET_KEY = os.environ.get('SecretKey', 'your_secret_key')

    print(f"SecretId: {SECRET_ID[:10] if SECRET_ID else 'NOT SET'}")
    print(f"SecretKey: {SECRET_KEY[:10] if SECRET_KEY else 'NOT SET'}")

    if not SECRET_ID or not SECRET_KEY:
        print("[翻译] 环境变量未配置")
        return

    try:
        from_lang = 'en'
        text = 'Hello World'
        timestamp = str(int(time.time() * 1000)
        sign_str = f"SecretId={SECRET_ID}&SecretKey={SECRET_KEY}&Timestamp={timestamp}"
        signature = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

        payload = json.dumps({
            'SourceText': text,
            'Source': 'en',
            'Target': 'zh-CHS',
            'ProjectId': 0
        })

        url = (f"https://tmt.tencentcloudapi.com/?Action=TextTranslate"
              f"&Version=2018-03-21&SecretId={SECRET_ID}&Timestamp={timestamp}&Signature={signature}&SignatureType=TC3-HMAC-SHA256")

        print(f"URL: {url[:80]}...")

        req = urllib.request.Request(
            url,
            data=payload.encode('utf-8'),
            headers={'Content-Type': 'application/json; charset=utf-8'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            print(f"Response: {result}")

            if result.get('Response', {}).get('TargetText'):
                print(f"翻译结果: {result['Response']['TargetText']}")
            else:
                print(f"翻译失败: {result}")

    except Exception as e:
        print(f"错误: {e}")

if __name__ == '__main__':
    test_translate()
