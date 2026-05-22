"""
策略管理 API 路由

功能:
- 策略列表（全部 / 按分类）
- 策略详情 + 参数Schema
- 策略参数验证
- 策略实例管理（创建/启停/删除）
- 运行中策略状态查询
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import logging

from strategies.registry import registry, get_strategy_class, create_strategy
from strategies.base import Strategy

logger = logging.getLogger(__name__)

router = APIRouter(tags=["策略管理"])


# ============================================================
# Request / Response 模型
# ============================================================

class ParamSchema(BaseModel):
    """参数Schema"""
    name: str
    type: str
    default: Any
    description: Optional[str] = None


class StrategyInfo(BaseModel):
    """策略信息"""
    name: str
    category: str
    version: str
    author: str
    description: str
    timeframes: List[str]
    params: Dict[str, Any]
    param_schema: Optional[List[ParamSchema]] = None


class StrategyListResponse(BaseModel):
    """策略列表响应"""
    total: int
    categories: List[str]
    strategies: List[StrategyInfo]


class StrategyDetailResponse(BaseModel):
    """策略详情响应"""
    name: str
    category: str
    version: str
    author: str
    description: str
    timeframes: List[str]
    params: Dict[str, Any]
    param_schema: List[ParamSchema]
    metadata: Dict[str, Any]


class CreateInstanceRequest(BaseModel):
    """创建策略实例请求"""
    strategy_name: str = Field(..., description="策略名称")
    instance_name: Optional[str] = Field(None, description="实例名称（可选，默认自动生成）")
    symbol: str = Field("BTCUSDT", description="交易对")
    timeframe: str = Field("1h", description="时间周期")
    params: Dict[str, Any] = Field(default_factory=dict, description="策略参数覆盖")
    auto_start: bool = Field(False, description="创建后是否自动启动")


class InstanceInfo(BaseModel):
    """策略实例信息"""
    instance_id: str
    strategy_name: str
    instance_name: str
    symbol: str
    timeframe: str
    params: Dict[str, Any]
    status: str  # created / running / stopped / error
    created_at: str
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    signals_generated: int = 0
    last_signal: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class InstanceListResponse(BaseModel):
    """策略实例列表响应"""
    total: int
    running: int
    stopped: int
    instances: List[InstanceInfo]


class UpdateInstanceParamsRequest(BaseModel):
    """更新实例参数请求"""
    params: Dict[str, Any] = Field(..., description="要更新的参数")


# ============================================================
# 策略实例管理器 (内存)
# ============================================================

class StrategyInstanceManager:
    """
    策略实例管理器
    
    管理策略的生命周期: 创建 → 启动 → 运行 → 停止 → 删除
    """
    
    def __init__(self):
        self._instances: Dict[str, dict] = {}
    
    def create_instance(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        params: Dict[str, Any],
        instance_name: Optional[str] = None,
    ) -> str:
        """创建策略实例"""
        strategy_class = get_strategy_class(strategy_name)
        if not strategy_class:
            raise ValueError(f"策略不存在: {strategy_name}")
        
        instance_id = str(uuid.uuid4())[:8]
        
        # 创建策略实例
        strategy_instance = create_strategy(strategy_name, params)
        
        if not instance_name:
            instance_name = f"{strategy_name}_{symbol}_{instance_id}"
        
        self._instances[instance_id] = {
            "instance_id": instance_id,
            "strategy_name": strategy_name,
            "instance_name": instance_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "params": strategy_instance.params.copy(),
            "strategy": strategy_instance,
            "status": "created",
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "stopped_at": None,
            "signals_generated": 0,
            "last_signal": None,
            "error": None,
        }
        
        logger.info(f"✅ 策略实例已创建: {instance_name} [{instance_id}]")
        return instance_id
    
    def start_instance(self, instance_id: str) -> bool:
        """启动策略实例"""
        if instance_id not in self._instances:
            raise ValueError(f"实例不存在: {instance_id}")
        
        inst = self._instances[instance_id]
        if inst["status"] == "running":
            return True  # 已经在运行
        
        inst["status"] = "running"
        inst["started_at"] = datetime.now().isoformat()
        inst["stopped_at"] = None
        inst["error"] = None
        
        logger.info(f"▶️ 策略实例已启动: {inst['instance_name']} [{instance_id}]")
        return True
    
    def stop_instance(self, instance_id: str) -> bool:
        """停止策略实例"""
        if instance_id not in self._instances:
            raise ValueError(f"实例不存在: {instance_id}")
        
        inst = self._instances[instance_id]
        if inst["status"] == "stopped":
            return True
        
        inst["status"] = "stopped"
        inst["stopped_at"] = datetime.now().isoformat()
        
        logger.info(f"⏹️ 策略实例已停止: {inst['instance_name']} [{instance_id}]")
        return True
    
    def delete_instance(self, instance_id: str) -> bool:
        """删除策略实例"""
        if instance_id not in self._instances:
            raise ValueError(f"实例不存在: {instance_id}")
        
        inst = self._instances.pop(instance_id)
        logger.info(f"🗑️ 策略实例已删除: {inst['instance_name']} [{instance_id}]")
        return True
    
    def update_params(self, instance_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """更新策略参数"""
        if instance_id not in self._instances:
            raise ValueError(f"实例不存在: {instance_id}")
        
        inst = self._instances[instance_id]
        strategy: Strategy = inst["strategy"]
        strategy.set_params(params)
        inst["params"] = strategy.params.copy()
        
        logger.info(f"🔧 策略参数已更新: {inst['instance_name']} [{instance_id}]")
        return inst["params"]
    
    def get_instance(self, instance_id: str) -> Optional[dict]:
        """获取实例信息"""
        return self._instances.get(instance_id)
    
    def list_instances(
        self,
        status: Optional[str] = None,
        strategy_name: Optional[str] = None,
    ) -> List[dict]:
        """列出实例"""
        instances = list(self._instances.values())
        
        if status:
            instances = [i for i in instances if i["status"] == status]
        if strategy_name:
            instances = [i for i in instances if i["strategy_name"] == strategy_name]
        
        return instances
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        all_instances = list(self._instances.values())
        return {
            "total": len(all_instances),
            "running": sum(1 for i in all_instances if i["status"] == "running"),
            "stopped": sum(1 for i in all_instances if i["status"] == "stopped"),
            "created": sum(1 for i in all_instances if i["status"] == "created"),
            "error": sum(1 for i in all_instances if i["status"] == "error"),
        }


# 全局实例管理器
_instance_manager = StrategyInstanceManager()


def get_instance_manager() -> StrategyInstanceManager:
    """获取策略实例管理器"""
    return _instance_manager


# ============================================================
# 工具函数
# ============================================================

def _build_param_schema(params: Dict[str, Any]) -> List[ParamSchema]:
    """从策略默认参数构建参数Schema"""
    schema = []
    for name, value in params.items():
        param_type = type(value).__name__
        # 推断描述
        description = _infer_param_description(name)
        schema.append(ParamSchema(
            name=name,
            type=param_type,
            default=value,
            description=description,
        ))
    return schema


def _infer_param_description(name: str) -> str:
    """从参数名推断描述"""
    descriptions = {
        "fast_period": "快线周期",
        "slow_period": "慢线周期",
        "stop_loss_pct": "止损百分比",
        "take_profit_pct": "止盈百分比",
        "use_ema": "是否使用EMA",
        "min_strength": "最小信号强度",
        "lookback_days": "回溯天数",
        "k1": "上轨系数",
        "k2": "下轨系数",
        "grid_count": "网格数量",
        "grid_type": "网格类型 (arithmetic/geometric)",
        "upper_price": "网格上界",
        "lower_price": "网格下界",
        "rsi_period": "RSI 周期",
        "oversold": "超卖阈值",
        "overbought": "超买阈值",
        "bb_period": "布林带周期",
        "bb_std": "布林带标准差倍数",
        "atr_period": "ATR 周期",
        "atr_multiplier": "ATR 倍数",
        "trail_pct": "移动止损百分比",
        "volume_confirm": "成交量确认",
        "trend_filter": "趋势过滤",
        "auto_range_period": "自动区间计算回溯周期",
        "order_size_pct": "每笔下单占比",
        "max_grids_one_side": "单边最大持仓格数",
    }
    return descriptions.get(name, name.replace("_", " "))


def _strategy_to_info(strategy_class: type) -> StrategyInfo:
    """将策略类转换为策略信息"""
    instance = strategy_class()
    return StrategyInfo(
        name=instance.name,
        category=instance.category,
        version=instance.version,
        author=instance.author,
        description=instance.description,
        timeframes=instance.timeframes,
        params=instance.params,
        param_schema=_build_param_schema(instance.params),
    )


def _instance_to_info(inst: dict) -> InstanceInfo:
    """将实例字典转换为响应模型"""
    return InstanceInfo(
        instance_id=inst["instance_id"],
        strategy_name=inst["strategy_name"],
        instance_name=inst["instance_name"],
        symbol=inst["symbol"],
        timeframe=inst["timeframe"],
        params=inst["params"],
        status=inst["status"],
        created_at=inst["created_at"],
        started_at=inst.get("started_at"),
        stopped_at=inst.get("stopped_at"),
        signals_generated=inst.get("signals_generated", 0),
        last_signal=inst.get("last_signal"),
        error=inst.get("error"),
    )


# ============================================================
# API 端点 - 策略目录
# ============================================================

@router.get("/list", response_model=StrategyListResponse)
async def list_strategies(
    category: Optional[str] = Query(None, description="按分类筛选 (trend/momentum/mean_reversion/volatility/market_making/composite)"),
):
    """
    获取所有可用策略
    
    支持按分类筛选：
    - trend: 趋势策略
    - momentum: 动量策略
    - mean_reversion: 均值回归策略
    - volatility: 波动率策略
    - market_making: 做市策略
    - composite: 组合策略
    """
    all_strategies = registry.list_all()
    
    if category:
        strategies_list = registry.list_by_category(category)
    else:
        strategies_list = list(all_strategies.values())
    
    strategies_info = []
    for strategy_class in strategies_list:
        try:
            info = _strategy_to_info(strategy_class)
            strategies_info.append(info)
        except Exception as e:
            logger.warning(f"策略信息获取失败 ({strategy_class.__name__}): {e}")
    
    return StrategyListResponse(
        total=len(strategies_info),
        categories=registry.list_categories(),
        strategies=strategies_info,
    )


@router.get("/categories")
async def list_categories():
    """获取所有策略分类"""
    categories = registry.list_categories()
    
    # 分类描述
    category_descriptions = {
        "trend": "趋势策略 - 跟随市场趋势方向交易",
        "momentum": "动量策略 - 基于价格动量和突破",
        "mean_reversion": "均值回归策略 - 价格偏离均值后回归",
        "volatility": "波动率策略 - 利用波动率变化获利",
        "market_making": "做市策略 - 提供流动性赚取价差",
        "composite": "组合策略 - 多策略组合使用",
    }
    
    result = []
    for cat in categories:
        cat_strategies = registry.list_by_category(cat)
        result.append({
            "name": cat,
            "description": category_descriptions.get(cat, cat),
            "strategy_count": len(cat_strategies),
            "strategies": [s.name for s in cat_strategies],
        })
    
    return {"categories": result, "total": len(categories)}


@router.get("/detail/{strategy_name}", response_model=StrategyDetailResponse)
async def get_strategy_detail(strategy_name: str):
    """
    获取策略详情
    
    包含完整参数Schema、默认值和描述
    """
    strategy_class = get_strategy_class(strategy_name)
    
    if not strategy_class:
        raise HTTPException(
            status_code=404,
            detail=f"策略不存在: {strategy_name}。可用策略: {list(registry.list_all().keys())}",
        )
    
    instance = strategy_class()
    param_schema = _build_param_schema(instance.params)
    
    return StrategyDetailResponse(
        name=instance.name,
        category=instance.category,
        version=instance.version,
        author=instance.author,
        description=instance.description,
        timeframes=instance.timeframes,
        params=instance.params,
        param_schema=param_schema,
        metadata=instance.get_metadata(),
    )


@router.post("/{strategy_name}/validate")
async def validate_strategy_params(strategy_name: str, params: Dict[str, Any]):
    """
    验证策略参数
    
    检查参数类型和范围是否合法
    """
    strategy_class = get_strategy_class(strategy_name)
    
    if not strategy_class:
        raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_name}")
    
    try:
        # 创建实例测试参数
        instance = strategy_class(params)
        
        # 验证通过
        return {
            "valid": True,
            "strategy_name": strategy_name,
            "resolved_params": instance.params,
            "message": "参数验证通过",
        }
        
    except Exception as e:
        return {
            "valid": False,
            "strategy_name": strategy_name,
            "error": str(e),
            "message": "参数验证失败",
        }


@router.post("/{strategy_name}/preview")
async def preview_strategy(strategy_name: str, params: Dict[str, Any] = None):
    """
    预览策略配置（不执行）
    
    返回策略将使用的完整配置，用于确认后再创建实例
    """
    strategy_class = get_strategy_class(strategy_name)
    
    if not strategy_class:
        raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_name}")
    
    try:
        instance = strategy_class(params)
        return {
            "strategy_name": strategy_name,
            "category": instance.category,
            "description": instance.description,
            "resolved_params": instance.params,
            "timeframes": instance.timeframes,
            "ready": True,
        }
    except Exception as e:
        return {
            "strategy_name": strategy_name,
            "error": str(e),
            "ready": False,
        }


# ============================================================
# API 端点 - 策略实例管理
# ============================================================

@router.post("/instances/create")
async def create_strategy_instance(request: CreateInstanceRequest):
    """
    创建策略实例
    
    将策略配置为可运行的实例，绑定到特定交易对和时间周期
    """
    manager = get_instance_manager()
    
    try:
        instance_id = manager.create_instance(
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            params=request.params,
            instance_name=request.instance_name,
        )
        
        # 自动启动
        if request.auto_start:
            manager.start_instance(instance_id)
        
        inst = manager.get_instance(instance_id)
        return {
            "success": True,
            "message": f"策略实例已创建: {inst['instance_name']}",
            "instance": _instance_to_info(inst),
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("创建策略实例失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances", response_model=InstanceListResponse)
async def list_instances(
    status: Optional[str] = Query(None, description="按状态筛选 (created/running/stopped/error)"),
    strategy_name: Optional[str] = Query(None, description="按策略名称筛选"),
):
    """获取所有策略实例"""
    manager = get_instance_manager()
    instances = manager.list_instances(status=status, strategy_name=strategy_name)
    stats = manager.get_stats()
    
    return InstanceListResponse(
        total=stats["total"],
        running=stats["running"],
        stopped=stats["stopped"],
        instances=[_instance_to_info(i) for i in instances],
    )


@router.get("/instances/{instance_id}")
async def get_instance_detail(instance_id: str):
    """获取策略实例详情"""
    manager = get_instance_manager()
    inst = manager.get_instance(instance_id)
    
    if not inst:
        raise HTTPException(status_code=404, detail=f"实例不存在: {instance_id}")
    
    return {
        "instance": _instance_to_info(inst),
        "strategy_detail": {
            "category": inst["strategy"].category,
            "description": inst["strategy"].description,
            "version": inst["strategy"].version,
        },
    }


@router.post("/instances/{instance_id}/start")
async def start_instance(instance_id: str):
    """启动策略实例"""
    manager = get_instance_manager()
    
    try:
        manager.start_instance(instance_id)
        inst = manager.get_instance(instance_id)
        return {
            "success": True,
            "message": f"策略实例已启动: {inst['instance_name']}",
            "instance": _instance_to_info(inst),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/instances/{instance_id}/stop")
async def stop_instance(instance_id: str):
    """停止策略实例"""
    manager = get_instance_manager()
    
    try:
        manager.stop_instance(instance_id)
        inst = manager.get_instance(instance_id)
        return {
            "success": True,
            "message": f"策略实例已停止: {inst['instance_name']}",
            "instance": _instance_to_info(inst),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/instances/{instance_id}/params")
async def update_instance_params(instance_id: str, request: UpdateInstanceParamsRequest):
    """
    更新策略实例参数
    
    运行中的实例参数更新后立即生效
    """
    manager = get_instance_manager()
    
    try:
        new_params = manager.update_params(instance_id, request.params)
        inst = manager.get_instance(instance_id)
        return {
            "success": True,
            "message": "参数已更新",
            "instance": _instance_to_info(inst),
            "updated_params": new_params,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str):
    """
    删除策略实例
    
    运行中的实例会先停止再删除
    """
    manager = get_instance_manager()
    
    inst = manager.get_instance(instance_id)
    if not inst:
        raise HTTPException(status_code=404, detail=f"实例不存在: {instance_id}")
    
    # 运行中先停止
    if inst["status"] == "running":
        manager.stop_instance(instance_id)
    
    instance_name = inst["instance_name"]
    manager.delete_instance(instance_id)
    
    return {
        "success": True,
        "message": f"策略实例已删除: {instance_name}",
    }


# ============================================================
# API 端点 - 统计与概览
# ============================================================

@router.get("/stats")
async def get_strategy_stats():
    """
    获取策略系统统计
    
    包含可用策略数、运行实例数等
    """
    manager = get_instance_manager()
    instance_stats = manager.get_stats()
    
    all_strategies = registry.list_all()
    categories = registry.list_categories()
    
    return {
        "available_strategies": len(all_strategies),
        "categories": len(categories),
        "category_breakdown": {
            cat: len(registry.list_by_category(cat))
            for cat in categories
        },
        "instances": instance_stats,
    }
