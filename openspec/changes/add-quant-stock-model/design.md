# Design: add-quant-stock-model

## 架构概述

量化选股模型采用**管线架构（Pipeline Architecture）**，四大引擎按顺序处理数据，每个引擎独立可测试、可替换。整体嵌入现有模块体系（`modules/quant/`），通过 Agent 层对外暴露 AI 交互能力。

**核心架构约束**：
1. **纯本地数据计算**：所有引擎仅从 ClickHouse 读取本地已有数据，**禁止在计算过程中调用任何 TuShare/AKShare 远程插件**
2. **数据就绪检查前置**：每个引擎执行前先通过 `DataReadinessChecker` 检查数据完整性，缺失则中断并返回结构化缺失报告
3. **前端全链路可视化**：Pipeline 每步的输入/输出/状态/关键数据都在前端展示，用户可看到每条规则的执行详情
4. **前端一键补数据**：数据缺失时，前端展示缺失详情并提供"一键补数据"按钮，调用现有 `batchTriggerSync` API 触发数据插件

## 系统架构

```
用户 ──────── 前端 (Vue3 + TDesign) ───────── API (FastAPI)
              │                                  │
              │  ┌─────────────────────────────┐  │
              │  │   量化模型 Pipeline 可视化    │  │
              │  │  ┌───┐ ┌───┐ ┌───┐ ┌───┐  │  │
              │  │  │初筛│→│核心│→│深度│→│信号│  │  │
              │  │  │ ✓ │ │ ⏳│ │ - │ │ - │  │  │
              │  │  └───┘ └───┘ └───┘ └───┘  │  │
              │  │                             │  │
              │  │  ⚠️ 缺失数据提示面板         │  │
              │  │  [一键补数据] 按钮           │  │
              │  │                             │  │
              │  │  📊 每步关键信息展示区       │  │
              │  └─────────────────────────────┘  │
              │                                   │
              └───────────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │     QuantRouter       │
                    │    /api/quant/*       │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │     QuantService      │
                    │    (Pipeline编排)      │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  DataReadinessChecker  │
                    │  (数据就绪检查层)       │
                    │                       │
                    │  每个引擎执行前:       │
                    │  1. 检查所需表是否存在  │
                    │  2. 检查日期范围完整性  │
                    │  3. 生成缺失报告       │
                    │  4. 缺失→返回报告      │
                    │  5. 就绪→继续执行      │
                    └───────────┬───────────┘
                                │ (数据就绪才继续)
        ┌───────────┬───────────┼───────────┬───────────┐
        │           │           │           │           │
   ┌────▼────┐ ┌────▼────┐ ┌───▼────┐ ┌────▼────┐     │
   │Screening│ │CorePool │ │  Deep  │ │ Signal  │     │
   │ Engine  │ │ Builder │ │Analyzer│ │Generator│     │
   └────┬────┘ └────┬────┘ └───┬────┘ └────┬────┘     │
        │           │          │            │          │
        └───────────┴──────┬───┴────────────┘          │
                           │                           │
                   ┌───────▼────────┐                  │
                   │  ClickHouse DB │ ←── 仅读取 ──────┘
                   │  (本地已有数据) │
                   └───────┬────────┘
                           │
          (数据由插件预先写入，计算过程不调用插件)
          (缺失时返回报告 → 前端展示 → 用户一键触发补数据)
                           │
      ┌────────────────────┼────────────────────┐
      │                    │                    │
 ┌────▼─────┐   ┌─────────▼──┐   ┌─────────────▼─┐
 │ Finance  │   │   Daily /  │   │   Index /     │
 │ Plugins  │   │ DailyBasic │   │  AdjFactor    │
 │(income/  │   │  Plugins   │   │   Plugins     │
 │balance/  │   └────────────┘   └───────────────┘
 │cashflow) │
 └──────────┘
 (仅通过前端"一键补数据"按钮触发)
```

### 数据流方向

```
用户在前端操作 → 调用 API → DataReadinessChecker 检查数据
  │
  ├── 数据完整 → 引擎执行计算(纯 ClickHouse 查询)
  │              → 返回计算结果 + 每步关键信息
  │              → 前端展示结果详情
  │
  └── 数据缺失 → 返回 MissingDataReport (结构化)
                → 前端展示缺失详情面板:
                  - 缺失哪些表
                  - 缺失哪些日期范围
                  - 影响哪些计算步骤
                  - 需要触发哪些插件
                → 用户点击"一键补数据"按钮
                → 前端调用 batchTriggerSync API
                → TuShare 插件执行数据拉取
                → 数据入库后用户重新触发计算
```

## 模块设计

### 1. 文件结构

```
src/stock_datasource/
├── modules/quant/
│   ├── __init__.py                    # 模块注册
│   ├── router.py                      # FastAPI 路由 (/api/quant/*)
│   ├── schemas.py                     # Pydantic 数据模型
│   ├── service.py                     # 核心服务编排 (Pipeline)
│   ├── data_readiness.py              # ★ 数据就绪检查器
│   ├── screening_engine.py            # ① 全市场初筛引擎
│   ├── core_pool_builder.py           # ② 核心池构建
│   ├── deep_analyzer.py               # ③ 深度分析引擎
│   ├── signal_generator.py            # ④ 交易信号生成
│   ├── rps_calculator.py              # RPS 指标计算
│   ├── benford_checker.py             # 本福德定律检验
│   └── factor_scorer.py              # 多因子打分模型
├── agents/
│   └── quant_agent.py                 # 量化模型 Agent
└── strategies/builtin/
    └── quant_ma_strategy.py           # 量化均线交叉策略

frontend/src/
├── views/quant/
│   ├── QuantView.vue                  # ★ 量化模型主页(Pipeline概览)
│   ├── QuantScreeningView.vue         # 初筛结果+规则配置
│   ├── QuantPoolView.vue              # 核心池+补充池
│   ├── QuantRpsView.vue               # RPS排名
│   ├── QuantAnalysisView.vue          # 深度分析仪表盘
│   ├── QuantSignalsView.vue           # 交易信号+风控
│   ├── QuantConfigView.vue            # 模型配置
│   └── components/
│       ├── PipelineProgress.vue       # ★ Pipeline 四阶段进度条
│       ├── DataReadinessPanel.vue     # ★ 数据就绪检查+一键补数据
│       ├── ScreeningRuleStats.vue     # ★ 每条规则命中/未命中统计
│       ├── ScreeningRejectTable.vue   # ★ 被剔除股票列表+原因
│       ├── FactorScoreDistribution.vue # ★ 因子得分分布图
│       ├── FactorScoreRadar.vue       # 因子雷达图
│       ├── PoolChangeLog.vue          # ★ 入池/出池变动日志
│       ├── RpsHeatmap.vue             # RPS热力图
│       ├── TechIndicatorChart.vue     # 技术指标图表
│       ├── AiAnalysisCard.vue         # AI分析卡片
│       ├── SignalList.vue             # 信号列表
│       ├── RiskStatusPanel.vue        # 风控状态面板
│       └── PositionSuggestion.vue     # 仓位建议
├── api/
│   └── quant.ts                       # 量化模型 API 客户端
└── stores/
    └── quant.ts                       # 量化模型状态管理
```

### 2. 数据就绪检查器设计 (DataReadinessChecker) ★核心新增

```python
class DataRequirement(BaseModel):
    """单个数据需求"""
    plugin_name: str           # 对应的数据插件名称
    table_name: str            # ClickHouse 表名
    required_columns: list[str] = []  # 必需列
    date_column: str = "trade_date"   # 日期列名
    min_date: Optional[str] = None    # 最早需要的日期
    max_date: Optional[str] = None    # 最晚需要的日期
    min_records: int = 0              # 最少记录数
    description: str = ""             # 数据用途说明（前端展示）

class DataReadinessResult(BaseModel):
    """数据就绪检查结果"""
    is_ready: bool                     # 是否所有数据就绪
    checked_at: datetime
    requirements: list[DataRequirementStatus]  # 每项需求的状态
    missing_summary: Optional[MissingDataSummary] = None  # 缺失汇总

class DataRequirementStatus(BaseModel):
    """单项数据需求状态"""
    requirement: DataRequirement
    status: Literal["ready", "missing_table", "missing_dates", "insufficient_data"]
    existing_date_range: Optional[tuple[str, str]] = None  # 已有日期范围
    missing_dates: list[str] = []     # 缺失的日期列表
    record_count: int = 0             # 已有记录数
    suggested_plugins: list[str] = [] # 建议触发的插件列表
    suggested_task_type: str = "incremental"  # 建议的同步方式

class MissingDataSummary(BaseModel):
    """缺失数据汇总（供前端展示）"""
    total_requirements: int
    ready_count: int
    missing_count: int
    affected_engines: list[str]       # 受影响的引擎
    plugins_to_trigger: list[PluginTriggerInfo]  # 需要触发的插件
    estimated_sync_time: str          # 预计同步时长

class PluginTriggerInfo(BaseModel):
    """需要触发的插件信息（前端展示用）"""
    plugin_name: str
    display_name: str
    table_name: str
    missing_dates: list[str]
    task_type: str                    # full / incremental / backfill
    description: str                  # 为什么需要这个数据

class DataReadinessChecker:
    """
    数据就绪检查器
    - 每个引擎执行前调用，检查所需数据是否在 ClickHouse 中就绪
    - 不调用任何远程数据插件
    - 返回结构化缺失报告，供前端展示和一键补数据
    """

    # 各引擎的数据需求声明
    SCREENING_REQUIREMENTS = [
        DataRequirement(
            plugin_name="tushare_fina_indicator",
            table_name="fact_fina_indicator",
            required_columns=["roe", "revenue_yoy", "netprofit_yoy"],
            description="财务指标数据(ROE/营收增速/净利润增速)，用于传统指标筛选"
        ),
        DataRequirement(
            plugin_name="tushare_income",
            table_name="fact_income",
            required_columns=["total_revenue", "n_income", "sell_exp", "admin_exp", "rd_exp"],
            description="利润表数据(营收/净利/费用拆项)，用于自定义指标筛选"
        ),
        DataRequirement(
            plugin_name="tushare_balancesheet",
            table_name="fact_balancesheet",
            required_columns=["accounts_receiv"],
            description="资产负债表(应收账款)，用于应收营收联动分析"
        ),
        DataRequirement(
            plugin_name="tushare_cashflow",
            table_name="fact_cashflow",
            required_columns=["n_cashflow_act"],
            description="现金流量表(经营现金流)，用于现金流同步率检查"
        ),
    ]

    CORE_POOL_REQUIREMENTS = [
        DataRequirement(
            plugin_name="tushare_daily_basic",
            table_name="fact_daily_basic",
            required_columns=["pe", "pb", "total_mv"],
            description="每日基本面指标(PE/PB/市值)，用于估值因子计算"
        ),
        DataRequirement(
            plugin_name="tushare_daily",
            table_name="fact_daily_bar",
            required_columns=["close", "pct_chg"],
            description="日线行情(收盘价/涨跌幅)，用于动量因子和RPS计算"
        ),
        DataRequirement(
            plugin_name="tushare_adj_factor",
            table_name="fact_adj_factor",
            required_columns=["adj_factor"],
            description="复权因子，用于前复权价格计算"
        ),
    ]

    SIGNAL_REQUIREMENTS = [
        DataRequirement(
            plugin_name="tushare_index_daily",
            table_name="fact_index_daily",
            required_columns=["close"],
            description="指数日线(沪深300)，用于市场风控(MA250)"
        ),
    ]

    async def check_screening_readiness(self) -> DataReadinessResult:
        """检查初筛引擎所需数据"""

    async def check_core_pool_readiness(self) -> DataReadinessResult:
        """检查核心池构建所需数据"""

    async def check_signal_readiness(self) -> DataReadinessResult:
        """检查信号生成所需数据"""

    async def check_full_pipeline_readiness(self) -> dict[str, DataReadinessResult]:
        """检查完整Pipeline所有阶段的数据就绪状态"""

    async def _check_table_exists(self, table_name: str) -> bool:
        """检查 ClickHouse 表是否存在"""

    async def _check_date_coverage(self, table_name: str, date_column: str,
                                     min_date: str, max_date: str) -> tuple[list[str], list[str]]:
        """检查日期覆盖范围，返回 (已有日期, 缺失日期)"""

    async def _check_record_count(self, table_name: str) -> int:
        """检查表记录数"""
```

### 3. 数据库设计（ClickHouse）

```sql
-- 初筛结果表
CREATE TABLE quant_screening_result (
    run_date Date,
    ts_code String,
    stock_name String,
    pass_traditional UInt8,        -- 传统指标通过
    pass_custom UInt8,             -- 自定义指标通过
    pass_benford UInt8,            -- 本福德检验通过
    overall_pass UInt8,            -- 最终是否通过
    reject_reasons Array(String),  -- 剔除原因
    -- ★ 每条规则的详细结果（供前端展示）
    rule_details String,           -- JSON: [{rule_name, passed, value, threshold, reason}]
    roe_3y_avg Float64,
    revenue_growth_2y Array(Float64),
    net_profit Float64,
    cashflow_sync_ratio Float64,
    expense_anomaly_score Float64,
    receivable_revenue_gap Float64,
    benford_chi2 Float64,
    benford_p_value Float64,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (run_date, ts_code);

-- ★ 初筛运行统计表（供前端Pipeline展示）
CREATE TABLE quant_screening_run_stats (
    run_date Date,
    run_id String,                  -- 运行ID
    total_stocks UInt32,            -- 参与筛选的总数
    passed_count UInt32,            -- 通过数
    rejected_count UInt32,          -- 剔除数
    -- 每条规则的统计
    rule_stats String,              -- JSON: [{rule_name, hit_count, miss_count, skip_count}]
    -- 数据就绪检查结果
    data_readiness String,          -- JSON: DataReadinessResult
    execution_time_ms UInt64,       -- 执行耗时
    status String,                  -- 'success' | 'partial' | 'data_missing'
    error_message String DEFAULT '',
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (run_date, run_id);

-- RPS排名表
CREATE TABLE quant_rps_rank (
    calc_date Date,
    ts_code String,
    stock_name String,
    rps_250 Float64,       -- 250日RPS
    rps_120 Float64,       -- 120日RPS
    rps_60 Float64,        -- 60日RPS
    price_chg_250 Float64, -- 250日涨幅
    price_chg_120 Float64, -- 120日涨幅
    price_chg_60 Float64,  -- 60日涨幅
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (calc_date, ts_code);

-- 核心池表
CREATE TABLE quant_core_pool (
    update_date Date,
    pool_type String,           -- 'core' | 'rps_supplement' | 'watchlist'
    ts_code String,
    stock_name String,
    quality_score Float64,      -- 质量因子得分
    growth_score Float64,       -- 成长因子得分
    value_score Float64,        -- 估值因子得分
    momentum_score Float64,     -- 动量因子得分
    total_score Float64,        -- 综合得分
    -- ★ 因子明细（供前端展示）
    factor_details String,      -- JSON: {roe, gross_margin, debt_ratio, rev_growth, ...}
    rank UInt32,
    rps_250 Float64,
    entry_date Date,            -- 入池日期
    exit_date Nullable(Date),   -- 出池日期
    change_type String DEFAULT '', -- ★ 'new_entry' | 'exit' | 'rank_change' | ''
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (update_date, pool_type, ts_code);

-- 交易信号表
CREATE TABLE quant_trading_signal (
    signal_date Date,
    ts_code String,
    stock_name String,
    signal_type String,         -- 'buy' | 'sell' | 'add' | 'reduce'
    signal_source String,       -- 'ma_crossover' | 'stop_loss' | 'stop_profit' | 'risk_control'
    price Float64,
    target_position Float64,    -- 目标仓位比例
    confidence Float64,
    reason String,
    pool_type String,           -- 所属池
    ma25 Float64,
    ma120 Float64,
    -- ★ 信号触发的详细上下文（供前端展示）
    signal_context String,      -- JSON: {prev_ma25, prev_ma120, crossover_date, ...}
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (signal_date, ts_code)
TTL signal_date + INTERVAL 365 DAY;

-- 深度分析结果表
CREATE TABLE quant_deep_analysis (
    analysis_date Date,
    ts_code String,
    stock_name String,
    tech_score Float64,          -- 技术面得分
    mgmt_discussion_score Float64, -- 管理层讨论可信度
    prospect_score Float64,       -- 前景乐观度
    key_findings Array(String),
    risk_factors Array(String),
    verification_points Array(String), -- 未来验证点
    ai_summary String,
    -- ★ 技术指标快照（供前端图表展示）
    tech_snapshot String,        -- JSON: {ma25, ma120, macd, rsi, volume_ratio, ...}
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (analysis_date, ts_code);

-- 量化模型配置表
CREATE TABLE quant_model_config (
    config_id String,
    config_name String,
    config_type String,          -- 'screening_rules' | 'factor_weights' | 'signal_params' | 'risk_params'
    config_data String,          -- JSON配置
    is_active UInt8 DEFAULT 1,
    user_id String DEFAULT '',
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (config_id);

-- ★ Pipeline 运行记录表（供前端Pipeline进度展示）
CREATE TABLE quant_pipeline_run (
    run_id String,
    run_date Date,
    pipeline_type String,        -- 'full' | 'screening_only' | 'signal_only' | ...
    stages String,               -- JSON: [{name, status, start_time, end_time, result_summary, data_readiness}]
    overall_status String,       -- 'running' | 'completed' | 'data_missing' | 'error'
    triggered_by String,         -- 'manual' | 'scheduler' | 'agent'
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (run_date, run_id);
```

### 4. 核心引擎设计

#### 4.1 全市场初筛引擎 (ScreeningEngine)

```python
class ScreeningRule(BaseModel):
    """可配置的筛选规则"""
    name: str
    category: Literal["traditional", "custom", "benford"]
    enabled: bool = True
    params: dict = {}
    is_hard_reject: bool = True  # True=直接剔除, False=标记警告

class RuleExecutionDetail(BaseModel):
    """★ 单条规则执行详情（前端展示用）"""
    rule_name: str
    category: str
    enabled: bool
    total_checked: int
    passed_count: int
    rejected_count: int
    skipped_count: int         # 数据不足跳过
    execution_time_ms: int
    threshold: str             # 阈值说明
    sample_rejects: list[dict] # 示例被剔除的股票(前5个)

class ScreeningResult(BaseModel):
    """★ 初筛结果（前端展示用）"""
    run_date: str
    total_stocks: int
    passed_stocks: list[dict]      # 通过的股票列表
    rejected_stocks: list[dict]    # 被剔除的股票列表
    rule_details: list[RuleExecutionDetail]  # ★ 每条规则的执行详情
    data_readiness: DataReadinessResult      # ★ 数据就绪状态
    execution_summary: dict        # {total_time_ms, rules_applied, ...}

class ScreeningEngine:
    """
    全市场初筛引擎
    - ★ 仅从 ClickHouse 读取全市场财务数据，不调用任何远程插件
    - 执行前通过 DataReadinessChecker 检查数据就绪状态
    - 应用可配置规则链
    - ★ 输出每条规则的详细执行统计，供前端逐条展示
    """
    def __init__(self, rules: list[ScreeningRule] = None):
        self.rules = rules or self.default_rules()
        self.readiness_checker = DataReadinessChecker()

    async def run_screening(self, trade_date: str = None) -> ScreeningResult:
        """
        执行全市场初筛:
        1. ★ 先调用 readiness_checker 检查数据就绪
        2. 数据缺失→直接返回(包含缺失报告，不执行计算)
        3. 数据就绪→逐条执行规则
        4. ★ 记录每条规则的命中/未命中统计
        5. 返回完整结果(含规则详情)供前端展示
        """

    async def check_revenue_growth(self, df: pd.DataFrame) -> tuple[pd.Series, RuleExecutionDetail]:
        """检查连续两年营收增长率 > 0，返回结果和执行详情"""

    async def check_net_profit(self, df: pd.DataFrame) -> tuple[pd.Series, RuleExecutionDetail]:
        """检查近一年净利润 > 0"""

    async def check_roe(self, df: pd.DataFrame) -> tuple[pd.Series, RuleExecutionDetail]:
        """检查近三年平均ROE >= 5%"""

    async def check_cashflow_sync(self, df: pd.DataFrame) -> tuple[pd.Series, RuleExecutionDetail]:
        """经营现金流/(营收+费用) > 0.5，连续两年"""

    async def check_expense_anomaly(self, df: pd.DataFrame) -> tuple[pd.Series, RuleExecutionDetail]:
        """费用率异常波动检测"""

    async def check_receivable_revenue(self, df: pd.DataFrame) -> tuple[pd.Series, RuleExecutionDetail]:
        """应收账款增速-营收增速 < 20%"""

    async def check_benford(self, df: pd.DataFrame) -> tuple[pd.Series, RuleExecutionDetail]:
        """本福德首位数字定律检验"""
```

#### 4.2 核心池构建 (CorePoolBuilder)

```python
class FactorWeight(BaseModel):
    """因子权重配置"""
    quality: float = 0.30
    growth: float = 0.30
    value: float = 0.20
    momentum: float = 0.20

class FactorScoreDetail(BaseModel):
    """★ 因子得分详情（前端展示用）"""
    ts_code: str
    stock_name: str
    quality_score: float
    quality_breakdown: dict    # {roe: 85, gross_margin: 72, debt_ratio: 90}
    growth_score: float
    growth_breakdown: dict     # {revenue_growth: 88, profit_growth: 76}
    value_score: float
    value_breakdown: dict      # {pe_percentile: 30, pb_percentile: 25}
    momentum_score: float
    momentum_breakdown: dict   # {half_year_return: 0.15, rps_250: 82}
    total_score: float

class CorePoolResult(BaseModel):
    """★ 核心池构建结果（前端展示用）"""
    update_date: str
    core_stocks: list[FactorScoreDetail]          # 核心50
    supplement_stocks: list[FactorScoreDetail]     # 补充20
    pool_changes: list[dict]                       # ★ 入池/出池变动列表
    factor_distribution: dict                      # ★ 因子得分分布统计
    data_readiness: DataReadinessResult

class CorePoolBuilder:
    """
    核心池构建器
    - ★ 仅从 ClickHouse 读取数据，不调用远程插件
    - 从初筛通过列表中多因子打分选Top50
    - RPS指标补充市场热点
    - ★ 输出因子得分详情和排名变动，供前端展示
    """
    async def build_core_pool(self, screened_stocks: list[str]) -> CorePoolResult:
        """构建核心池：先检查数据就绪 → Top50 + RPS补充"""

    async def calculate_quality_score(self, ts_code: str) -> tuple[float, dict]:
        """质量因子：ROE、毛利率、负债率 → 返回(得分, 明细)"""

    async def calculate_growth_score(self, ts_code: str) -> tuple[float, dict]:
        """成长因子：营收增速、利润增速 → 返回(得分, 明细)"""

    async def calculate_value_score(self, ts_code: str) -> tuple[float, dict]:
        """估值因子：PE/PB分位数 → 返回(得分, 明细)"""

    async def calculate_momentum_score(self, ts_code: str) -> tuple[float, dict]:
        """动量因子：近半年涨幅 → 返回(得分, 明细)"""

    async def update_pool(self) -> CorePoolResult:
        """动态调整：月度/季度更新，返回变动列表"""
```

#### 4.3 RPS 计算器

```python
class RPSCalculator:
    """
    RPS (Relative Price Strength) 计算器
    - ★ 仅从 ClickHouse 读取行情数据
    - 支持 60/120/250 日多周期
    """
    async def calculate_rps(self, period: int = 250) -> pd.DataFrame:
        """先检查数据就绪 → 计算全市场RPS"""

    async def get_strong_stocks(self, threshold: float = 80) -> list[str]:
        """获取RPS > threshold 的强势股"""
```

#### 4.4 深度分析引擎 (DeepAnalyzer)

```python
class DeepAnalyzer:
    """
    深度分析引擎
    - 技术指标监控（复用 market/indicators.py，★ 从本地数据计算）
    - 管理层讨论NLP分析（复用 ReportAgent + LLM）
    """
    async def analyze_technical(self, ts_code: str) -> TechAnalysisResult:
        """
        技术面分析（★ 纯本地数据）：
        - MA25/MA120 位置关系
        - MACD/RSI/成交量状态
        - ★ 返回完整指标快照，供前端图表渲染
        """

    async def analyze_mgmt_discussion(self, ts_code: str) -> MgmtAnalysisResult:
        """管理层讨论NLP分析（借助LLM）"""

    async def batch_analyze(self, pool_stocks: list[str]) -> list[DeepAnalysisResult]:
        """★ 批量分析，带进度回调供前端展示"""
```

#### 4.5 交易信号生成器 (SignalGenerator)

```python
class SignalConfig(BaseModel):
    """信号配置"""
    ma_short: int = 25
    ma_long: int = 120
    max_position_pct: float = 0.05
    stop_loss_pct: float = 0.15
    trailing_stop_pct: float = 0.10
    rps_exit_threshold: float = 75
    market_risk_ma: int = 250
    market_risk_position: float = 0.50

class SignalGenerator:
    """
    交易信号生成器
    - ★ 仅从 ClickHouse 读取行情数据，不调用远程插件
    - 入场：MA25上穿MA120金叉
    - 加仓：分批建仓（1/3 + 1/3 + 1/3）
    - 止损：跌破MA120 或 -15%
    - 止盈：高点回撤10% 或 RPS<75
    - 市场风控：沪深300跌破MA250降仓
    - ★ 每个信号带完整触发上下文，供前端展示
    """
    async def generate_signals(self, pool_stocks: list[str]) -> list[TradingSignal]:
        """先检查数据就绪 → 为目标池个股生成交易信号"""

    async def check_entry(self, ts_code: str, pool_type: str) -> Optional[TradingSignal]:
        """检查入场信号"""

    async def check_add_position(self, ts_code: str) -> Optional[TradingSignal]:
        """检查加仓信号"""

    async def check_exit(self, ts_code: str) -> Optional[TradingSignal]:
        """检查出场信号"""

    async def check_market_risk(self) -> MarketRiskLevel:
        """检查市场风控"""
```

### 5. Agent 设计

```python
class QuantAgent(LangGraphAgent):
    """
    量化模型 Agent
    工具集：
    - check_data_readiness: ★ 检查数据就绪状态
    - run_screening: 执行全市场初筛
    - build_core_pool: 构建/更新核心池
    - get_pool_status: 查看当前池状态
    - run_deep_analysis: 对指定个股深度分析
    - get_trading_signals: 获取最新交易信号
    - update_config: 更新模型参数配置
    - get_model_report: 生成模型运行报告
    """
```

### 6. API 设计

```
# ★ 数据就绪检查 API
GET  /api/quant/data-readiness              # 检查完整Pipeline数据就绪状态
GET  /api/quant/data-readiness/{stage}      # 检查特定阶段数据就绪(screening/pool/signal)

# ★ Pipeline 运行 API
POST /api/quant/pipeline/run                # 运行完整Pipeline(自动检查数据)
GET  /api/quant/pipeline/status/{run_id}    # 获取Pipeline运行状态和每步结果
GET  /api/quant/pipeline/latest             # 获取最近一次Pipeline运行结果

# 初筛 API
POST /api/quant/screening/run               # 运行全市场初筛(先检查数据)
GET  /api/quant/screening/result            # 获取最新初筛结果(含规则详情)
GET  /api/quant/screening/result/{run_date} # 获取指定日期初筛结果
GET  /api/quant/screening/rules             # 获取筛选规则配置
PUT  /api/quant/screening/rules             # 更新筛选规则
GET  /api/quant/screening/stats             # ★ 获取初筛统计(每条规则命中数)

# 核心池 API
GET  /api/quant/pool                        # 获取当前目标池(含因子详情)
GET  /api/quant/pool/history                # 池变动历史
GET  /api/quant/pool/changes                # ★ 入池/出池变动日志
POST /api/quant/pool/refresh                # 刷新核心池(先检查数据)

# RPS API
GET  /api/quant/rps                         # 获取RPS排名
GET  /api/quant/rps/{ts_code}               # 个股RPS详情

# 深度分析 API
POST /api/quant/analysis/{ts_code}          # 个股深度分析
GET  /api/quant/analysis/dashboard          # 目标池监控仪表盘(含技术指标快照)
GET  /api/quant/analysis/batch/status       # ★ 批量分析进度

# 交易信号 API
GET  /api/quant/signals                     # 获取最新交易信号(含触发上下文)
GET  /api/quant/signals/history             # 信号历史
GET  /api/quant/risk                        # 市场风控状态

# 配置 API
GET  /api/quant/config                      # 获取模型配置
PUT  /api/quant/config                      # 更新模型配置
GET  /api/quant/report                      # 模型运行报告
```

### 7. 调度设计

| 任务 | 频率 | 触发条件 | 描述 |
|------|------|---------|------|
| `daily_signal_check` | 每交易日收盘后 | 自动(★先检查数据就绪) | 检查目标池个股均线信号 |
| `daily_tech_monitor` | 每交易日收盘后 | 自动(★先检查数据就绪) | 更新技术指标监控数据 |
| `weekly_rps_calc` | 每周五收盘后 | 自动(★先检查数据就绪) | 计算全市场RPS排名 |
| `weekly_pool_supplement` | 每周五RPS后 | 依赖RPS | RPS补充池更新 |
| `quarterly_screening` | 季报发布后 | 手动触发 | 全市场财报初筛 |
| `quarterly_pool_rebuild` | 初筛后 | 依赖初筛 | 重建核心池 |
| `manual_deep_analysis` | 按需 | 手动触发 | 管理层讨论NLP分析 |

**调度数据检查**：所有自动调度任务执行前先检查数据就绪。若数据不足，记录到 `quant_pipeline_run` 表，前端可查看并一键补数据。

### 8. 前端页面设计 ★ 全链路可视化

#### 8.1 量化模型主页 (`/quant`) - Pipeline 概览

```
┌─────────────────────────────────────────────────────┐
│  量化选股模型                                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ★ Pipeline 进度条                                   │
│  ┌─────────┐  →  ┌─────────┐  →  ┌──────┐  →  ┌──────┐
│  │① 全市场 │     │② 核心池 │     │③ 深度│     │④ 交易│
│  │   初筛   │     │   构建  │     │  分析 │     │  信号 │
│  │  ✅完成  │     │  ⏳进行  │     │  ⬜待定│     │  ⬜待定│
│  │ 250/5000│     │  50+20  │     │       │     │       │
│  └─────────┘     └─────────┘     └──────┘     └──────┘
│                                                     │
│  ★ 数据就绪状态                                      │
│  ┌─────────────────────────────────────────┐       │
│  │ ⚠️ 以下数据缺失，影响后续计算：            │       │
│  │  - fact_income: 缺失 2025-12-31 季报数据  │       │
│  │  - fact_daily_bar: 缺失最近3个交易日      │       │
│  │                                          │       │
│  │  需要触发的插件:                           │       │
│  │  ☑ tushare_income (利润表)               │       │
│  │  ☑ tushare_daily (日线行情)              │       │
│  │                                          │       │
│  │  [一键补充所有缺失数据]  [仅补充选中项]    │       │
│  └─────────────────────────────────────────┘       │
│                                                     │
│  关键指标概览                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │核心池 50 │  │补充池 18 │  │今日信号 3 │         │
│  │↑3 ↓2     │  │↑5 ↓1    │  │买2 卖1   │         │
│  └──────────┘  └──────────┘  └──────────┘         │
└─────────────────────────────────────────────────────┘
```

#### 8.2 初筛结果页 (`/quant/screening`)

```
┌─────────────────────────────────────────────────────┐
│  全市场初筛                                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ★ 规则执行统计（每条规则的命中详情）                   │
│  ┌──────────────────────────────────────────┐      │
│  │ 规则名称          │ 通过 │ 剔除 │ 跳过  │      │
│  │─────────────────│──────│──────│──────│      │
│  │ 营收增长率(>0,2Y) │ 3200 │ 1800 │   0  │      │
│  │ 净利润(>0)       │ 3800 │ 1200 │   0  │      │
│  │ ROE(>5%,3Y)     │ 2100 │ 2900 │   0  │      │
│  │ 现金流同步率      │ 1800 │  300 │ 100  │      │
│  │ 费用异常检测      │ 1750 │   50 │   0  │      │
│  │ 应收营收联动      │ 1700 │   50 │   0  │      │
│  │ 本福德检验(软)    │ 1650 │   50 │   0  │      │
│  └──────────────────────────────────────────┘      │
│                                                     │
│  [规则配置] 按钮 → 弹窗编辑阈值/启用/禁用              │
│                                                     │
│  ★ 通过列表(250只)  |  ★ 剔除列表(4750只)            │
│  ┌──────────────────────────────────────────┐      │
│  │ 代码  │ 名称  │ ROE │ 营收增速 │ 剔除原因│      │
│  │ ...  │ ...  │ ... │  ...   │   ...  │      │
│  └──────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────┘
```

#### 8.3 核心池页 (`/quant/pool`)

```
┌─────────────────────────────────────────────────────┐
│  核心目标池                                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ★ 因子得分分布（四个因子的箱线图/直方图）              │
│  [质量30%] [成长30%] [估值20%] [动量20%]             │
│                                                     │
│  ★ 入池/出池变动日志                                  │
│  ┌──────────────────────────────────────────┐      │
│  │ 2026-02-27: 新入 000001(平安银行) 总分82  │      │
│  │ 2026-02-27: 调出 600519(贵州茅台) 排名↓55 │      │
│  └──────────────────────────────────────────┘      │
│                                                     │
│  核心池(50)  |  补充池(RPS, 18)                      │
│  ┌─────────────────────────────────────────┐       │
│  │ 排名│代码│名称│质量│成长│估值│动量│总分│RPS│       │
│  │  1 │...│...│ 85│ 92│ 78│ 80│88.2│ 95│       │
│  └─────────────────────────────────────────┘       │
│  点击行 → 展开因子明细雷达图                          │
└─────────────────────────────────────────────────────┘
```

#### 8.4 其他页面同理

- **RPS排名页** (`/quant/rps`)：全市场RPS热力图 + Top100列表 + 多周期对比
- **深度分析页** (`/quant/analysis`)：技术指标图表(MA/MACD/RSI) + AI分析卡片(可信度/乐观度/验证点) + 批量分析进度条
- **交易信号页** (`/quant/signals`)：信号列表(含触发原因和上下文) + 风控状态面板 + 仓位建议 + 历史信号回顾
- **模型配置页** (`/quant/config`)：规则阈值滑块 + 因子权重调节 + 信号参数 + 风控参数

## 关键设计决策

### D1: 纯本地数据计算，不调用 TuShare 插件 ★

**决策**：所有引擎计算过程只从 ClickHouse 读取本地已有数据，禁止调用任何 TuShare/AKShare 远程数据插件。

**理由**：
- 避免 TuShare 积分消耗不可控
- 保证计算速度（本地查询 vs 远程API调用）
- 计算过程可离线运行
- 数据的获取和计算解耦，职责清晰

### D2: 数据缺失时前端提示 + 一键补数据 ★

**决策**：数据不足时不自动拉取，而是返回结构化缺失报告，前端展示并提供一键触发按钮。

**理由**：
- 用户对数据拉取有知情权和控制权
- 避免意外消耗 TuShare 积分
- 复用现有 `MissingDataPanel` + `batchTriggerSync` 架构，开发成本低
- 用户可选择性补充部分数据

### D3: 本福德检验作为软条件

**决策**：本福德首位数字定律检验结果作为**标记警告**而非直接剔除条件。

**理由**：
- 部分行业（如金融）的数据分布天然不完全符合本福德分布
- 误判率较高可能导致错误剔除优质标的
- 作为软条件，由人工或 AI 进一步判断

### D4: RPS 补充池的财务快检

**决策**：RPS 补充个股需通过**简化版财务检查**（仅核心条件：净利润>0 + ROE>3%）。

**理由**：
- 完整初筛太慢，不适合周度频率
- RPS 强势股本身具有市场验证，无需过严的基本面门槛
- 但需排除明显有问题的标的

### D5: 信号确认机制

**决策**：系统只生成信号，不自动下单。所有信号标注置信度，由用户决定执行。

**理由**：
- 自动交易涉及券商API对接，安全和合规风险高
- 中线策略不需要毫秒级执行速度
- 保留人工判断环节，避免机械执行导致大额亏损

### D6: 每步关键信息全展示 ★

**决策**：Pipeline每个阶段的计算过程、中间结果、关键统计都通过API返回并在前端展示。

**理由**：
- 量化模型的透明度是用户信任的基础
- 用户需要理解模型的决策逻辑，而不是"黑箱"
- 方便排查问题和调优参数
- 前端分层展示（概览→详情→明细），避免信息过载

### D7: 增量计算 vs 全量计算

**决策**：行情类指标（RPS/MA/信号）增量计算，财务类指标（初筛/因子打分）全量计算。

**理由**：
- 行情数据每日更新，增量即可
- 财务数据季度更新，全量计算频率低且数据量可控
- 避免增量计算中的数据一致性问题

## 性能考量

- **数据就绪检查**：仅执行 `SELECT 1 / COUNT / MIN/MAX` 等轻量查询，预计 < 1 秒
- **初筛引擎**：约5000只股票 × 7条规则，纯 ClickHouse 查询，预计 30-60 秒
- **RPS 计算**：全市场 5000 只 × 250 日数据，利用 ClickHouse 向量计算，预计 5-10 秒
- **信号生成**：目标池 70 只 × 均线计算，预计 2-5 秒
- **深度分析**：单只 NLP 分析约 10-30 秒（LLM 调用），批量需排队处理，前端展示进度
