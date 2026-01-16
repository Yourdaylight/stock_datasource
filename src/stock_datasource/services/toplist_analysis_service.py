"""Top list analysis service for advanced analytics."""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np

from stock_datasource.models.database import db_client
from stock_datasource.utils.logger import logger
from .toplist_service import TopListService


class TopListAnalysisService:
    """龙虎榜分析服务"""
    
    def __init__(self):
        self.db = db_client
        self.logger = logger.bind(component="TopListAnalysisService")
        self.toplist_service = TopListService()
    
    async def analyze_institutional_flow(self, trade_date: str) -> Dict[str, Any]:
        """分析机构资金流向
        
        Args:
            trade_date: 交易日期
        
        Returns:
            机构资金流向分析结果
        """
        try:
            # 获取机构席位数据
            top_inst_data = await self.toplist_service.get_top_inst_by_date(trade_date)
            
            if not top_inst_data:
                return {
                    "net_buy_ranking": [],
                    "active_institutions": [],
                    "sector_preference": {},
                    "trading_patterns": {}
                }
            
            # 转换为DataFrame便于分析
            df = pd.DataFrame(top_inst_data)
            
            # 筛选机构席位
            inst_df = df[df['seat_type'] == 'institution'].copy()
            
            analysis = {
                "net_buy_ranking": [],
                "active_institutions": [],
                "sector_preference": {},
                "trading_patterns": {}
            }
            
            if not inst_df.empty:
                # 计算机构净买入排行
                inst_summary = inst_df.groupby('exalter').agg({
                    'buy': 'sum',
                    'sell': 'sum',
                    'net_buy': 'sum',
                    'ts_code': 'count'
                }).reset_index()
                
                inst_summary.columns = ['institution', 'total_buy', 'total_sell', 'net_buy', 'stock_count']
                inst_summary = inst_summary.sort_values('net_buy', ascending=False)
                
                # 转换为字典列表
                analysis['net_buy_ranking'] = inst_summary.head(20).to_dict('records')
                
                # 活跃机构（操作股票数量多）
                active_institutions = inst_summary[inst_summary['stock_count'] >= 3].head(10)
                analysis['active_institutions'] = active_institutions.to_dict('records')
                
                # 交易模式分析
                analysis['trading_patterns'] = {
                    'total_institutions': len(inst_summary),
                    'net_buyers': len(inst_summary[inst_summary['net_buy'] > 0]),
                    'net_sellers': len(inst_summary[inst_summary['net_buy'] < 0]),
                    'total_net_flow': float(inst_summary['net_buy'].sum()),
                    'avg_position_size': float(inst_summary['net_buy'].abs().mean())
                }
            
            self.logger.info(f"Completed institutional flow analysis for {trade_date}")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Failed to analyze institutional flow for {trade_date}: {e}")
            raise
    
    async def identify_hot_money_targets(self, days: int = 5) -> List[Dict[str, Any]]:
        """识别游资目标股票
        
        Args:
            days: 分析天数
        
        Returns:
            游资目标股票列表
        """
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # 查询游资活跃的股票
            query = """
            SELECT 
                t.ts_code,
                t.name,
                COUNT(DISTINCT i.exalter) as hot_money_count,
                SUM(i.net_buy) as total_hot_money_flow,
                AVG(t.pct_chg) as avg_pct_chg,
                COUNT(DISTINCT t.trade_date) as appearance_days,
                MAX(t.trade_date) as last_appearance
            FROM ods_top_list t
            JOIN ods_top_inst i ON t.ts_code = i.ts_code AND t.trade_date = i.trade_date
            WHERE t.trade_date >= %(start_date)s
              AND t.trade_date <= %(end_date)s
              AND i.seat_type = 'hot_money'
              AND i.net_buy > 0
            GROUP BY t.ts_code, t.name
            HAVING hot_money_count >= 2
            ORDER BY total_hot_money_flow DESC, hot_money_count DESC
            LIMIT 30
            """
            
            result = self.db.query(query, {
                "start_date": start_date,
                "end_date": end_date
            })
            
            # 计算游资集中度
            for item in result:
                item['concentration_score'] = (
                    item['hot_money_count'] * 0.4 + 
                    item['appearance_days'] * 0.3 + 
                    min(item['total_hot_money_flow'] / 10000, 10) * 0.3
                )
            
            # 按集中度重新排序
            result.sort(key=lambda x: x['concentration_score'], reverse=True)
            
            self.logger.info(f"Identified {len(result)} hot money targets in last {days} days")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to identify hot money targets: {e}")
            raise
    
    async def calculate_seat_concentration(self, ts_code: str, days: int = 10) -> Dict[str, Any]:
        """计算席位集中度
        
        Args:
            ts_code: 股票代码
            days: 分析天数
        
        Returns:
            席位集中度分析
        """
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # 获取股票的席位数据
            query = """
            SELECT 
                trade_date,
                exalter,
                net_buy,
                seat_type
            FROM ods_top_inst
            WHERE ts_code = %(ts_code)s
              AND trade_date >= %(start_date)s
              AND trade_date <= %(end_date)s
            ORDER BY trade_date DESC, net_buy DESC
            """
            
            result = self.db.query(query, {
                "ts_code": ts_code,
                "start_date": start_date,
                "end_date": end_date
            })
            
            if not result:
                return {
                    "concentration_index": 0,
                    "top_seats": [],
                    "seat_stability": 0,
                    "institution_dominance": 0
                }
            
            df = pd.DataFrame(result)
            
            # 计算席位集中度指标
            analysis = {}
            
            # 1. 赫芬达尔指数 (HHI) - 衡量集中度
            total_flow = df['net_buy'].abs().sum()
            if total_flow > 0:
                seat_shares = df.groupby('exalter')['net_buy'].sum().abs() / total_flow
                hhi = (seat_shares ** 2).sum()
                analysis['concentration_index'] = float(hhi)
            else:
                analysis['concentration_index'] = 0
            
            # 2. 主要席位分析
            top_seats = df.groupby('exalter').agg({
                'net_buy': 'sum',
                'trade_date': 'count',
                'seat_type': 'first'
            }).reset_index()
            
            top_seats.columns = ['seat_name', 'total_net_buy', 'appearance_count', 'seat_type']
            top_seats = top_seats.sort_values('total_net_buy', ascending=False)
            analysis['top_seats'] = top_seats.head(10).to_dict('records')
            
            # 3. 席位稳定性（重复出现的席位比例）
            total_appearances = len(df)
            repeat_appearances = df.groupby('exalter').size()
            stability_score = (repeat_appearances > 1).sum() / len(repeat_appearances) if len(repeat_appearances) > 0 else 0
            analysis['seat_stability'] = float(stability_score)
            
            # 4. 机构主导度
            institution_flow = df[df['seat_type'] == 'institution']['net_buy'].sum()
            total_net_flow = df['net_buy'].sum()
            if total_net_flow != 0:
                analysis['institution_dominance'] = float(abs(institution_flow) / abs(total_net_flow))
            else:
                analysis['institution_dominance'] = 0
            
            self.logger.info(f"Calculated seat concentration for {ts_code}")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Failed to calculate seat concentration for {ts_code}: {e}")
            raise
    
    async def analyze_sector_flow(self, trade_date: str) -> Dict[str, Any]:
        """分析板块资金流向
        
        Args:
            trade_date: 交易日期
        
        Returns:
            板块资金流向分析
        """
        try:
            # 这里需要结合股票基本信息表来获取行业分类
            # 暂时使用股票代码前缀进行简单分类
            query = """
            SELECT 
                CASE 
                    WHEN ts_code LIKE '00%' THEN '深市主板'
                    WHEN ts_code LIKE '30%' THEN '创业板'
                    WHEN ts_code LIKE '60%' THEN '沪市主板'
                    WHEN ts_code LIKE '68%' THEN '科创板'
                    ELSE '其他'
                END as sector,
                COUNT(*) as stock_count,
                SUM(net_amount) as net_flow,
                AVG(pct_chg) as avg_pct_chg,
                SUM(amount) as total_amount
            FROM ods_top_list
            WHERE trade_date = %(trade_date)s
            GROUP BY sector
            ORDER BY net_flow DESC
            """
            
            # 标准化日期格式
            if len(trade_date) == 8:  # YYYYMMDD
                formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            else:
                formatted_date = trade_date
            
            result = self.db.query(query, {"trade_date": formatted_date})
            
            # 计算占比
            total_amount = sum(item['total_amount'] or 0 for item in result)
            for item in result:
                item['amount_ratio'] = (item['total_amount'] or 0) / total_amount if total_amount > 0 else 0
            
            analysis = {
                "sector_flows": result,
                "total_sectors": len(result),
                "net_inflow_sectors": len([r for r in result if (r['net_flow'] or 0) > 0]),
                "net_outflow_sectors": len([r for r in result if (r['net_flow'] or 0) < 0])
            }
            
            self.logger.info(f"Analyzed sector flows for {trade_date}")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Failed to analyze sector flow for {trade_date}: {e}")
            raise
    
    async def detect_unusual_activity(self, days: int = 5) -> List[Dict[str, Any]]:
        """检测异常交易活动
        
        Args:
            days: 检测天数
        
        Returns:
            异常活动列表
        """
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # 检测异常大额交易
            large_trade_query = """
            SELECT 
                trade_date,
                ts_code,
                name,
                net_amount,
                pct_chg,
                turnover_rate,
                reason,
                'large_net_amount' as anomaly_type
            FROM ods_top_list
            WHERE trade_date >= %(start_date)s
              AND trade_date <= %(end_date)s
              AND net_amount > (
                  SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY net_amount)
                  FROM ods_top_list
                  WHERE trade_date >= %(start_date)s AND trade_date <= %(end_date)s
              )
            """
            
            # 检测异常换手率
            high_turnover_query = """
            SELECT 
                trade_date,
                ts_code,
                name,
                net_amount,
                pct_chg,
                turnover_rate,
                reason,
                'high_turnover' as anomaly_type
            FROM ods_top_list
            WHERE trade_date >= %(start_date)s
              AND trade_date <= %(end_date)s
              AND turnover_rate > 50
            """
            
            # 检测连续上榜
            continuous_query = """
            SELECT 
                ts_code,
                name,
                COUNT(*) as consecutive_days,
                SUM(net_amount) as total_net_amount,
                'continuous_appearance' as anomaly_type
            FROM ods_top_list
            WHERE trade_date >= %(start_date)s
              AND trade_date <= %(end_date)s
            GROUP BY ts_code, name
            HAVING consecutive_days >= 3
            """
            
            params = {"start_date": start_date, "end_date": end_date}
            
            large_trades = self.db.query(large_trade_query, params)
            high_turnovers = self.db.query(high_turnover_query, params)
            continuous_appearances = self.db.query(continuous_query, params)
            
            # 合并异常活动
            anomalies = []
            anomalies.extend(large_trades)
            anomalies.extend(high_turnovers)
            
            # 为连续上榜添加额外信息
            for item in continuous_appearances:
                item['trade_date'] = end_date.strftime('%Y-%m-%d')
                item['net_amount'] = item['total_net_amount']
                item['pct_chg'] = None
                item['turnover_rate'] = None
                item['reason'] = f"连续{item['consecutive_days']}天上榜"
                anomalies.append(item)
            
            # 按净买入额排序
            anomalies.sort(key=lambda x: abs(x.get('net_amount', 0)), reverse=True)
            
            self.logger.info(f"Detected {len(anomalies)} unusual activities in last {days} days")
            return anomalies[:50]  # 返回前50个异常
            
        except Exception as e:
            self.logger.error(f"Failed to detect unusual activity: {e}")
            raise