#!/usr/bin/env python3
"""
验证 HTTP 服务端点脚本。
用于 tushare-plugin-builder skill 生成插件后的 HTTP 服务验证。

用法:
  python verify_service_http.py --service SERVICE_NAME
  python verify_service_http.py --service ths_daily --method get_by_date_range --params '{"ts_code":"885001.TI","start_date":"20250101","end_date":"20250110"}'
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


DEFAULT_HOST = "http://localhost:8000"


def check_server_running(host: str) -> bool:
    """检查 HTTP 服务是否运行。"""
    try:
        req = Request(f"{host}/health", method="GET")
        with urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def list_routes(host: str) -> None:
    """列出所有可用路由。"""
    try:
        req = Request(f"{host}/openapi.json", method="GET")
        with urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            paths = data.get("paths", {})
            print(f"\n可用 API 路由 ({len(paths)} 个):")
            print("-" * 70)
            for path, methods in sorted(paths.items()):
                for method in methods:
                    if method.upper() in ("GET", "POST", "PUT", "DELETE"):
                        print(f"  {method.upper():6} {path}")
            print("-" * 70)
    except Exception as e:
        print(f"❌ 无法获取路由列表: {e}")


def call_service(host: str, service: str, method: str, params: dict) -> bool:
    """调用服务方法。"""
    url = f"{host}/api/{service}/{method}"
    print(f"\n正在调用: POST {url}")
    print(f"参数: {json.dumps(params, ensure_ascii=False)}")
    
    try:
        req = Request(
            url,
            data=json.dumps(params).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            print(f"\n✅ 响应状态: {response.status}")
            
            # 解析响应
            if isinstance(result, dict):
                if "data" in result:
                    data = result["data"]
                    if isinstance(data, list):
                        print(f"返回 {len(data)} 条记录")
                        if data:
                            print("\n前3条记录:")
                            for item in data[:3]:
                                print(f"  {json.dumps(item, ensure_ascii=False, default=str)}")
                    else:
                        print(f"返回数据: {json.dumps(data, ensure_ascii=False, indent=2, default=str)[:500]}")
                else:
                    print(f"返回: {json.dumps(result, ensure_ascii=False, indent=2, default=str)[:500]}")
            else:
                print(f"返回: {result}")
            
            return True
            
    except HTTPError as e:
        print(f"❌ HTTP 错误: {e.code} {e.reason}")
        try:
            error_body = e.read().decode("utf-8")
            print(f"错误详情: {error_body[:500]}")
        except Exception:
            pass
        return False
    except URLError as e:
        print(f"❌ 连接错误: {e.reason}")
        return False
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


def generate_curl_example(host: str, service: str, method: str, params: dict) -> None:
    """生成 curl 命令示例。"""
    url = f"{host}/api/{service}/{method}"
    params_json = json.dumps(params, ensure_ascii=False)
    
    print(f"\n📋 curl 命令示例:")
    print("-" * 70)
    print(f'curl -X POST "{url}" \\')
    print('  -H "Content-Type: application/json" \\')
    print(f"  -d '{params_json}'")
    print("-" * 70)


def main():
    parser = argparse.ArgumentParser(description="验证 HTTP 服务端点")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"HTTP 服务地址 (默认: {DEFAULT_HOST})")
    parser.add_argument("--service", "-s", help="服务名称 (如: ths_daily)")
    parser.add_argument("--method", "-m", help="方法名称 (如: get_by_date_range)")
    parser.add_argument("--params", "-p", default="{}", help="请求参数 (JSON 格式)")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有路由")
    parser.add_argument("--curl", "-c", action="store_true", help="仅生成 curl 命令")
    
    args = parser.parse_args()
    
    # 检查服务是否运行
    print(f"正在检查 HTTP 服务: {args.host}")
    if not check_server_running(args.host):
        print(f"❌ HTTP 服务未运行或无法访问: {args.host}")
        print("\n启动服务命令:")
        print("  python -m stock_datasource.services.http_server")
        sys.exit(1)
    print("✅ HTTP 服务运行中")
    
    # 列出路由
    if args.list:
        list_routes(args.host)
        sys.exit(0)
    
    # 调用服务
    if args.service and args.method:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"❌ 参数 JSON 格式错误: {e}")
            sys.exit(1)
        
        # 生成 curl 示例
        generate_curl_example(args.host, args.service, args.method, params)
        
        # 如果只生成 curl 命令
        if args.curl:
            sys.exit(0)
        
        # 实际调用
        if not call_service(args.host, args.service, args.method, params):
            sys.exit(1)
    elif not args.list:
        print("\n请指定 --service 和 --method，或使用 --list 查看所有路由")
        parser.print_help()
        sys.exit(1)
    
    print("\n✅ 验证完成")


if __name__ == "__main__":
    main()
