# ETF基准指数列表 (etf_index)

## 接口说明

获取ETF基准指数列表信息，包含指数代码、名称、发布机构、基日、基点等信息。

## 数据来源

- API: `pro.etf_index()`
- 文档: https://tushare.pro/document/2?doc_id=386

## 权限要求

- 积分要求: 8000积分
- 单次最大返回: 5000行（当前总数未超过2000个）

## 输入参数

| 名称 | 类型 | 必选 | 描述 |
|------|------|------|------|
| ts_code | str | 否 | 指数代码 |
| pub_date | str | 否 | 发布日期（格式：YYYYMMDD） |
| base_date | str | 否 | 指数基期（格式：YYYYMMDD） |

## 输出字段

| 名称 | 类型 | 描述 |
|------|------|------|
| ts_code | str | 指数代码 |
| indx_name | str | 指数全称 |
| indx_csname | str | 指数简称 |
| pub_party_name | str | 指数发布机构 |
| pub_date | str | 指数发布日期 |
| base_date | str | 指数基日 |
| bp | float | 指数基点(点) |
| adj_circle | str | 指数成份证券调整周期 |

## 调用示例

```python
# 获取当前ETF跟踪的基准指数列表
df = pro.etf_index(fields='ts_code,indx_name,pub_date,bp')
```

## 数据表

- ODS表: `ods_etf_index`
- 引擎: ReplacingMergeTree
- 主键: `ts_code`

## 同步策略

- 同步模式: `full_replace`（全量覆盖）
- 调度频率: 每周一次（数据变化不频繁）
