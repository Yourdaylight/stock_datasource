"""Anomaly detection service for top list data."""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass

from stock_datasource.models.database import db_client
from stock_datasource.utils.logger import logger


@dataclass
class AnomalyAlert:
    """异动预警数据结构"""
    ts_code: str
    name: str
    trade_date: str
    anomaly_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    metrics: Dict[str, Any]
    confidence: float


class AnomalyDetectionService:
    """异动检测服务"""
    
    def __init__(self):
        self.db = db_client
        self.logger = logger.bind(component="AnomalyDetectionService")
        
        # 异动检测阈值配置
        self.thresholds = {
            'volume_multiplier': 3.0,  # 成交量异常倍数
            'price_change_threshold': 7.0,  # 价格变动阈值
            'turnover_threshold': 20.0,  # 换手率阈值
            'concentration_threshold': 0.6,  # 席位集中度阈值
            'net_flow_threshold': 50000,  # 净流入阈值（万元）
            'continuous_days': 3  # 连续上榜天数
        }
    
    def _convert_df_to_list(self, result) -> List[Dict[str, Any]]:
        """将DataFrame转换为字典列表，并处理numpy类型"""
        if hasattr(result, 'empty') and result.empty:
            return []
        
        if hasattr(result, 'to_dict'):
            data_list = result.to_dict('records')
        else:
            data_list = result if isinstance(result, list) else []
        
        # 转换numpy类型为Python原生类型
        for item in data_list:
            for key, value in item.items():
                if value is None:
                    continue
                # 处理numpy数值类型
                if hasattr(value, 'item'):  # numpy类型都有item()方法
                    item[key] = value.item()
                # 处理日期类型
                elif hasattr(value, 'strftime'):
                    item[key] = value.strftime('%Y-%m-%d')
        
        return data_list
    
    async def detect_volume_anomalies(self, multiplier: float = 3.0) -> List[Dict[str, Any]]:
        """检测成交量异动
        
        Args:
            multiplier: 异常倍数阈值
        
        Returns:
            成交量异动列表
        """
        try:
            # 获取最近的交易日
            latest_date_query = "SELECT MAX(trade_date) as latest_date FROM ods_top_list"
            latest_result = self.db.query(latest_date_query)
            latest_result = self._convert_df_to_list(latest_result)
            
            if not latest_result or not latest_result[0].get('latest_date'):
                return []
            
            latest_date = latest_result[0]['latest_date']
            # 确保latest_date是date对象
            if isinstance(latest_date, str):
                latest_date = datetime.strptime(latest_date, '%Y-%m-%d').date()
            
            # 计算历史平均成交量并检测异动
            # 使用 stddevPop 替代 STDDEV 以兼容 ClickHouse
            query = """
            WITH stock_avg AS (
                SELECT 
                    ts_code,
                    AVG(amount) as avg_amount,
                    stddevPop(amount) as std_amount
                FROM ods_top_list
                WHERE trade_date >= %(start_date)s
                  AND trade_date < %(latest_date)s
                GROUP BY ts_code
                HAVING COUNT(*) >= 5
            ),
            current_data AS (
                SELECT 
                    ts_code,
                    name,
                    trade_date,
                    amount,
                    pct_chg,
                    turnover_rate,
                    net_amount,
                    reason
                FROM ods_top_list
                WHERE trade_date = %(latest_date)s
            )
            SELECT 
                c.ts_code,
                c.name,
                c.trade_date,
                c.amount,
                c.pct_chg,
                c.turnover_rate,
                c.net_amount,
                c.reason,
                s.avg_amount,
                s.std_amount,
                c.amount / s.avg_amount as volume_ratio
            FROM current_data c
            JOIN stock_avg s ON c.ts_code = s.ts_code
            WHERE c.amount > s.avg_amount * %(multiplier)s
              AND s.avg_amount > 0
            ORDER BY volume_ratio DESC
            """
            
            # 计算30天前的日期
            start_date = latest_date - timedelta(days=30)
            
            result = self.db.query(query, {
                "latest_date": latest_date,
                "start_date": start_date,
                "multiplier": multiplier
            })
            
            # 转换为字典列表
            result = self._convert_df_to_list(result)
            
            # 添加异动评级
            for item in result:
                ratio = float(item.get('volume_ratio', 1))
                if ratio >= 10:
                    item['severity'] = 'critical'
                elif ratio >= 5:
                    item['severity'] = 'high'
                elif ratio >= 3:
                    item['severity'] = 'medium'
                else:
                    item['severity'] = 'low'
                
                item['anomaly_type'] = 'volume_spike'
                item['description'] = f"成交量异常放大{ratio:.1f}倍"
            
            self.logger.info(f"Detected {len(result)} volume anomalies")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to detect volume anomalies: {e}")
            raise
    
    async def detect_seat_concentration_anomalies(self, threshold: float = 0.6) -> List[Dict[str, Any]]:
        """检测席位集中度异动
        
        Args:
            threshold: 集中度阈值
        
        Returns:
            席位集中度异动列表
        """
        try:
            # 获取最近的交易日
            latest_date_query = "SELECT MAX(trade_date) as latest_date FROM ods_top_inst"
            latest_result = self.db.query(latest_date_query)
            latest_result = self._convert_df_to_list(latest_result)
            
            if not latest_result or not latest_result[0].get('latest_date'):
                return []
            
            latest_date = latest_result[0]['latest_date']
            
            # 计算席位集中度
            query = """
            WITH seat_data AS (
                SELECT 
                    ts_code,
                    exalter,
                    ABS(net_buy) as abs_net_buy
                FROM ods_top_inst
                WHERE trade_date = %(latest_date)s
                  AND net_buy IS NOT NULL
            ),
            stock_totals AS (
                SELECT 
                    ts_code,
                    SUM(abs_net_buy) as total_flow
                FROM seat_data
                GROUP BY ts_code
                HAVING total_flow > 0
            ),
            concentration_calc AS (
                SELECT 
                    s.ts_code,
                    s.total_flow,
                    SUM(POW(sd.abs_net_buy / s.total_flow, 2)) as hhi_index,
                    COUNT(DISTINCT sd.exalter) as seat_count
                FROM stock_totals s
                JOIN seat_data sd ON s.ts_code = sd.ts_code
                GROUP BY s.ts_code, s.total_flow
            )
            SELECT 
                cc.ts_code,
                tl.name,
                tl.trade_date,
                tl.pct_chg,
                tl.turnover_rate,
                tl.net_amount,
                cc.hhi_index,
                cc.seat_count,
                cc.total_flow
            FROM concentration_calc cc
            JOIN ods_top_list tl ON cc.ts_code = tl.ts_code AND tl.trade_date = %(latest_date)s
            WHERE cc.hhi_index >= %(threshold)s
            ORDER BY cc.hhi_index DESC
            """
            
            result = self.db.query(query, {
                "latest_date": latest_date,
                "threshold": threshold
            })
            
            # 转换为字典列表
            result = self._convert_df_to_list(result)
            
            # 添加异动评级和描述
            for item in result:
                hhi = float(item.get('hhi_index', 0))
                seat_count = int(item.get('seat_count', 0))
                
                if hhi >= 0.8:
                    item['severity'] = 'critical'
                elif hhi >= 0.7:
                    item['severity'] = 'high'
                elif hhi >= 0.6:
                    item['severity'] = 'medium'
                else:
                    item['severity'] = 'low'
                
                item['anomaly_type'] = 'seat_concentration'
                item['description'] = f"席位高度集中(HHI={hhi:.3f}, {seat_count}个席位)"
            
            self.logger.info(f"Detected {len(result)} seat concentration anomalies")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to detect seat concentration anomalies: {e}")
            raise
    
    async def detect_price_momentum_anomalies(self, days: int = 5) -> List[Dict[str, Any]]:
        """检测价格动量异动
        
        Args:
            days: 检测天数
        
        Returns:
            价格动量异动列表
        """
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # 检测连续大幅波动
            # 使用小写 lag 函数以兼容 ClickHouse
            query = """
            WITH daily_changes AS (
                SELECT 
                    ts_code,
                    name,
                    trade_date,
                    pct_chg,
                    net_amount,
                    lag(pct_chg, 1) OVER (PARTITION BY ts_code ORDER BY trade_date) as prev_pct_chg,
                    lag(pct_chg, 2) OVER (PARTITION BY ts_code ORDER BY trade_date) as prev2_pct_chg
                FROM ods_top_list
                WHERE trade_date >= %(start_date)s
                  AND trade_date <= %(end_date)s
                ORDER BY ts_code, trade_date
            ),
            momentum_stocks AS (
                SELECT 
                    ts_code,
                    name,
                    trade_date,
                    pct_chg,
                    net_amount,
                    (pct_chg + COALESCE(prev_pct_chg, 0) + COALESCE(prev2_pct_chg, 0)) as cumulative_change,
                    ABS(pct_chg) + ABS(COALESCE(prev_pct_chg, 0)) + ABS(COALESCE(prev2_pct_chg, 0)) as volatility_sum
                FROM daily_changes
                WHERE ABS(pct_chg) >= 7
            )
            SELECT 
                ts_code,
                name,
                trade_date,
                pct_chg,
                net_amount,
                cumulative_change,
                volatility_sum
            FROM momentum_stocks
            WHERE ABS(cumulative_change) >= 15
               OR volatility_sum >= 25
            ORDER BY ABS(cumulative_change) DESC
            """
            
            result = self.db.query(query, {
                "start_date": start_date,
                "end_date": end_date
            })
            
            # 转换为字典列表
            result = self._convert_df_to_list(result)
            
            # 添加异动评级
            for item in result:
                cumulative = abs(float(item.get('cumulative_change', 0)))
                volatility = float(item.get('volatility_sum', 0))
                
                if cumulative >= 30 or volatility >= 40:
                    item['severity'] = 'critical'
                elif cumulative >= 20 or volatility >= 30:
                    item['severity'] = 'high'
                elif cumulative >= 15 or volatility >= 25:
                    item['severity'] = 'medium'
                else:
                    item['severity'] = 'low'
                
                item['anomaly_type'] = 'price_momentum'
                item['description'] = f"价格动量异常(累计变动{float(item.get('cumulative_change', 0)):.1f}%)"
            
            self.logger.info(f"Detected {len(result)} price momentum anomalies")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to detect price momentum anomalies: {e}")
            raise
    
    async def detect_institutional_behavior_anomalies(self) -> List[Dict[str, Any]]:
        """检测机构行为异动"""
        try:
            # 获取最近的交易日
            latest_date_query = "SELECT MAX(trade_date) as latest_date FROM ods_top_inst"
            latest_result = self.db.query(latest_date_query)
            latest_result = self._convert_df_to_list(latest_result)
            
            if not latest_result or not latest_result[0].get('latest_date'):
                return []
            
            latest_date = latest_result[0]['latest_date']
            
            # 检测机构异常大额交易
            query = """
            WITH inst_summary AS (
                SELECT 
                    ts_code,
                    SUM(CASE WHEN seat_type = 'institution' AND net_buy > 0 THEN net_buy ELSE 0 END) as inst_buy,
                    SUM(CASE WHEN seat_type = 'institution' AND net_buy < 0 THEN ABS(net_buy) ELSE 0 END) as inst_sell,
                    COUNT(CASE WHEN seat_type = 'institution' THEN 1 END) as inst_count
                FROM ods_top_inst
                WHERE trade_date = %(latest_date)s
                GROUP BY ts_code
                HAVING inst_count >= 2  -- 至少2个机构席位
            )
            SELECT 
                tl.ts_code,
                tl.name,
                tl.trade_date,
                tl.pct_chg,
                tl.net_amount,
                ins.inst_buy,
                ins.inst_sell,
                ins.inst_count,
                (ins.inst_buy - ins.inst_sell) as net_inst_flow
            FROM inst_summary ins
            JOIN ods_top_list tl ON ins.ts_code = tl.ts_code AND tl.trade_date = %(latest_date)s
            WHERE ABS(ins.inst_buy - ins.inst_sell) >= %(flow_threshold)s
            ORDER BY ABS(ins.inst_buy - ins.inst_sell) DESC
            """
            
            result = self.db.query(query, {
                "latest_date": latest_date,
                "flow_threshold": self.thresholds['net_flow_threshold']
            })
            
            # 转换为字典列表
            result = self._convert_df_to_list(result)
            
            # 添加异动评级
            for item in result:
                net_flow = abs(float(item.get('net_inst_flow', 0)))
                inst_count = int(item.get('inst_count', 0))
                
                if net_flow >= 200000 or inst_count >= 5:
                    item['severity'] = 'critical'
                elif net_flow >= 100000 or inst_count >= 4:
                    item['severity'] = 'high'
                elif net_flow >= 50000 or inst_count >= 3:
                    item['severity'] = 'medium'
                else:
                    item['severity'] = 'low'
                
                item['anomaly_type'] = 'institutional_behavior'
                direction = "净买入" if item['net_inst_flow'] > 0 else "净卖出"
                item['description'] = f"机构{direction}{net_flow/10000:.1f}万元({inst_count}个席位)"
            
            self.logger.info(f"Detected {len(result)} institutional behavior anomalies")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to detect institutional behavior anomalies: {e}")
            raise
    
    async def generate_anomaly_alerts(self) -> List[AnomalyAlert]:
        """生成异动预警
        
        Returns:
            异动预警列表
        """
        try:
            alerts = []
            
            # 收集各种异动检测结果
            volume_anomalies = await self.detect_volume_anomalies()
            concentration_anomalies = await self.detect_seat_concentration_anomalies()
            momentum_anomalies = await self.detect_price_momentum_anomalies()
            institutional_anomalies = await self.detect_institutional_behavior_anomalies()
            
            # 转换为统一的预警格式
            all_anomalies = [
                *volume_anomalies,
                *concentration_anomalies,
                *momentum_anomalies,
                *institutional_anomalies
            ]
            
            for anomaly in all_anomalies:
                alert = AnomalyAlert(
                    ts_code=anomaly['ts_code'],
                    name=anomaly['name'],
                    trade_date=str(anomaly['trade_date']),
                    anomaly_type=anomaly['anomaly_type'],
                    severity=anomaly['severity'],
                    description=anomaly['description'],
                    metrics={
                        'pct_chg': anomaly.get('pct_chg'),
                        'net_amount': anomaly.get('net_amount'),
                        'turnover_rate': anomaly.get('turnover_rate')
                    },
                    confidence=self._calculate_confidence(anomaly)
                )
                alerts.append(alert)
            
            # 按严重程度和置信度排序
            severity_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
            alerts.sort(
                key=lambda x: (severity_order.get(x.severity, 0), x.confidence),
                reverse=True
            )
            
            self.logger.info(f"Generated {len(alerts)} anomaly alerts")
            return alerts[:100]  # 返回前100个预警
            
        except Exception as e:
            self.logger.error(f"Failed to generate anomaly alerts: {e}")
            raise
    
    def _calculate_confidence(self, anomaly: Dict[str, Any]) -> float:
        """计算异动预警的置信度
        
        Args:
            anomaly: 异动数据
        
        Returns:
            置信度分数 (0-1)
        """
        confidence = 0.5  # 基础置信度
        
        # 根据异动类型调整置信度
        if anomaly['anomaly_type'] == 'volume_spike':
            ratio = anomaly.get('volume_ratio', 1)
            confidence += min(ratio / 10, 0.4)
        
        elif anomaly['anomaly_type'] == 'seat_concentration':
            hhi = anomaly.get('hhi_index', 0)
            confidence += min(hhi, 0.4)
        
        elif anomaly['anomaly_type'] == 'price_momentum':
            cumulative = abs(anomaly.get('cumulative_change', 0))
            confidence += min(cumulative / 50, 0.4)
        
        elif anomaly['anomaly_type'] == 'institutional_behavior':
            flow = abs(anomaly.get('net_inst_flow', 0))
            confidence += min(flow / 500000, 0.4)
        
        # 根据严重程度调整
        severity_bonus = {
            'critical': 0.1,
            'high': 0.05,
            'medium': 0.0,
            'low': -0.05
        }
        confidence += severity_bonus.get(anomaly.get('severity', 'medium'), 0)
        
        return max(0.0, min(1.0, confidence))