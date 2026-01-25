"""SQL security validator for data explorer.

This module provides SQL validation to ensure only safe SELECT queries
are executed against the database.
"""

import re
from typing import List, Set, Tuple
import sqlparse
from sqlparse.sql import IdentifierList, Identifier
from sqlparse.tokens import Keyword, DML


class SqlValidationError(Exception):
    """SQL validation error."""
    pass


class SqlValidator:
    """SQL security validator.
    
    Validates SQL statements to ensure:
    - Only SELECT statements are allowed
    - No dangerous keywords (DROP, DELETE, INSERT, etc.)
    - Only whitelisted tables can be queried
    - No dangerous functions
    """
    
    # Forbidden keywords (case-insensitive)
    FORBIDDEN_KEYWORDS = {
        'DROP', 'DELETE', 'INSERT', 'UPDATE', 'TRUNCATE', 
        'ALTER', 'CREATE', 'GRANT', 'REVOKE', 'EXECUTE',
        'CALL', 'MERGE', 'REPLACE', 'SET', 'KILL',
        'ATTACH', 'DETACH', 'OPTIMIZE', 'SYSTEM', 'RENAME'
    }
    
    # Forbidden functions (ClickHouse specific)
    FORBIDDEN_FUNCTIONS = {
        'file', 'url', 'hdfs', 's3', 'mysql', 'postgresql',
        'input', 'remote', 'remoteSecure', 'jdbc',
        'odbc', 'sqlite', 'mongodb', 'redis'
    }
    
    def __init__(self, allowed_tables: Set[str]):
        """Initialize SQL validator.
        
        Args:
            allowed_tables: Set of table names that are allowed to be queried
        """
        self.allowed_tables = {t.lower() for t in allowed_tables}
    
    def validate(self, sql: str) -> Tuple[bool, str]:
        """Validate SQL statement.
        
        Args:
            sql: SQL statement to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # 1. Basic format check
            sql = sql.strip()
            if not sql:
                return False, "SQL 语句不能为空"
            
            # 2. Parse SQL
            parsed = sqlparse.parse(sql)
            if not parsed:
                return False, "无法解析 SQL 语句"
            
            stmt = parsed[0]
            
            # 3. Check statement type (only SELECT allowed)
            stmt_type = stmt.get_type()
            if stmt_type != 'SELECT':
                return False, f"只允许 SELECT 查询，不允许 {stmt_type or 'UNKNOWN'}"
            
            # 4. Check for forbidden keywords
            sql_upper = sql.upper()
            for keyword in self.FORBIDDEN_KEYWORDS:
                # Use word boundary matching to avoid false positives
                if re.search(rf'\b{keyword}\b', sql_upper):
                    return False, f"SQL 包含禁止的关键字: {keyword}"
            
            # 5. Check for forbidden functions
            for func in self.FORBIDDEN_FUNCTIONS:
                if re.search(rf'\b{func}\s*\(', sql, re.IGNORECASE):
                    return False, f"SQL 包含禁止的函数: {func}"
            
            # 6. Extract and check table names
            tables = self._extract_table_names(sql)
            for table in tables:
                table_lower = table.lower()
                if table_lower not in self.allowed_tables:
                    return False, f"不允许查询表: {table}"
            
            # 7. Check for dangerous content in comments
            if '--' in sql or '/*' in sql:
                # Remove comments and re-validate
                sql_no_comment = sqlparse.format(sql, strip_comments=True)
                if sql_no_comment.strip() != sql.strip():
                    return self.validate(sql_no_comment)
            
            # 8. Check for subqueries with INTO
            if re.search(r'\bINTO\b', sql_upper):
                return False, "SQL 包含禁止的 INTO 子句"
            
            return True, ""
            
        except Exception as e:
            return False, f"SQL 校验出错: {str(e)}"
    
    def _extract_table_names(self, sql: str) -> List[str]:
        """Extract table names from SQL.
        
        Args:
            sql: SQL statement
            
        Returns:
            List of table names
        """
        tables = []
        
        # Use regex to extract table names after FROM and JOIN
        # Pattern: FROM/JOIN table_name [AS alias]
        pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        
        for match in matches:
            # Handle database.table format
            if '.' in match:
                table = match.split('.')[-1]
            else:
                table = match
            tables.append(table)
        
        return list(set(tables))
    
    def add_limit_if_missing(self, sql: str, max_rows: int) -> str:
        """Add LIMIT clause if not present.
        
        Args:
            sql: SQL statement
            max_rows: Maximum rows to return
            
        Returns:
            SQL with LIMIT clause
        """
        sql_upper = sql.upper().strip()
        
        # Check if already has LIMIT
        if 'LIMIT' not in sql_upper:
            sql = f"{sql.rstrip().rstrip(';')} LIMIT {max_rows}"
        
        return sql
    
    def add_allowed_table(self, table_name: str):
        """Add a table to the allowed list.
        
        Args:
            table_name: Table name to add
        """
        self.allowed_tables.add(table_name.lower())
    
    def remove_allowed_table(self, table_name: str):
        """Remove a table from the allowed list.
        
        Args:
            table_name: Table name to remove
        """
        self.allowed_tables.discard(table_name.lower())
    
    def refresh_allowed_tables(self, tables: Set[str]):
        """Refresh the allowed tables list.
        
        Args:
            tables: New set of allowed tables
        """
        self.allowed_tables = {t.lower() for t in tables}
