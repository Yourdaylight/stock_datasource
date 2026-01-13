ETF基础信息
接口：etf_basic
描述：获取国内ETF基础信息，包括了QDII。数据来源与沪深交易所公开披露信息。
限量：单次请求最大放回5000条数据（当前ETF总数未超过2000）
权限：用户积8000积分可调取，具体请参阅积分获取办法



输入参数

名称	类型	必选	描述
ts_code	str	N	ETF代码（带.SZ/.SH后缀的6位数字，如：159526.SZ）
index_code	str	N	跟踪指数代码
list_date	str	N	上市日期（格式：YYYYMMDD）
list_status	str	N	上市状态（L上市 D退市 P待上市）
exchange	str	N	交易所（SH上交所 SZ深交所）
mgr	str	N	管理人（简称，e.g.华夏基金)


输出参数

名称	类型	默认显示	描述
ts_code	str	Y	基金交易代码
csname	str	Y	ETF中文简称
extname	str	Y	ETF扩位简称(对应交易所简称)
cname	str	Y	基金中文全称
index_code	str	Y	ETF基准指数代码
index_name	str	Y	ETF基准指数中文全称
setup_date	str	Y	设立日期（格式：YYYYMMDD）
list_date	str	Y	上市日期（格式：YYYYMMDD）
list_status	str	Y	存续状态（L上市 D退市 P待上市）
exchange	str	Y	交易所（上交所SH 深交所SZ）
mgr_name	str	Y	基金管理人简称
custod_name	str	Y	基金托管人名称
mgt_fee	float	Y	基金管理人收取的费用
etf_type	str	Y	基金投资通道类型（境内、QDII）


接口示例


#获取当前所有上市的ETF列表
df = pro.etf_basic(list_status='L', fields='ts_code,extname,index_code,index_name,exchange,mgr_name')


#获取“嘉实基金”所有上市的ETF列表
df = pro.etf_basic(mgr='嘉实基金'， list_status='L', fields='ts_code,extname,index_code,index_name,exchange,etf_type')


#获取“嘉实基金”在深交所上市的所有ETF列表
df = pro.etf_basic(mgr='嘉实基金'， list_status='L', exchange='SZ', fields='ts_code,extname,index_code,index_name,exchange,etf_type')


#获取以沪深300指数为跟踪指数的所有上市的ETF列表
df = pro.etf_basic(index_code='000300.SH', fields='ts_code,extname,index_code,index_name,exchange,mgr_name')


数据示例

      ts_code       extname    index_code    index_name exchange   mgr_name
0   159238.SZ      300ETF增强  000300.SH    沪深300指数       SZ   景顺长城基金
1   159300.SZ        300ETF  000300.SH    沪深300指数       SZ     富国基金
2   159330.SZ    沪深300ETF基金  000300.SH    沪深300指数       SZ   西藏东财基金
3   159393.SZ    沪深300指数ETF  000300.SH    沪深300指数       SZ     万家基金
4   159673.SZ    沪深300ETF鹏华  000300.SH    沪深300指数       SZ     鹏华基金
5   159919.SZ      沪深300ETF  000300.SH    沪深300指数       SZ     嘉实基金
6   159925.SZ    沪深300ETF南方  000300.SH    沪深300指数       SZ     南方基金