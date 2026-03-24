#!/usr/bin/env python3
"""
AI Agent 实时股票数据订阅演示
================================

展示AI agent如何通过stock-rt-subscribe skill获取实时股票数据，
包括鉴权引导、订阅管理、数据接收和智能分析。

使用步骤:
1. 引导用户设置环境变量
2. 启动WebSocket订阅服务
3. 连接服务接收实时数据
4. 分析数据变化并生成报告
5. 提供智能投资建议

运行方式:
    python3 ai_agent_demo.py
"""

import asyncio
import os
import sys
import time
from datetime import datetime

# 添加当前目录到路径，以便导入自定义模块
sys.path.insert(0, os.path.dirname(__file__))

from ai_agent_integration import StockDataAgent


class AIStockAnalyst:
    """AI股票分析师 - 演示AI agent的智能分析能力"""
    
    def __init__(self):
        self.agent = StockDataAgent()
        self.analysis_results = {}
        
    def print_welcome(self):
        """打印欢迎信息"""
        print("🤖" + "="*60)
        print("🤖 AI Agent 实时股票数据分析系统")
        print("🤖" + "="*60)
        print("\n📈 本系统将为您提供:")
        print("   • 实时股票行情监控")
        print("   • 价格变化统计分析")
        print("   • 智能投资建议")
        print("   • 风险预警提示")
        print()
    
    def guide_setup(self) -> bool:
        """引导用户完成设置"""
        print("🔧 系统设置引导")
        print("-" * 40)
        
        # 检查环境变量
        node_url = os.getenv("STOCK_RT_NODE_URL")
        
        if not node_url:
            print("❌ 检测到未设置股票数据源")
            print("💡 请执行以下命令设置数据源:")
            print("   export STOCK_RT_NODE_URL=\"http://139.155.0.115:9100\"")
            print("\n📝 或者直接在脚本中设置:")
            print("   os.environ['STOCK_RT_NODE_URL'] = 'http://139.155.0.115:9100'")
            return False
        
        print(f"✅ 数据源已设置: {node_url}")
        
        # 检查Token（可选）
        token = os.getenv("STOCK_RT_TOKEN")
        if token:
            print(f"✅ 鉴权Token已设置")
        else:
            print("⚠️  未设置鉴权Token（如果需要）")
        
        return True
    
    def select_stocks(self) -> list:
        """选择要监控的股票"""
        print("\n📊 选择监控股票")
        print("-" * 40)
        
        # 预定义的股票池
        stock_pool = {
            "港股科技": ["00700.HK", "09988.HK", "09888.HK", "09618.HK"],
            "A股蓝筹": ["600519.SH", "000858.SZ", "601318.SH", "000001.SZ"],
            "新能源": ["300750.SZ", "002594.SZ", "601012.SH"],
            "金融": ["601398.SH", "601939.SH", "601988.SH"]
        }
        
        print("可选股票池:")
        for i, (category, stocks) in enumerate(stock_pool.items(), 1):
            print(f"  {i}. {category}: {', '.join(stocks)}")
        
        print("\n💡 建议选择:")
        print("   1. 港股科技 + A股蓝筹 (推荐)")
        print("   2. 新能源 + 金融 (分散投资)")
        
        # 默认选择
        selected_stocks = stock_pool["港股科技"] + stock_pool["A股蓝筹"]
        print(f"\n✅ 默认选择: {', '.join(selected_stocks)}")
        
        return selected_stocks
    
    def on_realtime_data(self, data: dict):
        """实时数据回调函数 - AI agent的智能分析"""
        symbol = data["ts_code"]
        name = data["name"]
        price = data["close"]
        change = data["pct_chg"]
        volume = data["vol"]
        amount = data["amount"]
        
        # AI分析逻辑
        analysis = self.analyze_single_tick(data)
        
        if analysis["alert_level"] == "high":
            print(f"🚨 {symbol} {name}: {analysis['message']}")
        elif analysis["alert_level"] == "medium":
            print(f"⚠️  {symbol} {name}: {analysis['message']}")
        else:
            print(f"📊 {symbol} {name}: {price:.2f}元 ({change:+.2f}%)")
    
    def analyze_single_tick(self, data: dict) -> dict:
        """分析单条tick数据"""
        symbol = data["ts_code"]
        change = data["pct_chg"]
        volume = data["vol"]
        amount = data["amount"]
        
        # 基于规则的分析
        if abs(change) > 5.0:
            return {
                "alert_level": "high",
                "message": f"大幅波动! {change:+.2f}%，建议关注"
            }
        elif abs(change) > 2.0:
            return {
                "alert_level": "medium", 
                "message": f"明显波动 {change:+.2f}%，持续观察"
            }
        elif amount > 1e9:  # 成交额超过10亿
            return {
                "alert_level": "medium",
                "message": f"成交活跃 {amount/1e8:.1f}亿，资金关注度高"
            }
        else:
            return {
                "alert_level": "low",
                "message": "正常波动"
            }
    
    def generate_investment_advice(self, analysis_results: dict):
        """生成投资建议"""
        print("\n💡 AI 投资建议")
        print("=" * 50)
        
        if not analysis_results:
            print("⚠️  无足够数据生成投资建议")
            return
        
        # 分析股票表现
        best_performers = []
        worst_performers = []
        
        for symbol, analysis in analysis_results.items():
            if "error" in analysis or "status" in analysis:
                continue
                
            change_pct = analysis["total_change_pct"]
            volatility = analysis["volatility"]
            
            if change_pct > 0:
                best_performers.append((symbol, analysis["name"], change_pct))
            else:
                worst_performers.append((symbol, analysis["name"], change_pct))
        
        # 排序
        best_performers.sort(key=lambda x: x[2], reverse=True)
        worst_performers.sort(key=lambda x: x[2])
        
        # 生成建议
        if best_performers:
            print("📈 表现优异股票:")
            for symbol, name, change in best_performers[:3]:
                print(f"   ✅ {name}({symbol}): +{change:.2f}% - 可考虑持有或加仓")
        
        if worst_performers:
            print("\n📉 表现不佳股票:")
            for symbol, name, change in worst_performers[:3]:
                print(f"   ⚠️  {name}({symbol}): {change:.2f}% - 建议谨慎观察")
        
        # 总体建议
        total_stocks = len(analysis_results)
        positive_stocks = len(best_performers)
        positive_ratio = positive_stocks / total_stocks if total_stocks > 0 else 0
        
        print(f"\n📊 总体市场分析:")
        print(f"   监控股票: {total_stocks} 只")
        print(f"   上涨股票: {positive_stocks} 只 ({positive_ratio:.1%})")
        
        if positive_ratio > 0.6:
            print("   🌟 市场情绪积极，可考虑适度投资")
        elif positive_ratio > 0.4:
            print("   ⚖️  市场分化明显，建议精选个股")
        else:
            print("   💤 市场情绪偏弱，建议观望为主")
    
    async def run_complete_analysis(self, duration: int = 60):
        """运行完整的AI分析流程"""
        
        # 1. 欢迎和设置引导
        self.print_welcome()
        
        if not self.guide_setup():
            print("❌ 系统设置未完成，无法继续")
            return
        
        # 2. 选择股票
        selected_stocks = self.select_stocks()
        
        # 3. 启动订阅服务
        print(f"\n🚀 启动实时数据订阅...")
        if not self.agent.start_subscription(selected_stocks, alert_threshold=2.0):
            print("❌ 订阅服务启动失败")
            return
        
        # 4. 设置数据回调
        self.agent.set_data_callback(self.on_realtime_data)
        
        # 5. 接收和分析数据
        print(f"\n📡 开始接收 {duration} 秒实时数据...")
        print("-" * 50)
        
        stock_data = await self.agent.receive_realtime_data(
            duration=duration, 
            on_tick=self.on_realtime_data
        )
        
        # 6. 生成分析报告
        print("\n📊 数据分析中...")
        analysis_results = self.agent.analyze_stock_changes(stock_data)
        self.agent.print_analysis_report(analysis_results)
        
        # 7. AI投资建议
        self.generate_investment_advice(analysis_results)
        
        # 8. 清理资源
        self.agent.stop_subscription()
        
        print("\n✅ AI分析完成!")
        print("💡 提示: 可调整监控时长或股票组合进行更深入分析")


async def main():
    """主函数"""
    analyst = AIStockAnalyst()
    
    try:
        # 运行30秒的演示分析
        await analyst.run_complete_analysis(duration=30)
        
    except KeyboardInterrupt:
        print("\n\n🛑 用户中断分析")
        analyst.agent.stop_subscription()
    except Exception as e:
        print(f"\n❌ 分析过程中出现错误: {e}")
        analyst.agent.stop_subscription()


if __name__ == "__main__":
    # 运行演示
    asyncio.run(main())