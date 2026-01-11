"""
策略注册中心

管理所有策略的注册、查询和实例化。
支持内置策略和AI生成策略的统一管理。
"""

import logging
from typing import Dict, List, Type, Optional, Any
from datetime import datetime

from .base import BaseStrategy, AIGeneratedStrategy, StrategyCategory, StrategyMetadata

logger = logging.getLogger(__name__)


class StrategyInfo:
    """策略信息类"""
    
    def __init__(self, strategy_class: Type[BaseStrategy], metadata: StrategyMetadata):
        self.strategy_class = strategy_class
        self.metadata = metadata
        self.usage_count = 0
        self.last_used = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.metadata.id,
            'name': self.metadata.name,
            'description': self.metadata.description,
            'category': self.metadata.category.value,
            'author': self.metadata.author,
            'version': self.metadata.version,
            'tags': self.metadata.tags,
            'risk_level': self.metadata.risk_level.value,
            'is_ai_generated': self.metadata.is_ai_generated,
            'usage_count': self.usage_count,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'created_at': self.metadata.created_at.isoformat()
        }


class StrategyRegistry:
    """
    策略注册中心
    
    负责管理所有策略的注册、查询和实例化。
    支持内置策略和AI生成策略的统一管理。
    """
    
    def __init__(self):
        """初始化注册中心"""
        self._strategies: Dict[str, StrategyInfo] = {}
        self._ai_strategies: Dict[str, AIGeneratedStrategy] = {}
        self._categories: Dict[StrategyCategory, List[str]] = {
            category: [] for category in StrategyCategory
        }
        
        logger.info("Strategy registry initialized")
    
    def register_strategy(self, strategy_id: str, strategy_class: Type[BaseStrategy], overwrite: bool = False) -> bool:
        """
        注册策略（通用方法）
        
        Args:
            strategy_id: 策略ID（可选，如果不提供则使用策略类的元数据ID）
            strategy_class: 策略类
            overwrite: 是否覆盖已存在的策略
            
        Returns:
            注册是否成功
        """
        try:
            # 创建临时实例获取元数据
            temp_instance = strategy_class()
            metadata = temp_instance.metadata
            
            # 使用提供的ID或元数据中的ID
            actual_id = strategy_id or metadata.id
            
            # 检查ID冲突
            if actual_id in self._strategies and not overwrite:
                logger.warning(f"Strategy ID {actual_id} already exists, use overwrite=True to replace")
                return False
            
            # 如果覆盖，先移除旧策略
            if actual_id in self._strategies and overwrite:
                self.remove_strategy(actual_id)
            
            # 更新元数据ID
            metadata.id = actual_id
            
            # 创建策略信息
            strategy_info = StrategyInfo(strategy_class, metadata)
            
            # 注册策略
            self._strategies[actual_id] = strategy_info
            self._categories[metadata.category].append(actual_id)
            
            logger.info(f"Registered strategy: {metadata.name} ({actual_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register strategy {strategy_class.__name__}: {e}")
            return False
    
    def register_builtin_strategy(self, strategy_class: Type[BaseStrategy]) -> bool:
        """
        注册内置策略
        
        Args:
            strategy_class: 策略类
            
        Returns:
            注册是否成功
        """
        try:
            # 创建临时实例获取元数据
            temp_instance = strategy_class()
            metadata = temp_instance.metadata
            
            # 检查ID冲突
            if metadata.id in self._strategies:
                logger.warning(f"Strategy ID {metadata.id} already exists, skipping registration")
                return False
            
            # 创建策略信息
            strategy_info = StrategyInfo(strategy_class, metadata)
            
            # 注册策略
            self._strategies[metadata.id] = strategy_info
            self._categories[metadata.category].append(metadata.id)
            
            logger.info(f"Registered builtin strategy: {metadata.name} ({metadata.id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register strategy {strategy_class.__name__}: {e}")
            return False
    
    def register_ai_strategy(self, strategy: AIGeneratedStrategy) -> bool:
        """
        注册AI生成策略
        
        Args:
            strategy: AI生成的策略实例
            
        Returns:
            注册是否成功
        """
        try:
            strategy_id = strategy.metadata.id
            
            # 检查ID冲突
            if strategy_id in self._ai_strategies:
                logger.warning(f"AI strategy ID {strategy_id} already exists, updating")
            
            # 注册AI策略
            self._ai_strategies[strategy_id] = strategy
            
            # 同时在主注册表中注册
            strategy_info = StrategyInfo(type(strategy), strategy.metadata)
            self._strategies[strategy_id] = strategy_info
            self._categories[StrategyCategory.AI_GENERATED].append(strategy_id)
            
            logger.info(f"Registered AI strategy: {strategy.metadata.name} ({strategy_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register AI strategy: {e}")
            return False
    
    def get_strategy_class(self, strategy_id: str) -> Optional[Type[BaseStrategy]]:
        """
        获取策略类
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            策略类，如果不存在返回None
        """
        if strategy_id in self._strategies:
            return self._strategies[strategy_id].strategy_class
        return None
    
    def get_all_strategies(self) -> Dict[str, Type[BaseStrategy]]:
        """
        获取所有策略类
        
        Returns:
            策略ID到策略类的映射
        """
        return {
            strategy_id: info.strategy_class 
            for strategy_id, info in self._strategies.items()
        }
    
    def get_strategy(self, strategy_id: str, params: Dict[str, Any] = None) -> Optional[BaseStrategy]:
        """
        获取策略实例
        
        Args:
            strategy_id: 策略ID
            params: 策略参数
            
        Returns:
            策略实例，如果不存在返回None
        """
        try:
            # 检查AI策略
            if strategy_id in self._ai_strategies:
                ai_strategy = self._ai_strategies[strategy_id]
                if params:
                    # 创建新实例并应用参数
                    new_strategy = ai_strategy.__class__(params, ai_strategy.generation_info)
                    return new_strategy
                return ai_strategy
            
            # 检查内置策略
            if strategy_id in self._strategies:
                strategy_info = self._strategies[strategy_id]
                
                # 更新使用统计
                strategy_info.usage_count += 1
                strategy_info.last_used = datetime.now()
                
                # 创建实例
                return strategy_info.strategy_class(params)
            
            logger.warning(f"Strategy not found: {strategy_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get strategy {strategy_id}: {e}")
            return None
    
    def list_strategies(self, 
                       category: Optional[StrategyCategory] = None,
                       tags: Optional[List[str]] = None,
                       author: Optional[str] = None,
                       include_ai: bool = True) -> List[Dict[str, Any]]:
        """
        列出策略
        
        Args:
            category: 策略分类过滤
            tags: 标签过滤
            author: 作者过滤
            include_ai: 是否包含AI策略
            
        Returns:
            策略信息列表
        """
        strategies = []
        
        for strategy_id, strategy_info in self._strategies.items():
            metadata = strategy_info.metadata
            
            # 分类过滤
            if category and metadata.category != category:
                continue
            
            # AI策略过滤
            if not include_ai and metadata.is_ai_generated:
                continue
            
            # 标签过滤
            if tags and not any(tag in metadata.tags for tag in tags):
                continue
            
            # 作者过滤
            if author and metadata.author != author:
                continue
            
            strategies.append(strategy_info.to_dict())
        
        # 按使用次数和创建时间排序
        strategies.sort(key=lambda x: (x['usage_count'], x['created_at']), reverse=True)
        
        return strategies
    
    def get_categories(self) -> Dict[str, int]:
        """
        获取策略分类统计
        
        Returns:
            分类及其策略数量
        """
        return {
            category.value: len(strategy_ids)
            for category, strategy_ids in self._categories.items()
            if strategy_ids
        }
    
    def search_strategies(self, query: str) -> List[Dict[str, Any]]:
        """
        搜索策略
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的策略列表
        """
        query_lower = query.lower()
        results = []
        
        for strategy_info in self._strategies.values():
            metadata = strategy_info.metadata
            
            # 搜索名称、描述、标签
            if (query_lower in metadata.name.lower() or
                query_lower in metadata.description.lower() or
                any(query_lower in tag.lower() for tag in metadata.tags)):
                
                result = strategy_info.to_dict()
                results.append(result)
        
        return results
    
    def get_popular_strategies(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取热门策略
        
        Args:
            limit: 返回数量限制
            
        Returns:
            热门策略列表
        """
        strategies = list(self._strategies.values())
        strategies.sort(key=lambda x: x.usage_count, reverse=True)
        
        return [info.to_dict() for info in strategies[:limit]]
    
    def get_recent_strategies(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近创建的策略
        
        Args:
            limit: 返回数量限制
            
        Returns:
            最近策略列表
        """
        strategies = list(self._strategies.values())
        strategies.sort(key=lambda x: x.metadata.created_at, reverse=True)
        
        return [info.to_dict() for info in strategies[:limit]]
    
    def remove_strategy(self, strategy_id: str) -> bool:
        """
        移除策略
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            移除是否成功
        """
        try:
            if strategy_id in self._strategies:
                strategy_info = self._strategies[strategy_id]
                category = strategy_info.metadata.category
                
                # 从主注册表移除
                del self._strategies[strategy_id]
                
                # 从分类中移除
                if strategy_id in self._categories[category]:
                    self._categories[category].remove(strategy_id)
                
                # 如果是AI策略，也从AI注册表移除
                if strategy_id in self._ai_strategies:
                    del self._ai_strategies[strategy_id]
                
                logger.info(f"Removed strategy: {strategy_id}")
                return True
            
            logger.warning(f"Strategy not found for removal: {strategy_id}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to remove strategy {strategy_id}: {e}")
            return False
    
    def get_strategy_count(self) -> Dict[str, int]:
        """
        获取策略统计信息
        
        Returns:
            策略统计字典
        """
        total_strategies = len(self._strategies)
        ai_strategies = len(self._ai_strategies)
        builtin_strategies = total_strategies - ai_strategies
        
        return {
            'total': total_strategies,
            'builtin': builtin_strategies,
            'ai_generated': ai_strategies,
            'categories': self.get_categories()
        }
    
    def validate_strategy_id(self, strategy_id: str) -> bool:
        """
        验证策略ID是否存在
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否存在
        """
        return strategy_id in self._strategies
    
    def get_strategy_metadata(self, strategy_id: str) -> Optional[StrategyMetadata]:
        """
        获取策略元数据
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            策略元数据，如果不存在返回None
        """
        if strategy_id in self._strategies:
            return self._strategies[strategy_id].metadata
        return None


# 全局策略注册中心实例
strategy_registry = StrategyRegistry()