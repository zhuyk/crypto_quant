-- CryptoQuant 数据库初始化脚本
-- MySQL 8.0+

CREATE DATABASE IF NOT EXISTS crypto_quant CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE crypto_quant;

-- ============================================
-- 用户与账户表
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(128) UNIQUE,
    password_hash VARCHAR(256),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS accounts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    exchange VARCHAR(32) NOT NULL DEFAULT 'binance',
    api_key VARCHAR(256) NOT NULL,
    api_secret VARCHAR(256) NOT NULL,
    passphrase VARCHAR(256),
    is_testnet BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_exchange (user_id, exchange)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 策略相关表
-- ============================================

CREATE TABLE IF NOT EXISTS strategies (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(128) UNIQUE NOT NULL,
    category VARCHAR(64) NOT NULL,
    class_name VARCHAR(128) NOT NULL,
    description TEXT,
    default_params JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS strategy_instances (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    strategy_id INT NOT NULL,
    name VARCHAR(128) NOT NULL,
    params JSON NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE,
    INDEX idx_user (user_id),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS strategy_combos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    configs JSON NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 交易对与市场数据表
-- ============================================

CREATE TABLE IF NOT EXISTS symbols (
    id INT PRIMARY KEY AUTO_INCREMENT,
    exchange VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    base_currency VARCHAR(16) NOT NULL,
    quote_currency VARCHAR(16) NOT NULL,
    tick_size DECIMAL(32,16),
    step_size DECIMAL(32,16),
    min_notional DECIMAL(32,16),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_exchange_symbol (exchange, symbol),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- K 线数据表 - 按年分表
CREATE TABLE IF NOT EXISTS klines_2026 (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    exchange VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    `interval` VARCHAR(8) NOT NULL,
    open_time BIGINT NOT NULL,
    open DECIMAL(32,16) NOT NULL,
    high DECIMAL(32,16) NOT NULL,
    low DECIMAL(32,16) NOT NULL,
    close DECIMAL(32,16) NOT NULL,
    volume DECIMAL(32,16) NOT NULL,
    quote_volume DECIMAL(32,16),
    trades_count INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_exchange_symbol_time (exchange, symbol, `interval`, open_time),
    INDEX idx_symbol_time (symbol, open_time),
    INDEX idx_exchange (exchange)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 交易相关表
-- ============================================

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id VARCHAR(64) NOT NULL,
    user_id INT NOT NULL,
    strategy_instance_id INT,
    exchange VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,
    type VARCHAR(16) NOT NULL,
    price DECIMAL(32,16),
    quantity DECIMAL(32,16) NOT NULL,
    filled_quantity DECIMAL(32,16) DEFAULT 0,
    avg_fill_price DECIMAL(32,16),
    status VARCHAR(16) NOT NULL,
    time_in_force VARCHAR(8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    filled_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_instance_id) REFERENCES strategy_instances(id) ON DELETE SET NULL,
    INDEX idx_user (user_id),
    INDEX idx_strategy (strategy_instance_id),
    INDEX idx_status (status),
    INDEX idx_symbol (symbol),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS positions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    strategy_instance_id INT,
    exchange VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,
    quantity DECIMAL(32,16) NOT NULL DEFAULT 0,
    avg_entry_price DECIMAL(32,16),
    unrealized_pnl DECIMAL(32,16) DEFAULT 0,
    realized_pnl DECIMAL(32,16) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_instance_id) REFERENCES strategy_instances(id) ON DELETE SET NULL,
    UNIQUE KEY uk_user_exchange_symbol (user_id, exchange, symbol),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trades (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    trade_id VARCHAR(64) NOT NULL,
    order_id BIGINT,
    user_id INT NOT NULL,
    strategy_instance_id INT,
    exchange VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,
    price DECIMAL(32,16) NOT NULL,
    quantity DECIMAL(32,16) NOT NULL,
    commission DECIMAL(32,16),
    commission_asset VARCHAR(16),
    trade_time BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    FOREIGN KEY (strategy_instance_id) REFERENCES strategy_instances(id) ON DELETE SET NULL,
    INDEX idx_user (user_id),
    INDEX idx_symbol (symbol),
    INDEX idx_time (trade_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 资金与绩效表
-- ============================================

CREATE TABLE IF NOT EXISTS account_balance (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    exchange VARCHAR(32) NOT NULL,
    asset VARCHAR(16) NOT NULL,
    free DECIMAL(32,16) DEFAULT 0,
    locked DECIMAL(32,16) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_user_exchange_asset (user_id, exchange, asset),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS equity_curve (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    strategy_instance_id INT,
    date DATE NOT NULL,
    timestamp BIGINT NOT NULL,
    total_equity DECIMAL(32,16) NOT NULL,
    cash DECIMAL(32,16) NOT NULL,
    position_value DECIMAL(32,16) NOT NULL,
    daily_pnl DECIMAL(32,16) DEFAULT 0,
    cumulative_pnl DECIMAL(32,16) DEFAULT 0,
    drawdown DECIMAL(10,4) DEFAULT 0,
    max_drawdown DECIMAL(10,4) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_instance_id) REFERENCES strategy_instances(id) ON DELETE CASCADE,
    INDEX idx_user_date (user_id, date),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS daily_performance (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    strategy_instance_id INT,
    date DATE NOT NULL,
    starting_equity DECIMAL(32,16) NOT NULL,
    ending_equity DECIMAL(32,16) NOT NULL,
    daily_return DECIMAL(10,4) NOT NULL,
    trade_count INT DEFAULT 0,
    win_count INT DEFAULT 0,
    loss_count INT DEFAULT 0,
    pnl DECIMAL(32,16) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_instance_id) REFERENCES strategy_instances(id) ON DELETE CASCADE,
    UNIQUE KEY uk_user_strategy_date (user_id, strategy_instance_id, date),
    INDEX idx_user_date (user_id, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 回测结果表
-- ============================================

CREATE TABLE IF NOT EXISTS backtest_runs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    strategy_id INT NOT NULL,
    name VARCHAR(128),
    start_time BIGINT NOT NULL,
    end_time BIGINT NOT NULL,
    initial_capital DECIMAL(32,16) NOT NULL,
    final_capital DECIMAL(32,16) NOT NULL,
    total_return DECIMAL(10,4),
    annual_return DECIMAL(10,4),
    sharpe_ratio DECIMAL(10,4),
    sortino_ratio DECIMAL(10,4),
    max_drawdown DECIMAL(10,4),
    win_rate DECIMAL(10,4),
    profit_factor DECIMAL(10,4),
    total_trades INT,
    winning_trades INT,
    losing_trades INT,
    avg_win DECIMAL(32,16),
    avg_loss DECIMAL(32,16),
    params JSON,
    symbols JSON,
    status VARCHAR(16) DEFAULT 'pending',
    equity_curve_path VARCHAR(256),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE,
    INDEX idx_user (user_id),
    INDEX idx_status (status),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 系统日志表
-- ============================================

CREATE TABLE IF NOT EXISTS system_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    level VARCHAR(16) NOT NULL,
    module VARCHAR(64),
    message TEXT NOT NULL,
    context JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_level (level),
    INDEX idx_module (module),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 初始化默认数据
-- ============================================

-- 插入默认策略
INSERT INTO strategies (name, category, class_name, description, default_params) VALUES
('ma_cross', 'trend', 'MACrossStrategy', '双均线交叉趋势策略', 
 '{"fast_period": 20, "slow_period": 60, "stop_loss_pct": 0.05, "take_profit_pct": 0.15}'),
('breakout', 'trend', 'BreakoutStrategy', 'Donchian 通道突破策略',
 '{"lookback_period": 20, "stop_loss_pct": 0.08, "trailing_stop": true}'),
('macd_trend', 'trend', 'MACDTrendStrategy', 'MACD 趋势跟踪策略',
 '{"fast_period": 12, "slow_period": 26, "signal_period": 9, "stop_loss_pct": 0.06}');

-- 插入默认 Binance 交易对
INSERT INTO symbols (exchange, symbol, base_currency, quote_currency, is_active) VALUES
('binance', 'BTCUSDT', 'BTC', 'USDT', TRUE),
('binance', 'ETHUSDT', 'ETH', 'USDT', TRUE),
('binance', 'BNBUSDT', 'BNB', 'USDT', TRUE),
('binance', 'SOLUSDT', 'SOL', 'USDT', TRUE),
('binance', 'XRPUSDT', 'XRP', 'USDT', TRUE);
