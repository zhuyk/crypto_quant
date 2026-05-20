#!/usr/bin/env python3
"""
迁移脚本：为 backtest_runs 表添加缺失的列
"""
import sys
import os

# 确保能导入 app 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.core.database import engine

# 需要添加/修改的列
COLUMN_CHANGES = [
    # 改 user_id 为 nullable
    {"col": "user_id", "nullable": True},
    # 新增列
    {"col": "annual_return", "type": "FLOAT", "nullable": True},
    {"col": "winning_trades", "type": "INT", "nullable": True},
    {"col": "losing_trades", "type": "INT", "nullable": True},
    {"col": "profit_factor", "type": "FLOAT", "nullable": True},
]


def get_mysql_columns(table: str) -> set:
    """获取表已有的列"""
    with engine.connect() as conn:
        result = conn.execute(text(f"SHOW COLUMNS FROM {table}"))
        return {row[0] for row in result}


def migrate():
    table = "backtest_runs"
    
    try:
        existing = get_mysql_columns(table)
        print(f"📋 当前表已有列: {existing}")
    except Exception as e:
        print(f"❌ 无法读取表结构: {e}")
        return False

    with engine.connect() as conn:
        for change in COLUMN_CHANGES:
            col = change["col"]
            
            if col in existing:
                print(f"⏭️  列 {col} 已存在，跳过")
                continue
            
            if "nullable" in change:
                # 只能改 nullable 属性，用 MODIFY
                try:
                    conn.execute(text(
                        f"ALTER TABLE {table} MODIFY COLUMN {col} INT {'NULL' if change['nullable'] else 'NOT NULL'}"
                    ))
                    conn.commit()
                    print(f"✅ 列 {col} 已修改为 nullable={change['nullable']}")
                except Exception as e:
                    print(f"⚠️  修改 {col} 失败（可能已是正确类型）: {e}")
                continue
            
            col_type = change["type"]
            sql = f"ALTER TABLE {table} ADD COLUMN {col} {col_type} NULL"
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ 新增列 {col} ({col_type})")
            except Exception as e:
                print(f"❌ 新增列 {col} 失败: {e}")
                return False
    
    print("\n✅ 迁移完成！")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("🔧 backtest_runs 表结构迁移")
    print("=" * 50)
    migrate()
