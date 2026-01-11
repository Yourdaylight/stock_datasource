#!/usr/bin/env python3
"""
初始化持仓管理相关数据表
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)

def init_portfolio_tables():
    """初始化持仓管理相关数据表"""
    
    # 读取SQL文件
    sql_files = [
        project_root / "src/stock_datasource/modules/portfolio/schema.sql",
        project_root / "src/stock_datasource/sql/portfolio_tables.sql"
    ]
    
    try:
        for sql_file in sql_files:
            if not sql_file.exists():
                logger.warning(f"SQL文件不存在: {sql_file}")
                continue
                
            logger.info(f"执行SQL文件: {sql_file}")
            
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # 分割SQL语句并执行
            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
            
            for statement in statements:
                if statement.upper().startswith(('CREATE', 'ALTER', 'DROP')):
                    try:
                        db_client.execute(statement)
                        logger.info(f"成功执行: {statement[:50]}...")
                    except Exception as e:
                        logger.error(f"执行SQL失败: {statement[:50]}... 错误: {e}")
        
        logger.info("持仓管理数据表初始化完成")
        
    except Exception as e:
        logger.error(f"初始化数据表失败: {e}")
        raise

def verify_tables():
    """验证数据表是否创建成功"""
    
    expected_tables = [
        'user_positions',
        'portfolio_analysis', 
        'user_portfolio_analysis',
        'daily_analysis_reports',
        'position_history',
        'position_alerts',
        'technical_indicators',
        'portfolio_risk_metrics'
    ]
    
    try:
        # 查询现有表
        result = db_client.execute_query("SHOW TABLES")
        existing_tables = set(result['name'].tolist() if not result.empty else [])
        
        logger.info(f"现有数据表: {existing_tables}")
        
        # 检查必需的表
        missing_tables = []
        for table in expected_tables:
            if table not in existing_tables:
                missing_tables.append(table)
        
        if missing_tables:
            logger.warning(f"缺少数据表: {missing_tables}")
        else:
            logger.info("所有必需的数据表都已创建")
            
        return len(missing_tables) == 0
        
    except Exception as e:
        logger.error(f"验证数据表失败: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        logger.info("开始初始化持仓管理数据表...")
        init_portfolio_tables()
        
        logger.info("验证数据表创建结果...")
        if verify_tables():
            logger.info("✅ 数据表初始化成功")
        else:
            logger.error("❌ 数据表初始化不完整")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        sys.exit(1)