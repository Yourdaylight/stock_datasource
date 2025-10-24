> 来源：https://tushare.pro/document/2?doc_id=25

# 接口：stock_basic

**描述**  
获取基础信息数据，包括股票代码、名称、上市日期、退市日期等。

**权限**  
2000 积分起。本接口为基础信息接口，调取一次即可拉取全部数据。  
建议保存到本地存储后使用。

---

## 输入参数

| 名称 | 类型 | 必选 | 描述 |
|------|------|------|------|
| ts_code | str | N | TS股票代码 |
| name | str | N | 名称 |
| market | str | N | 市场类别（主板/创业板/科创板/CDR/北交所） |
| list_status | str | N | 上市状态 L上市 D退市 P暂停上市，默认是L |
| exchange | str | N | 交易所 SSE上交所 SZSE深交所 BSE北交所 |
| is_hs | str | N | 是否沪深港通标的，N否 H沪股通 S深股通 |

---

## 输出参数

| 名称 | 类型 | 默认显示 | 描述 |
|------|------|-----------|------|
| ts_code | str | Y | TS代码 |
| symbol | str | Y | 股票代码 |
| name | str | Y | 股票名称 |
| area | str | Y | 地域 |
| industry | str | Y | 所属行业 |
| fullname | str | N | 股票全称 |
| enname | str | N | 英文全称 |
| cnspell | str | Y | 拼音缩写 |
| market | str | Y | 市场类型（主板/创业板/科创板/CDR） |
| exchange | str | N | 交易所代码 |
| curr_type | str | N | 交易货币 |
| list_status | str | N | 上市状态 L上市 D退市 P暂停上市 |
| list_date | str | Y | 上市日期 |
| delist_date | str | N | 退市日期 |
| is_hs | str | N | 是否沪深港通标的，N否 H沪股通 S深股通 |
| act_name | str | Y | 实控人名称 |
| act_ent_type | str | Y | 实控人企业性质 |

> 说明：旧版上的 PE / PB / 股本等字段，请在行情接口「每日指标」中获取。

---

## 接口示例

```python
import tushare as ts

pro = ts.pro_api()

# 查询当前所有正常上市交易的股票列表
data = pro.stock_basic(
    exchange='',
    list_status='L',
    fields='ts_code,symbol,name,area,industry,list_date'
)
```

或：

```python
# 查询当前所有正常上市交易的股票列表
data = pro.query(
    'stock_basic',
    exchange='',
    list_status='L',
    fields='ts_code,symbol,name,area,industry,list_date'
)
```

---

## 数据样例

| ts_code | symbol | name | area | industry | list_date |
|----------|---------|------|------|-----------|------------|
| 000001.SZ | 000001 | 平安银行 | 深圳 | 银行 | 19910403 |
| 000002.SZ | 000002 | 万科A | 深圳 | 全国地产 | 19910129 |
| 000004.SZ | 000004 | 国农科技 | 深圳 | 生物制药 | 19910114 |
| 000005.SZ | 000005 | 世纪星源 | 深圳 | 房产服务 | 19901210 |
| 000006.SZ | 000006 | 深振业A | 深圳 | 区域地产 | 19920427 |
| 000007.SZ | 000007 | 全新好 | 深圳 | 酒店餐饮 | 19920413 |

