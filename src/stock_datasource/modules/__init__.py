"""Business modules for AI stock platform."""

from fastapi import APIRouter

def get_all_routers() -> list:
    """Get all module routers."""
    routers = []
    
    try:
        from .chat.router import router as chat_router
        routers.append(("/chat", chat_router, ["对话交互"]))
    except ImportError:
        pass
    
    try:
        from .market.router import router as market_router
        routers.append(("/market", market_router, ["行情分析"]))
    except ImportError:
        pass
    
    try:
        from .screener.router import router as screener_router
        routers.append(("/screener", screener_router, ["智能选股"]))
    except ImportError:
        pass
    
    try:
        from .report.router import router as report_router
        routers.append(("/report", report_router, ["财报研读"]))
    except ImportError:
        pass
    
    try:
        from .memory.router import router as memory_router
        routers.append(("/memory", memory_router, ["用户记忆"]))
    except ImportError:
        pass
    
    try:
        from .datamanage.router import router as datamanage_router
        routers.append(("/datamanage", datamanage_router, ["数据管理"]))
    except ImportError:
        pass
    
    try:
        from .portfolio.router import router as portfolio_router
        routers.append(("/portfolio", portfolio_router, ["持仓管理"]))
    except ImportError:
        pass
    
    try:
        from .backtest.router import router as backtest_router
        routers.append(("/backtest", backtest_router, ["策略回测"]))
    except ImportError:
        pass
    
    try:
        from .index.router import router as index_router
        routers.append(("/index", index_router, ["指数选股"]))
    except ImportError:
        pass
    
    return routers
