接口：stk_mins
描述：获取ETF分钟数据，支持1min/5min/15min/30min/60min行情，提供Python SDK和 http Restful API两种方式
限量：单次最大8000行数据，可以通过股票代码和时间循环获取，本接口可以提供超过10年ETF历史分钟数据
权限：正式权限请参阅 权限说明



输入参数

名称	类型	必选	描述
ts_code	str	Y	ETF代码，e.g. 159001.SZ
freq	str	Y	分钟频度（1min/5min/15min/30min/60min）
start_date	datetime	N	开始日期 格式：2025-06-01 09:00:00
end_date	datetime	N	结束时间 格式：2025-06-20 19:00:00


freq参数说明

freq	说明
1min	1分钟
5min	5分钟
15min	15分钟
30min	30分钟
60min	60分钟


输出参数

名称	类型	默认显示	描述
ts_code	str	Y	ETF代码
trade_time	str	Y	交易时间
open	float	Y	开盘价
close	float	Y	收盘价
high	float	Y	最高价
low	float	Y	最低价
vol	int	Y	成交量
amount	float	Y	成交金额


接口用法


pro = ts.pro_api()

#获取沪深300ETF华夏510330.SH的历史分钟数据
df = pro.stk_mins(ts_code='510330.SH', freq='1min', start_date='2025-06-20 09:00:00', end_date='2025-06-20 19:00:00')


数据样例

       ts_code           trade_time  close   open   high    low        vol      amount
0    510330.SH  2025-06-20 15:00:00  3.991  3.991  3.992  3.990   800600.0   3194805.0
1    510330.SH  2025-06-20 14:59:00  3.991  3.990  3.991  3.989   182500.0    728177.0
2    510330.SH  2025-06-20 14:58:00  3.990  3.992  3.992  3.990   113700.0    453763.