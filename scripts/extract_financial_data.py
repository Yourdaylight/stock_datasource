"""提取财务数据到 ClickHouse"""

from stock_datasource.plugins.tushare_income.plugin import TuShareIncomePlugin
from stock_datasource.plugins.tushare_balancesheet.plugin import TuShareBalancesheetPlugin
from stock_datasource.plugins.tushare_cashflow.plugin import TuShareCashflowPlugin
from stock_datasource.plugins.tushare_forecast.plugin import TuShareForecastPlugin
from stock_datasource.plugins.tushare_express.plugin import TuShareExpressPlugin

ts_code = '600519.SH'
print(f'开始提取 {ts_code} 的财务数据...\n')

print('1. 提取利润表...')
TuShareIncomePlugin().run(ts_code=ts_code)
print('   完成\n')

print('2. 提取资产负债表...')
TuShareBalancesheetPlugin().run(ts_code=ts_code)
print('   完成\n')

print('3. 提取现金流量表...')
TuShareCashflowPlugin().run(ts_code=ts_code)
print('   完成\n')

print('4. 提取业绩预告...')
TuShareForecastPlugin().run(ts_code=ts_code)
print('   完成\n')

print('5. 提取业绩快报...')
TuShareExpressPlugin().run(ts_code=ts_code)
print('   完成\n')

print(f'{ts_code} 所有财务数据提取完成!')
