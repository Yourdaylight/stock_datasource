#!/usr/bin/env python3
"""
验证 MCP 工具注册脚本。
用于 tushare-plugin-builder skill 生成插件后的 MCP 工具验证。

用法:
  python verify_mcp_tool.py                        # 列出所有已注册工具
  python verify_mcp_tool.py --tool TOOL_NAME      # 验证指定工具
  python verify_mcp_tool.py --pattern PATTERN     # 搜索工具名
"""

import argparse
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root / "src"))


def list_mcp_tools(pattern: str = None) -> bool:
    """列出所有已注册的 MCP 工具。"""
    try:
        # 导入 MCP 服务模块
        from stock_datasource.services.mcp_server import mcp
        
        tools = mcp.list_tools()
        
        if pattern:
            tools = [t for t in tools if pattern.lower() in t.name.lower()]
        
        print(f"\n已注册的 MCP 工具 ({len(tools)} 个):")
        print("-" * 70)
        
        for tool in sorted(tools, key=lambda t: t.name):
            desc = tool.description[:50] + "..." if len(tool.description) > 50 else tool.description
            print(f"  {tool.name:40} {desc}")
        
        print("-" * 70)
        return True
        
    except ImportError as e:
        print(f"❌ 无法导入 MCP 服务模块: {e}")
        print("\n请确保已安装 mcp 依赖:")
        print("  pip install mcp")
        return False
    except Exception as e:
        print(f"❌ 列出工具失败: {e}")
        return False


def verify_tool(tool_name: str) -> bool:
    """验证指定工具是否已注册。"""
    try:
        from stock_datasource.services.mcp_server import mcp
        
        tools = mcp.list_tools()
        tool_names = [t.name for t in tools]
        
        if tool_name in tool_names:
            print(f"✅ 工具 {tool_name} 已注册")
            
            # 获取工具详情
            tool = next(t for t in tools if t.name == tool_name)
            print(f"\n工具详情:")
            print(f"  名称: {tool.name}")
            print(f"  描述: {tool.description}")
            
            if hasattr(tool, "inputSchema") and tool.inputSchema:
                print(f"\n输入参数 Schema:")
                properties = tool.inputSchema.get("properties", {})
                required = tool.inputSchema.get("required", [])
                for prop_name, prop_def in properties.items():
                    req_mark = "*" if prop_name in required else " "
                    prop_type = prop_def.get("type", "any")
                    prop_desc = prop_def.get("description", "")
                    print(f"    {req_mark}{prop_name}: {prop_type} - {prop_desc}")
            
            return True
        else:
            print(f"❌ 工具 {tool_name} 未注册")
            
            # 搜索相似工具
            similar = [n for n in tool_names if tool_name.lower() in n.lower()]
            if similar:
                print(f"\n相似工具:")
                for name in similar[:5]:
                    print(f"  - {name}")
            
            return False
            
    except ImportError as e:
        print(f"❌ 无法导入 MCP 服务模块: {e}")
        return False
    except Exception as e:
        print(f"❌ 验证工具失败: {e}")
        return False


def verify_service_tools(service_name: str) -> bool:
    """验证指定服务的所有工具是否已注册。"""
    try:
        from stock_datasource.services.mcp_server import mcp
        
        tools = mcp.list_tools()
        service_tools = [t for t in tools if service_name.lower() in t.name.lower()]
        
        if service_tools:
            print(f"✅ 服务 {service_name} 已注册 {len(service_tools)} 个工具:")
            for tool in service_tools:
                print(f"  - {tool.name}")
            return True
        else:
            print(f"❌ 未找到服务 {service_name} 的工具")
            return False
            
    except ImportError as e:
        print(f"❌ 无法导入 MCP 服务模块: {e}")
        return False
    except Exception as e:
        print(f"❌ 验证服务工具失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="验证 MCP 工具注册")
    parser.add_argument("--tool", "-t", help="要验证的工具名称")
    parser.add_argument("--service", "-s", help="要验证的服务名称")
    parser.add_argument("--pattern", "-p", help="工具名过滤模式")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有工具")
    
    args = parser.parse_args()
    
    # 验证指定工具
    if args.tool:
        if not verify_tool(args.tool):
            sys.exit(1)
    # 验证服务工具
    elif args.service:
        if not verify_service_tools(args.service):
            sys.exit(1)
    # 列出工具
    else:
        if not list_mcp_tools(args.pattern):
            sys.exit(1)
    
    print("\n✅ 验证完成")


if __name__ == "__main__":
    main()
