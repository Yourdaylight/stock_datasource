# Design: Add Plugin Data Explorer

## Overview

本设计文档描述"数据浏览器"功能的技术实现方案，包括后端 API 设计、前端组件结构、SQL 安全校验机制等。

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (Vue 3)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  DataExplorerView.vue                                                       │
│  ├── TableListPanel.vue      (表列表面板)                                    │
│  ├── SimpleFilterForm.vue    (简单筛选表单)                                  │
│  ├── SqlEditorTabs.vue       (多 Tab SQL 编辑器)                            │
│  ├── QueryResultTable.vue    (查询结果表格)                                  │
│  ├── QueryHistory.vue        (查询历史面板)                                  │
│  └── TemplateManager.vue     (模板管理)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Backend API (FastAPI)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  /api/datamanage/                                                           │
│  ├── tables                  GET     (获取表列表)                            │
│  ├── tables/{name}/schema    GET     (获取表结构)                            │
│  ├── tables/{name}/query     POST    (简单筛选查询)                          │
│  ├── sql/execute             POST    (SQL 查询执行)                          │
│  ├── sql/export              POST    (导出查询结果)                          │
│  └── sql/templates           CRUD    (查询模板管理)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Service Layer                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  DataExplorerService                                                        │
│  ├── get_available_tables()          (从插件读取表信息)                      │
│  ├── get_table_schema()              (获取表结构详情)                        │
│  ├── execute_simple_query()          (执行简单筛选查询)                      │
│  ├── execute_sql_query()             (执行 SQL 查询)                        │
│  └── export_query_result()           (导出查询结果)                          │
│                                                                             │
│  SqlValidator                                                               │
│  ├── validate_sql()                  (SQL 安全校验)                          │
│  ├── extract_table_names()           (提取查询中的表名)                      │
│  └── check_allowed_tables()          (检查表名白名单)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Data Layer                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  ClickHouse Database                                                        │
│  ├── ods_daily, ods_daily_basic, ...  (插件数据表)                          │
│  └── user_sql_templates               (用户查询模板表)                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Backend Design

### 1. 数据模型 (schemas.py)

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class ColumnInfo(BaseModel):
    """列信息"""
    name: str
    data_type: str
    nullable: bool
    comment: Optional[str] = None

class TableInfo(BaseModel):
    """表信息"""
    plugin_name: str
    table_name: str
    category: str  # cn_stock, index, etf_fund, etc.
    columns: List[ColumnInfo]
    row_count: Optional[int] = None
    description: Optional[str] = None

class TableSchema(BaseModel):
    """表结构详情"""
    table_name: str
    columns: List[ColumnInfo]
    partition_by: Optional[str] = None
    order_by: Optional[List[str]] = None
    engine: Optional[str] = None
    comment: Optional[str] = None

class TableListResponse(BaseModel):
    """表列表响应"""
    tables: List[TableInfo]
    categories: List[Dict[str, str]]

# 简单筛选查询
class SimpleQueryRequest(BaseModel):
    """简单筛选查询请求"""
    filters: Dict[str, Any] = Field(default_factory=dict)
    sort_by: Optional[str] = None
    sort_order: str = Field(default="DESC", pattern="^(ASC|DESC)$")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=1000)

class DateRangeFilter(BaseModel):
    """日期范围筛选"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class CodeFilter(BaseModel):
    """代码筛选"""
    codes: Optional[List[str]] = None
    code_pattern: Optional[str] = None  # 支持模糊匹配

# SQL 查询
class SqlExecuteRequest(BaseModel):
    """SQL 查询请求"""
    sql: str = Field(..., max_length=10000)
    max_rows: int = Field(default=1000, ge=1, le=10000)
    timeout: int = Field(default=30, ge=1, le=300)

class SqlExecuteResponse(BaseModel):
    """SQL 查询响应"""
    columns: List[str]
    data: List[Dict[str, Any]]
    row_count: int
    total_count: Optional[int] = None
    execution_time_ms: int
    truncated: bool = False

# 导出
class ExportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"

class SqlExportRequest(BaseModel):
    """导出请求"""
    sql: str = Field(..., max_length=10000)
    format: ExportFormat = ExportFormat.CSV
    filename: Optional[str] = None

# 查询模板
class SqlTemplate(BaseModel):
    """查询模板"""
    id: Optional[int] = None
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    sql: str = Field(..., max_length=10000)
    category: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class SqlTemplateCreate(BaseModel):
    """创建查询模板"""
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    sql: str = Field(..., max_length=10000)
    category: Optional[str] = None
```

### 2. SQL 安全校验器 (sql_validator.py)

```python
import re
import sqlparse
from typing import List, Set, Tuple
from sqlparse.sql import IdentifierList, Identifier
from sqlparse.tokens import Keyword, DML

class SqlValidationError(Exception):
    """SQL 校验错误"""
    pass

class SqlValidator:
    """SQL 安全校验器"""
    
    # 禁止的关键字（不区分大小写）
    FORBIDDEN_KEYWORDS = {
        'DROP', 'DELETE', 'INSERT', 'UPDATE', 'TRUNCATE', 
        'ALTER', 'CREATE', 'GRANT', 'REVOKE', 'EXECUTE',
        'CALL', 'MERGE', 'REPLACE', 'SET', 'KILL'
    }
    
    # 禁止的函数
    FORBIDDEN_FUNCTIONS = {
        'file', 'url', 'hdfs', 's3', 'mysql', 'postgresql',
        'input', 'remote', 'remoteSecure'
    }
    
    def __init__(self, allowed_tables: Set[str]):
        """
        Args:
            allowed_tables: 允许查询的表名集合
        """
        self.allowed_tables = {t.lower() for t in allowed_tables}
    
    def validate(self, sql: str) -> Tuple[bool, str]:
        """
        校验 SQL 语句
        
        Returns:
            (is_valid, error_message)
        """
        try:
            # 1. 基础格式检查
            sql = sql.strip()
            if not sql:
                return False, "SQL 语句不能为空"
            
            # 2. 解析 SQL
            parsed = sqlparse.parse(sql)
            if not parsed:
                return False, "无法解析 SQL 语句"
            
            stmt = parsed[0]
            
            # 3. 检查语句类型（只允许 SELECT）
            stmt_type = stmt.get_type()
            if stmt_type != 'SELECT':
                return False, f"只允许 SELECT 查询，不允许 {stmt_type}"
            
            # 4. 检查禁止的关键字
            sql_upper = sql.upper()
            for keyword in self.FORBIDDEN_KEYWORDS:
                # 使用单词边界匹配，避免误判
                if re.search(rf'\b{keyword}\b', sql_upper):
                    return False, f"SQL 包含禁止的关键字: {keyword}"
            
            # 5. 检查禁止的函数
            for func in self.FORBIDDEN_FUNCTIONS:
                if re.search(rf'\b{func}\s*\(', sql, re.IGNORECASE):
                    return False, f"SQL 包含禁止的函数: {func}"
            
            # 6. 提取并检查表名
            tables = self._extract_table_names(sql)
            for table in tables:
                table_lower = table.lower()
                if table_lower not in self.allowed_tables:
                    return False, f"不允许查询表: {table}"
            
            # 7. 检查注释中的危险内容
            if '--' in sql or '/*' in sql:
                # 简单处理：去除注释后重新校验
                sql_no_comment = sqlparse.format(sql, strip_comments=True)
                if sql_no_comment.strip() != sql.strip():
                    # 有注释，对去除注释后的 SQL 重新校验
                    return self.validate(sql_no_comment)
            
            return True, ""
            
        except Exception as e:
            return False, f"SQL 校验出错: {str(e)}"
    
    def _extract_table_names(self, sql: str) -> List[str]:
        """从 SQL 中提取表名"""
        tables = []
        
        # 使用正则表达式提取 FROM 和 JOIN 后的表名
        # 匹配模式：FROM/JOIN 表名 [AS 别名]
        pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        
        for match in matches:
            # 处理 database.table 格式
            if '.' in match:
                table = match.split('.')[-1]
            else:
                table = match
            tables.append(table)
        
        return list(set(tables))
    
    def add_limit_if_missing(self, sql: str, max_rows: int) -> str:
        """如果 SQL 没有 LIMIT，添加 LIMIT"""
        sql_upper = sql.upper().strip()
        
        # 检查是否已有 LIMIT
        if 'LIMIT' not in sql_upper:
            sql = f"{sql.rstrip().rstrip(';')} LIMIT {max_rows}"
        
        return sql
```

### 3. API 路由 (router.py 新增部分)

```python
from fastapi import APIRouter, Query, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import io

# === 表信息 API ===

@router.get("/tables", response_model=TableListResponse)
async def get_available_tables(
    category: Optional[str] = Query(default=None, description="按分类筛选"),
    current_user: dict = Depends(get_current_user),
):
    """获取所有可查询的表列表"""
    return data_explorer_service.get_available_tables(category)


@router.get("/tables/{table_name}/schema", response_model=TableSchema)
async def get_table_schema(
    table_name: str,
    current_user: dict = Depends(get_current_user),
):
    """获取表结构详情"""
    schema = data_explorer_service.get_table_schema(table_name)
    if not schema:
        raise HTTPException(status_code=404, detail=f"表 {table_name} 不存在")
    return schema


# === 简单筛选查询 API ===

@router.post("/tables/{table_name}/query", response_model=SqlExecuteResponse)
async def query_table_data(
    table_name: str,
    request: SimpleQueryRequest,
    current_user: dict = Depends(get_current_user),
):
    """简单筛选查询"""
    return data_explorer_service.execute_simple_query(table_name, request)


# === SQL 查询 API ===

@router.post("/sql/execute", response_model=SqlExecuteResponse)
async def execute_sql(
    request: SqlExecuteRequest,
    current_user: dict = Depends(require_admin),  # 需要管理员权限
):
    """执行 SQL 查询"""
    return data_explorer_service.execute_sql_query(
        sql=request.sql,
        max_rows=request.max_rows,
        timeout=request.timeout
    )


@router.post("/sql/export")
async def export_sql_result(
    request: SqlExportRequest,
    current_user: dict = Depends(require_admin),
):
    """导出查询结果"""
    content, filename = data_explorer_service.export_query_result(
        sql=request.sql,
        format=request.format,
        filename=request.filename
    )
    
    media_type = "text/csv" if request.format == ExportFormat.CSV else \
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# === 查询模板 API ===

@router.get("/sql/templates", response_model=List[SqlTemplate])
async def get_sql_templates(
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """获取查询模板列表"""
    return data_explorer_service.get_templates(current_user["id"], category)


@router.post("/sql/templates", response_model=SqlTemplate)
async def create_sql_template(
    template: SqlTemplateCreate,
    current_user: dict = Depends(get_current_user),
):
    """创建查询模板"""
    return data_explorer_service.create_template(current_user["id"], template)


@router.delete("/sql/templates/{template_id}")
async def delete_sql_template(
    template_id: int,
    current_user: dict = Depends(get_current_user),
):
    """删除查询模板"""
    success = data_explorer_service.delete_template(current_user["id"], template_id)
    if not success:
        raise HTTPException(status_code=404, detail="模板不存在或无权删除")
    return {"message": "删除成功"}
```

### 4. 服务层 (service.py 新增部分)

```python
class DataExplorerService:
    """数据浏览服务"""
    
    def __init__(self):
        self._table_cache: Dict[str, TableInfo] = {}
        self._validator: Optional[SqlValidator] = None
    
    def _get_validator(self) -> SqlValidator:
        """获取 SQL 校验器（延迟初始化）"""
        if self._validator is None:
            tables = self.get_available_tables()
            allowed_tables = {t.table_name for t in tables.tables}
            self._validator = SqlValidator(allowed_tables)
        return self._validator
    
    def get_available_tables(self, category: Optional[str] = None) -> TableListResponse:
        """获取所有可查询的表列表"""
        tables = []
        
        # 从插件管理器获取所有插件
        for plugin in plugin_manager.get_all_plugins():
            try:
                schema = plugin.get_schema()
                config = plugin.get_config()
                
                table_name = schema.get("table_name")
                if not table_name:
                    continue
                
                # 获取表行数（缓存）
                row_count = self._get_table_row_count(table_name)
                
                # 解析列信息
                columns = [
                    ColumnInfo(
                        name=col["name"],
                        data_type=col["data_type"],
                        nullable=col.get("nullable", True),
                        comment=col.get("comment")
                    )
                    for col in schema.get("columns", [])
                ]
                
                # 确定分类
                plugin_category = self._get_plugin_category(plugin.name)
                
                if category and plugin_category != category:
                    continue
                
                tables.append(TableInfo(
                    plugin_name=plugin.name,
                    table_name=table_name,
                    category=plugin_category,
                    columns=columns,
                    row_count=row_count,
                    description=config.get("description")
                ))
            except Exception as e:
                logger.warning(f"读取插件 {plugin.name} 信息失败: {e}")
        
        # 分类信息
        categories = [
            {"key": "cn_stock", "label": "A股"},
            {"key": "index", "label": "指数"},
            {"key": "etf_fund", "label": "ETF基金"},
            {"key": "other", "label": "其他"}
        ]
        
        return TableListResponse(tables=tables, categories=categories)
    
    def execute_sql_query(
        self, 
        sql: str, 
        max_rows: int = 1000,
        timeout: int = 30
    ) -> SqlExecuteResponse:
        """执行 SQL 查询"""
        import time
        
        # 1. SQL 校验
        validator = self._get_validator()
        is_valid, error = validator.validate(sql)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
        
        # 2. 添加 LIMIT
        sql = validator.add_limit_if_missing(sql, max_rows)
        
        # 3. 执行查询
        start_time = time.time()
        try:
            result = db_client.execute_query(
                sql, 
                settings={'max_execution_time': timeout}
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"查询执行失败: {str(e)}")
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # 4. 转换结果
        columns = list(result.columns)
        data = result.to_dict(orient='records')
        row_count = len(data)
        
        return SqlExecuteResponse(
            columns=columns,
            data=data,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            truncated=row_count >= max_rows
        )
    
    def export_query_result(
        self,
        sql: str,
        format: ExportFormat,
        filename: Optional[str] = None
    ) -> Tuple[bytes, str]:
        """导出查询结果"""
        import pandas as pd
        from datetime import datetime
        
        # 执行查询（限制 10000 行）
        result = self.execute_sql_query(sql, max_rows=10000)
        df = pd.DataFrame(result.data)
        
        # 生成文件名
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"query_result_{timestamp}"
        
        # 导出
        if format == ExportFormat.CSV:
            content = df.to_csv(index=False).encode('utf-8-sig')  # 支持中文
            filename = f"{filename}.csv"
        else:  # Excel
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine='openpyxl')
            content = buffer.getvalue()
            filename = f"{filename}.xlsx"
        
        return content, filename
```

## Frontend Design

### 1. 路由配置

数据浏览器作为数据管理的二级菜单：

```typescript
// router/index.ts
{
  path: '/datamanage',
  name: 'DataManage',
  component: () => import('@/views/datamanage/DataManageLayout.vue'),
  meta: { title: '数据管理', icon: 'data' },
  children: [
    {
      path: '',
      name: 'DataManageOverview',
      component: () => import('@/views/datamanage/DataManageView.vue'),
      meta: { title: '数据概览' }
    },
    {
      path: 'explorer',
      name: 'DataExplorer',
      component: () => import('@/views/datamanage/DataExplorerView.vue'),
      meta: { title: '数据浏览器', requiresAuth: true }
    }
  ]
}
```

### 2. 主页面结构

```vue
<!-- views/datamanage/DataExplorerView.vue -->
<template>
  <div class="data-explorer">
    <!-- 左侧：表列表 -->
    <div class="table-list-panel">
      <TableListPanel 
        v-model:selected="selectedTable"
        @select="handleTableSelect"
      />
    </div>
    
    <!-- 右侧：查询区域 -->
    <div class="query-panel">
      <!-- 模式切换 -->
      <t-tabs v-model="queryMode">
        <t-tab-panel value="simple" label="简单筛选" />
        <t-tab-panel value="sql" label="SQL 查询" />
      </t-tabs>
      
      <!-- 简单筛选模式 -->
      <SimpleFilterForm 
        v-if="queryMode === 'simple'"
        :table="selectedTable"
        @query="handleSimpleQuery"
      />
      
      <!-- SQL 查询模式 - 多 Tab -->
      <SqlEditorTabs 
        v-else
        v-model:tabs="sqlTabs"
        v-model:activeTab="activeTabId"
        :tables="allTables"
        @execute="handleSqlExecute"
      />
      
      <!-- 查询历史（侧边栏或下拉） -->
      <QueryHistory 
        v-if="showHistory"
        @select="loadFromHistory"
      />
      
      <!-- 查询结果 -->
      <QueryResultTable 
        :result="queryResult"
        :loading="loading"
        @export="handleExport"
      />
    </div>
  </div>
</template>
```

### 3. 多 Tab SQL 编辑器组件

```vue
<!-- components/SqlEditorTabs.vue -->
<template>
  <div class="sql-editor-tabs">
    <!-- Tab 栏 -->
    <div class="tab-bar">
      <div 
        v-for="tab in tabs" 
        :key="tab.id" 
        :class="['tab-item', { active: tab.id === activeTab }]"
        @click="activeTab = tab.id"
      >
        <span class="tab-title">{{ tab.title || '未命名查询' }}</span>
        <t-icon name="close" @click.stop="closeTab(tab.id)" />
      </div>
      <t-button variant="text" @click="addTab">
        <t-icon name="add" />
      </t-button>
    </div>
    
    <!-- 当前 Tab 的编辑器 -->
    <div class="editor-wrapper">
      <div class="editor-toolbar">
        <t-button theme="primary" @click="handleExecute">
          <template #icon><t-icon name="play" /></template>
          运行 (Ctrl+Enter)
        </t-button>
        <t-button @click="handleFormat">格式化</t-button>
        <t-button @click="showTemplateDialog = true">保存模板</t-button>
        <t-dropdown :options="templateOptions" @click="loadTemplate">
          <t-button>加载模板</t-button>
        </t-dropdown>
        <t-button variant="text" @click="toggleHistory">
          <t-icon name="history" /> 历史
        </t-button>
      </div>
      
      <div class="editor-container" ref="editorContainer">
        <!-- Monaco Editor -->
      </div>
    </div>
    
    <!-- 保存模板对话框 -->
    <t-dialog v-model:visible="showTemplateDialog" header="保存查询模板">
      <t-form>
        <t-form-item label="模板名称">
          <t-input v-model="templateName" />
        </t-form-item>
        <t-form-item label="描述">
          <t-textarea v-model="templateDesc" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import * as monaco from 'monaco-editor'
import { useQueryHistory } from '@/composables/useQueryHistory'

interface SqlTab {
  id: string
  title: string
  sql: string
  result?: SqlExecuteResponse
}

const props = defineProps<{
  tabs: SqlTab[]
  activeTab: string
  tables: TableInfo[]
}>()

const emit = defineEmits<{
  (e: 'update:tabs', value: SqlTab[]): void
  (e: 'update:activeTab', value: string): void
  (e: 'execute', sql: string, tabId: string): void
}>()

const { addToHistory } = useQueryHistory()

// 编辑器实例映射
const editorInstances = new Map<string, monaco.editor.IStandaloneCodeEditor>()

const addTab = () => {
  const newTab: SqlTab = {
    id: `tab_${Date.now()}`,
    title: `查询 ${props.tabs.length + 1}`,
    sql: ''
  }
  emit('update:tabs', [...props.tabs, newTab])
  emit('update:activeTab', newTab.id)
}

const closeTab = (tabId: string) => {
  if (props.tabs.length <= 1) return
  
  const newTabs = props.tabs.filter(t => t.id !== tabId)
  emit('update:tabs', newTabs)
  
  if (props.activeTab === tabId) {
    emit('update:activeTab', newTabs[0].id)
  }
  
  // 销毁编辑器实例
  editorInstances.get(tabId)?.dispose()
  editorInstances.delete(tabId)
}

const handleExecute = () => {
  const currentTab = props.tabs.find(t => t.id === props.activeTab)
  if (currentTab?.sql.trim()) {
    // 添加到历史记录
    addToHistory({
      sql: currentTab.sql,
      executedAt: new Date().toISOString()
    })
    emit('execute', currentTab.sql, currentTab.id)
  }
}

// 快捷键绑定
const setupEditor = (container: HTMLElement, tabId: string) => {
  const editor = monaco.editor.create(container, {
    value: props.tabs.find(t => t.id === tabId)?.sql || '',
    language: 'sql',
    theme: 'vs-dark',
    minimap: { enabled: false },
    fontSize: 14,
    lineNumbers: 'on',
    automaticLayout: true
  })
  
  // Ctrl+Enter 执行
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, handleExecute)
  
  // 值变化同步
  editor.onDidChangeModelContent(() => {
    const newTabs = props.tabs.map(t => 
      t.id === tabId ? { ...t, sql: editor.getValue() } : t
    )
    emit('update:tabs', newTabs)
  })
  
  editorInstances.set(tabId, editor)
  return editor
}
</script>

<style scoped>
.tab-bar {
  display: flex;
  align-items: center;
  background: var(--td-bg-color-container);
  border-bottom: 1px solid var(--td-component-border);
  padding: 0 8px;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  
  &.active {
    border-bottom-color: var(--td-brand-color);
    background: var(--td-bg-color-secondarycontainer);
  }
  
  &:hover {
    background: var(--td-bg-color-secondarycontainer);
  }
}
</style>
```

### 4. 查询历史记录 Composable

```typescript
// composables/useQueryHistory.ts
import { ref, computed } from 'vue'

const STORAGE_KEY = 'sql_query_history'
const MAX_HISTORY_SIZE = 100

export interface QueryHistoryItem {
  id: string
  sql: string
  tableName?: string
  executedAt: string
  executionTime?: number
  rowCount?: number
}

export function useQueryHistory() {
  // 从 localStorage 加载历史
  const loadHistory = (): QueryHistoryItem[] => {
    try {
      const data = localStorage.getItem(STORAGE_KEY)
      return data ? JSON.parse(data) : []
    } catch {
      return []
    }
  }
  
  const history = ref<QueryHistoryItem[]>(loadHistory())
  
  // 保存到 localStorage
  const saveHistory = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history.value))
    } catch (e) {
      console.warn('Failed to save query history:', e)
    }
  }
  
  // 添加历史记录
  const addToHistory = (item: Omit<QueryHistoryItem, 'id'>) => {
    const newItem: QueryHistoryItem = {
      ...item,
      id: `history_${Date.now()}`
    }
    
    // 检查是否重复（相同 SQL）
    const existingIndex = history.value.findIndex(h => h.sql.trim() === item.sql.trim())
    if (existingIndex >= 0) {
      // 移除旧的，添加新的到顶部
      history.value.splice(existingIndex, 1)
    }
    
    // 添加到顶部
    history.value.unshift(newItem)
    
    // 限制大小
    if (history.value.length > MAX_HISTORY_SIZE) {
      history.value = history.value.slice(0, MAX_HISTORY_SIZE)
    }
    
    saveHistory()
  }
  
  // 删除单条记录
  const removeFromHistory = (id: string) => {
    history.value = history.value.filter(h => h.id !== id)
    saveHistory()
  }
  
  // 清空历史
  const clearHistory = () => {
    history.value = []
    localStorage.removeItem(STORAGE_KEY)
  }
  
  // 搜索历史
  const searchHistory = (keyword: string) => {
    if (!keyword.trim()) return history.value
    const lower = keyword.toLowerCase()
    return history.value.filter(h => 
      h.sql.toLowerCase().includes(lower) ||
      h.tableName?.toLowerCase().includes(lower)
    )
  }
  
  return {
    history: computed(() => history.value),
    addToHistory,
    removeFromHistory,
    clearHistory,
    searchHistory
  }
}
```

### 5. API 接口

```typescript
// api/datamanage.ts 新增

export interface TableInfo {
  plugin_name: string
  table_name: string
  category: string
  columns: ColumnInfo[]
  row_count?: number
  description?: string
}

export interface ColumnInfo {
  name: string
  data_type: string
  nullable: boolean
  comment?: string
}

export interface SqlExecuteRequest {
  sql: string
  max_rows?: number
  timeout?: number
}

export interface SqlExecuteResponse {
  columns: string[]
  data: Record<string, any>[]
  row_count: number
  total_count?: number
  execution_time_ms: number
  truncated: boolean
}

// API 方法
export const dataExplorerApi = {
  // 获取表列表
  getTables(category?: string): Promise<{ tables: TableInfo[], categories: any[] }> {
    const params = category ? `?category=${category}` : ''
    return request.get(`/api/datamanage/tables${params}`)
  },
  
  // 获取表结构
  getTableSchema(tableName: string): Promise<TableSchema> {
    return request.get(`/api/datamanage/tables/${tableName}/schema`)
  },
  
  // 简单查询
  queryTable(tableName: string, params: SimpleQueryRequest): Promise<SqlExecuteResponse> {
    return request.post(`/api/datamanage/tables/${tableName}/query`, params)
  },
  
  // SQL 查询
  executeSql(params: SqlExecuteRequest): Promise<SqlExecuteResponse> {
    return request.post('/api/datamanage/sql/execute', params)
  },
  
  // 导出
  exportSql(sql: string, format: 'csv' | 'xlsx'): Promise<Blob> {
    return request.post('/api/datamanage/sql/export', { sql, format }, {
      responseType: 'blob'
    })
  },
  
  // 查询模板
  getTemplates(category?: string): Promise<SqlTemplate[]> {
    return request.get('/api/datamanage/sql/templates', { params: { category } })
  },
  
  createTemplate(template: SqlTemplateCreate): Promise<SqlTemplate> {
    return request.post('/api/datamanage/sql/templates', template)
  },
  
  deleteTemplate(id: number): Promise<void> {
    return request.delete(`/api/datamanage/sql/templates/${id}`)
  }
}
```

## Database Schema

### 查询模板表

```sql
CREATE TABLE IF NOT EXISTS user_sql_templates (
    id UInt64,
    user_id UInt64,
    name String,
    description Nullable(String),
    sql String,
    category Nullable(String),
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, id);
```

## Security Considerations

### 1. SQL 注入防护
- 使用 `sqlparse` 解析 SQL 结构
- 白名单校验表名
- 黑名单校验危险关键字和函数

### 2. 资源限制
- 查询超时：默认 30 秒，最大 300 秒
- 返回行数：默认 1000 行，最大 10000 行
- 导出行数：最大 10000 行

### 3. 权限控制
- 简单筛选：所有登录用户
- SQL 查询：仅管理员

## Performance Considerations

### 1. 表信息缓存
- 表列表信息缓存 5 分钟
- 表行数统计缓存 1 小时

### 2. 查询优化
- 强制添加 LIMIT 防止全表扫描
- 建议用户添加日期筛选条件

### 3. 导出优化
- 使用流式导出避免内存溢出
- 大数据量时建议分批导出

## Testing Strategy

### 单元测试
- SQL 校验器测试（各种 SQL 注入场景）
- API 端点测试

### 集成测试
- 端到端查询流程测试
- 导出功能测试

### 性能测试
- 大表查询性能
- 并发查询测试
