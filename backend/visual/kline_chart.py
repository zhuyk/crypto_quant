"""
K 线图表 - TradingView 风格
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CandleData:
    """K 线数据"""
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class KlineChart:
    """
    K 线图表生成器
    
    生成 TradingView 风格的 K 线图配置
    """
    
    def __init__(self):
        """初始化图表生成器"""
        self._indicators = []
    
    def add_indicator(
        self,
        name: str,
        type: str,
        params: dict,
        color: str = "#000000",
    ):
        """
        添加技术指标
        
        Args:
            name: 指标名称
            type: 指标类型 (MA/EMA/RSI/MACD/BOLL)
            params: 参数
            color: 颜色
        """
        self._indicators.append({
            'name': name,
            'type': type,
            'params': params,
            'color': color,
        })
    
    def generate_config(
        self,
        symbol: str,
        timeframe: str,
        width: int = 800,
        height: int = 600,
        theme: str = "light",
    ) -> dict:
        """
        生成图表配置
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            width: 宽度
            height: 高度
            theme: 主题
            
        Returns:
            dict: 图表配置
        """
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'width': width,
            'height': height,
            'theme': theme,
            'indicators': self._indicators.copy(),
            'chart_type': 'candlestick',
            'show_volume': True,
        }
    
    def prepare_data(
        self,
        klines: List[dict],
        indicators: Optional[Dict] = None,
    ) -> dict:
        """
        准备图表数据
        
        Args:
            klines: K 线数据
            indicators: 指标数据
            
        Returns:
            dict: 图表数据
        """
        candles = [
            CandleData(
                time=k['time'],
                open=float(k['open']),
                high=float(k['high']),
                low=float(k['low']),
                close=float(k['close']),
                volume=float(k['volume']),
            )
            for k in klines
        ]
        
        data = {
            'candles': [
                {
                    'time': c.time,
                    'open': c.open,
                    'high': c.high,
                    'low': c.low,
                    'close': c.close,
                    'volume': c.volume,
                }
                for c in candles
            ],
            'indicators': indicators or {},
        }
        
        return data
    
    def generate_tradingview_widget(
        self,
        symbol: str,
        interval: str = "60",
        width: int = 800,
        height: int = 600,
    ) -> str:
        """
        生成 TradingView Widget HTML
        
        Args:
            symbol: 交易对
            interval: 时间间隔
            width: 宽度
            height: 高度
            
        Returns:
            str: HTML 代码
        """
        html = f"""
        <!-- TradingView Widget BEGIN -->
        <div class="tradingview-widget-container">
          <div id="tradingview_{symbol}"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
          new TradingView.widget(
          {{
          "width": {width},
          "height": {height},
          "symbol": "BINANCE:{symbol}",
          "interval": "{interval}",
          "timezone": "Asia/Shanghai",
          "theme": "light",
          "style": "1",
          "locale": "zh_CN",
          "toolbar_bg": "#f1f3f6",
          "enable_publishing": false,
          "allow_symbol_change": true,
          "container_id": "tradingview_{symbol}"
          }}
          );
          </script>
        </div>
        <!-- TradingView Widget END -->
        """
        return html
