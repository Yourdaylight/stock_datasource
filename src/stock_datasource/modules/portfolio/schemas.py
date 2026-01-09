"""Portfolio module database schemas."""

from stock_datasource.models.schemas import TableSchema, ColumnDefinition, TableType

# User positions table schema
USER_POSITIONS_SCHEMA = TableSchema(
    table_name="user_positions",
    table_type=TableType.FACT,
    columns=[
        ColumnDefinition(
            name="id",
            data_type="String",
            nullable=False,
            comment="Unique position identifier"
        ),
        ColumnDefinition(
            name="ts_code",
            data_type="LowCardinality(String)",
            nullable=False,
            comment="Stock code (e.g., 600519.SH)"
        ),
        ColumnDefinition(
            name="stock_name",
            data_type="String",
            nullable=False,
            comment="Stock name"
        ),
        ColumnDefinition(
            name="quantity",
            data_type="UInt32",
            nullable=False,
            comment="Number of shares"
        ),
        ColumnDefinition(
            name="cost_price",
            data_type="Decimal(10, 3)",
            nullable=False,
            comment="Cost price per share"
        ),
        ColumnDefinition(
            name="buy_date",
            data_type="Date",
            nullable=False,
            comment="Purchase date"
        ),
        ColumnDefinition(
            name="current_price",
            data_type="Nullable(Decimal(10, 3))",
            nullable=True,
            comment="Current market price"
        ),
        ColumnDefinition(
            name="market_value",
            data_type="Nullable(Decimal(15, 2))",
            nullable=True,
            comment="Current market value"
        ),
        ColumnDefinition(
            name="profit_loss",
            data_type="Nullable(Decimal(15, 2))",
            nullable=True,
            comment="Profit or loss amount"
        ),
        ColumnDefinition(
            name="profit_rate",
            data_type="Nullable(Decimal(8, 4))",
            nullable=True,
            comment="Profit rate percentage"
        ),
        ColumnDefinition(
            name="notes",
            data_type="Nullable(String)",
            nullable=True,
            comment="User notes"
        ),
        ColumnDefinition(
            name="created_at",
            data_type="DateTime",
            nullable=False,
            default_value="now()",
            comment="Creation timestamp"
        ),
        ColumnDefinition(
            name="updated_at",
            data_type="DateTime",
            nullable=False,
            default_value="now()",
            comment="Last update timestamp"
        )
    ],
    partition_by="toYYYYMM(buy_date)",
    order_by=["ts_code", "buy_date", "id"],
    engine="ReplacingMergeTree",
    engine_params=["updated_at"],
    comment="User stock positions and holdings"
)

# Portfolio analysis table schema
PORTFOLIO_ANALYSIS_SCHEMA = TableSchema(
    table_name="portfolio_analysis",
    table_type=TableType.FACT,
    columns=[
        ColumnDefinition(
            name="id",
            data_type="String",
            nullable=False,
            comment="Unique analysis identifier"
        ),
        ColumnDefinition(
            name="analysis_date",
            data_type="Date",
            nullable=False,
            comment="Analysis date"
        ),
        ColumnDefinition(
            name="analysis_summary",
            data_type="Nullable(String)",
            nullable=True,
            comment="Analysis summary text"
        ),
        ColumnDefinition(
            name="stock_analyses",
            data_type="Nullable(String)",
            nullable=True,
            comment="Individual stock analyses (JSON format)"
        ),
        ColumnDefinition(
            name="risk_alerts",
            data_type="Nullable(String)",
            nullable=True,
            comment="Risk alerts (JSON array)"
        ),
        ColumnDefinition(
            name="recommendations",
            data_type="Nullable(String)",
            nullable=True,
            comment="Investment recommendations (JSON array)"
        ),
        ColumnDefinition(
            name="created_at",
            data_type="DateTime",
            nullable=False,
            default_value="now()",
            comment="Creation timestamp"
        )
    ],
    partition_by="toYYYYMM(analysis_date)",
    order_by=["analysis_date", "id"],
    engine="ReplacingMergeTree",
    engine_params=["created_at"],
    comment="Portfolio analysis and recommendations"
)

# Portfolio module schemas
PORTFOLIO_SCHEMAS = {
    "user_positions": USER_POSITIONS_SCHEMA,
    "portfolio_analysis": PORTFOLIO_ANALYSIS_SCHEMA,
}