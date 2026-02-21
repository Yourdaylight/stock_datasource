#!/usr/bin/env python3
"""
验证插件是否符合规范的脚本。
用于 tushare-plugin-builder skill 验证用户编写的插件是否符合项目规范。

用法:
  python validate_plugin.py PLUGIN_NAME
  python validate_plugin.py tushare_ths_daily --verbose
  python validate_plugin.py tushare_ths_daily --fix  # 尝试修复简单问题
"""

import argparse
import ast
import importlib
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any

# 将项目根目录加入 sys.path
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root / "src"))

PLUGINS_DIR = project_root / "src" / "stock_datasource" / "plugins"

# 校验结果类型
PASS = "✅"
FAIL = "❌"
WARN = "⚠️"


class PluginValidator:
    """插件规范验证器。"""

    # 必需文件列表
    REQUIRED_FILES = [
        "__init__.py",
        "plugin.py",
        "extractor.py",
        "service.py",
        "schema.json",
        "config.json",
    ]

    # schema.json 必需字段
    SCHEMA_REQUIRED_FIELDS = ["table_name", "columns", "engine", "order_by"]

    # config.json 必需字段
    CONFIG_REQUIRED_FIELDS = ["rate_limit", "timeout", "retry_attempts"]

    # 必需的系统列
    SYSTEM_COLUMNS = ["version", "_ingested_at"]

    def __init__(self, plugin_name: str, verbose: bool = False):
        self.plugin_name = plugin_name
        self.plugin_dir = PLUGINS_DIR / plugin_name
        self.verbose = verbose
        self.results: List[Tuple[str, str, str]] = []  # (status, check_name, message)
        self.errors = 0
        self.warnings = 0

    def log(self, status: str, check: str, message: str):
        """记录检查结果。"""
        self.results.append((status, check, message))
        if status == FAIL:
            self.errors += 1
        elif status == WARN:
            self.warnings += 1

    def validate(self) -> bool:
        """执行所有验证。"""
        print(f"\n{'='*70}")
        print(f"验证插件: {self.plugin_name}")
        print(f"路径: {self.plugin_dir}")
        print(f"{'='*70}\n")

        # 1. 检查目录是否存在
        if not self.plugin_dir.exists():
            self.log(FAIL, "目录存在", f"插件目录不存在: {self.plugin_dir}")
            self._print_results()
            return False

        # 2. 检查必需文件
        self._check_required_files()

        # 3. 检查 __init__.py
        self._check_init_py()

        # 4. 检查 plugin.py
        self._check_plugin_py()

        # 5. 检查 extractor.py
        self._check_extractor_py()

        # 6. 检查 service.py
        self._check_service_py()

        # 7. 检查 schema.json
        self._check_schema_json()

        # 8. 检查 config.json
        self._check_config_json()

        # 9. 尝试导入模块
        self._check_import()

        # 10. 检查数据库表
        self._check_database_table()

        self._print_results()
        return self.errors == 0

    def _check_required_files(self):
        """检查必需文件是否存在。"""
        for filename in self.REQUIRED_FILES:
            filepath = self.plugin_dir / filename
            if filepath.exists():
                self.log(PASS, f"文件 {filename}", "存在")
            else:
                self.log(FAIL, f"文件 {filename}", "缺失")

    def _check_init_py(self):
        """检查 __init__.py 内容。"""
        init_file = self.plugin_dir / "__init__.py"
        if not init_file.exists():
            return

        content = init_file.read_text(encoding="utf-8")

        # 检查是否导出插件类
        if "Plugin" in content:
            self.log(PASS, "__init__.py 导出", "导出了 Plugin 类")
        else:
            self.log(WARN, "__init__.py 导出", "未找到 Plugin 类导出")

        # 检查是否导出 Service
        if "Service" in content:
            self.log(PASS, "__init__.py 导出", "导出了 Service 类")
        else:
            self.log(WARN, "__init__.py 导出", "未找到 Service 类导出")

    def _check_plugin_py(self):
        """检查 plugin.py 内容。"""
        plugin_file = self.plugin_dir / "plugin.py"
        if not plugin_file.exists():
            return

        content = plugin_file.read_text(encoding="utf-8")

        # 检查继承 BasePlugin
        if "BasePlugin" in content:
            self.log(PASS, "plugin.py 继承", "继承自 BasePlugin")
        else:
            self.log(FAIL, "plugin.py 继承", "未继承 BasePlugin")

        # 检查必需方法
        required_methods = ["extract_data", "validate_data", "transform_data", "load_data"]
        for method in required_methods:
            if f"def {method}" in content:
                self.log(PASS, f"plugin.py 方法", f"实现了 {method}")
            else:
                self.log(WARN, f"plugin.py 方法", f"未找到 {method} 方法")

        # 检查是否添加系统列
        if "version" in content and "_ingested_at" in content:
            self.log(PASS, "plugin.py 系统列", "添加了 version 和 _ingested_at")
        else:
            self.log(WARN, "plugin.py 系统列", "可能未添加 version 或 _ingested_at 列")

    def _check_extractor_py(self):
        """检查 extractor.py 内容。"""
        extractor_file = self.plugin_dir / "extractor.py"
        if not extractor_file.exists():
            return

        content = extractor_file.read_text(encoding="utf-8")

        # 检查是否使用 proxy_context
        if "proxy_context" in content:
            self.log(PASS, "extractor.py 代理", "使用了 proxy_context")
        else:
            self.log(FAIL, "extractor.py 代理", "未使用 proxy_context，API 调用可能失败")

        # 检查是否使用 tushare
        if "tushare" in content or "ts." in content:
            self.log(PASS, "extractor.py SDK", "使用了 tushare SDK")
        else:
            self.log(WARN, "extractor.py SDK", "未检测到 tushare SDK 使用")

        # 检查是否有重试逻辑
        if "retry" in content or "tenacity" in content:
            self.log(PASS, "extractor.py 重试", "实现了重试逻辑")
        else:
            self.log(WARN, "extractor.py 重试", "未检测到重试逻辑")

    def _check_service_py(self):
        """检查 service.py 内容。"""
        service_file = self.plugin_dir / "service.py"
        if not service_file.exists():
            return

        content = service_file.read_text(encoding="utf-8")

        # 检查继承 BaseService
        if "BaseService" in content:
            self.log(PASS, "service.py 继承", "继承自 BaseService")
        else:
            self.log(FAIL, "service.py 继承", "未继承 BaseService")

        # 检查 SQL 注入风险 - 字符串拼接
        dangerous_patterns = [
            r'f"[^"]*SELECT[^"]*\{',  # f-string SQL
            r"f'[^']*SELECT[^']*\{",  # f-string SQL
            r'"\s*\+\s*[^"]+\s*\+\s*"',  # 字符串拼接
            r"'\s*\+\s*[^']+\s*\+\s*'",  # 字符串拼接
            r'\.format\s*\([^)]*\)',  # format 方法
        ]

        sql_safe = True
        for pattern in dangerous_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                # 进一步检查是否在 SQL 语句中
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if re.search(pattern, line, re.IGNORECASE) and 'SELECT' in content[max(0, content.find(line)-200):content.find(line)+len(line)].upper():
                        sql_safe = False
                        break

        if sql_safe and ("%(param)s" in content or "params" in content.lower()):
            self.log(PASS, "service.py SQL 安全", "使用了参数化查询")
        elif not sql_safe:
            self.log(FAIL, "service.py SQL 安全", "检测到 SQL 注入风险，请使用参数化查询")
        else:
            self.log(WARN, "service.py SQL 安全", "未检测到参数化查询模式")

        # 检查查询方法
        query_methods = re.findall(r"def (get_\w+|query_\w+|fetch_\w+)", content)
        if query_methods:
            self.log(PASS, "service.py 查询方法", f"找到 {len(query_methods)} 个查询方法: {', '.join(query_methods[:5])}")
        else:
            self.log(WARN, "service.py 查询方法", "未找到查询方法（get_*/query_*/fetch_*）")

    def _check_schema_json(self):
        """检查 schema.json 内容。"""
        schema_file = self.plugin_dir / "schema.json"
        if not schema_file.exists():
            return

        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                schema = json.load(f)

            # 检查必需字段
            for field in self.SCHEMA_REQUIRED_FIELDS:
                if field in schema:
                    self.log(PASS, f"schema.json 字段", f"包含 {field}")
                else:
                    self.log(FAIL, f"schema.json 字段", f"缺少 {field}")

            # 检查引擎类型
            engine = schema.get("engine", "")
            if "ReplacingMergeTree" in engine:
                self.log(PASS, "schema.json 引擎", "使用 ReplacingMergeTree")
            else:
                self.log(WARN, "schema.json 引擎", f"引擎为 {engine}，推荐使用 ReplacingMergeTree")

            # 检查系统列
            columns = schema.get("columns", [])
            column_names = [c.get("name") for c in columns]
            for sys_col in self.SYSTEM_COLUMNS:
                if sys_col in column_names:
                    self.log(PASS, f"schema.json 系统列", f"包含 {sys_col}")
                else:
                    self.log(FAIL, f"schema.json 系统列", f"缺少 {sys_col} 列")

            # 检查分区
            partition_by = schema.get("partition_by", "")
            if partition_by:
                self.log(PASS, "schema.json 分区", f"分区策略: {partition_by}")
            else:
                self.log(WARN, "schema.json 分区", "未设置分区策略")

        except json.JSONDecodeError as e:
            self.log(FAIL, "schema.json 格式", f"JSON 解析错误: {e}")

    def _check_config_json(self):
        """检查 config.json 内容。"""
        config_file = self.plugin_dir / "config.json"
        if not config_file.exists():
            return

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 检查必需字段
            for field in self.CONFIG_REQUIRED_FIELDS:
                if field in config:
                    self.log(PASS, f"config.json 字段", f"包含 {field}: {config[field]}")
                else:
                    self.log(WARN, f"config.json 字段", f"缺少 {field}")

            # 检查参数 schema
            if "parameters_schema" in config:
                self.log(PASS, "config.json 参数", "包含 parameters_schema")
            else:
                self.log(WARN, "config.json 参数", "未包含 parameters_schema")

        except json.JSONDecodeError as e:
            self.log(FAIL, "config.json 格式", f"JSON 解析错误: {e}")

    def _check_import(self):
        """尝试导入插件模块。"""
        try:
            # 导入插件模块
            plugin_module = importlib.import_module(
                f"stock_datasource.plugins.{self.plugin_name}.plugin"
            )
            self.log(PASS, "模块导入", "plugin.py 导入成功")

            # 查找插件类
            plugin_class = None
            for name in dir(plugin_module):
                obj = getattr(plugin_module, name)
                if isinstance(obj, type) and name.endswith("Plugin") and name != "BasePlugin":
                    plugin_class = obj
                    break

            if plugin_class:
                self.log(PASS, "插件类", f"找到插件类: {plugin_class.__name__}")
            else:
                self.log(WARN, "插件类", "未找到以 Plugin 结尾的类")

        except ImportError as e:
            self.log(FAIL, "模块导入", f"导入失败: {e}")
        except Exception as e:
            self.log(WARN, "模块导入", f"导入时出现警告: {e}")

        try:
            # 导入 Service 模块
            service_module = importlib.import_module(
                f"stock_datasource.plugins.{self.plugin_name}.service"
            )
            self.log(PASS, "模块导入", "service.py 导入成功")

            # 查找 Service 类
            service_class = None
            for name in dir(service_module):
                obj = getattr(service_module, name)
                if isinstance(obj, type) and name.endswith("Service") and name != "BaseService":
                    service_class = obj
                    break

            if service_class:
                self.log(PASS, "Service 类", f"找到 Service 类: {service_class.__name__}")
                
                # 列出查询方法
                methods = [m for m in dir(service_class) if m.startswith(("get_", "query_", "fetch_")) and not m.startswith("_")]
                if methods:
                    self.log(PASS, "Service 方法", f"可用方法: {', '.join(methods)}")
            else:
                self.log(WARN, "Service 类", "未找到以 Service 结尾的类")

        except ImportError as e:
            self.log(FAIL, "模块导入", f"Service 导入失败: {e}")
        except Exception as e:
            self.log(WARN, "模块导入", f"Service 导入时出现警告: {e}")

    def _check_database_table(self):
        """检查数据库表是否存在。"""
        schema_file = self.plugin_dir / "schema.json"
        if not schema_file.exists():
            return

        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                schema = json.load(f)

            table_name = schema.get("table_name")
            if not table_name:
                return

            from stock_datasource.models.database import ClickHouseClient
            client = ClickHouseClient()

            if client.table_exists(table_name):
                self.log(PASS, "数据库表", f"表 {table_name} 存在")

                # 检查数据量
                result = client.execute(f"SELECT count() FROM {table_name}")
                count = result[0][0]
                if count > 0:
                    self.log(PASS, "数据库数据", f"表中有 {count:,} 条数据")
                else:
                    self.log(WARN, "数据库数据", "表为空，尚未入库数据")
            else:
                self.log(WARN, "数据库表", f"表 {table_name} 不存在，需要建表")

        except Exception as e:
            self.log(WARN, "数据库检查", f"无法连接数据库: {e}")

    def _print_results(self):
        """打印验证结果。"""
        print("\n验证结果:")
        print("-" * 70)

        # 按状态分组
        for status, check, message in self.results:
            if self.verbose or status != PASS:
                print(f"{status} [{check}] {message}")

        print("-" * 70)
        total = len(self.results)
        passed = total - self.errors - self.warnings
        print(f"\n总计: {total} 项检查")
        print(f"  {PASS} 通过: {passed}")
        print(f"  {WARN} 警告: {self.warnings}")
        print(f"  {FAIL} 失败: {self.errors}")

        if self.errors == 0:
            print(f"\n{PASS} 插件 {self.plugin_name} 验证通过！")
        else:
            print(f"\n{FAIL} 插件 {self.plugin_name} 存在 {self.errors} 个错误需要修复。")


def list_plugins() -> List[str]:
    """列出所有插件。"""
    plugins = []
    for path in PLUGINS_DIR.iterdir():
        if path.is_dir() and not path.name.startswith("_"):
            plugins.append(path.name)
    return sorted(plugins)


def main():
    parser = argparse.ArgumentParser(description="验证插件是否符合规范")
    parser.add_argument("plugin_name", nargs="?", help="要验证的插件名称")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示所有检查结果")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有插件")
    parser.add_argument("--all", "-a", action="store_true", help="验证所有插件")

    args = parser.parse_args()

    # 列出插件
    if args.list:
        plugins = list_plugins()
        print(f"\n可用插件 ({len(plugins)} 个):")
        print("-" * 40)
        for plugin in plugins:
            print(f"  - {plugin}")
        sys.exit(0)

    # 验证所有插件
    if args.all:
        plugins = list_plugins()
        results = {}
        for plugin in plugins:
            validator = PluginValidator(plugin, verbose=args.verbose)
            results[plugin] = validator.validate()

        print("\n" + "=" * 70)
        print("总体结果:")
        print("=" * 70)
        passed = sum(1 for v in results.values() if v)
        failed = len(results) - passed
        for plugin, result in results.items():
            status = PASS if result else FAIL
            print(f"  {status} {plugin}")
        print(f"\n通过: {passed}/{len(results)}, 失败: {failed}/{len(results)}")
        sys.exit(0 if failed == 0 else 1)

    # 验证单个插件
    if not args.plugin_name:
        print("请指定插件名称，或使用 --list 查看所有插件")
        parser.print_help()
        sys.exit(1)

    validator = PluginValidator(args.plugin_name, verbose=args.verbose)
    success = validator.validate()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
