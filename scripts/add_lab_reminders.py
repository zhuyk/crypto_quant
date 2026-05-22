#!/usr/bin/env python3
"""
为 LAB Token 解锁设置日历提醒

你的 LAB Vesting 时间线：
- TGE: 2025-10-14
- Cliff: 9 个月（2025.10 ~ 2026.07）
- 线性释放: 6 个月（2026.07 ~ 2027.01）
- 全部解锁: 2027-01-14

运行方式：
  cd backend
  python -m scripts.add_lab_reminders
"""
import sys
from pathlib import Path
from datetime import datetime

# 添加 backend 到 path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.database import SessionLocal, Base, engine
from app.models.reminder import Reminder


def create_lab_reminders():
    """创建 LAB 代币解锁相关的所有提醒"""
    
    # 确保表存在
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    reminders_data = [
        # === Cliff 结束 / 第一批解锁 ===
        {
            "title": "🔓 LAB 第一批解锁！~1,667 LAB 可出售",
            "description": (
                "LAB Token 9个月 Cliff 结束，第一批线性释放开始！\n"
                "解锁量: ~1,667 LAB (总量的 16.7%)\n"
                "建议: 考虑至少卖出 30-50% 锁定利润\n"
                "注意: 查看当时价格和 ZachXBT 调查进展\n"
                "你的总持仓: ~10,000 LAB (成本 $200)"
            ),
            "remind_at": datetime(2026, 7, 14, 8, 0, 0),
            "reminder_type": "expiry",
            "priority": "critical",
            "repeat_rule": "none",
            "metadata_json": {
                "token": "LAB",
                "event": "cliff_end_first_unlock",
                "unlock_amount": 1667,
                "unlock_pct": 16.7,
                "total_holding": 10000,
                "cost_basis": 200,
                "ido_price": 0.02,
            },
        },
        # === 提前一周预警 ===
        {
            "title": "⏰ LAB 解锁倒计时 7 天！准备策略",
            "description": (
                "LAB 第一批解锁还有 7 天（7月14日）\n"
                "建议提前做好准备:\n"
                "1. 确认钱包连接正常\n"
                "2. 检查当前 LAB 价格\n"
                "3. 决定卖出比例和价位\n"
                "4. 确认 claim 操作步骤"
            ),
            "remind_at": datetime(2026, 7, 7, 9, 0, 0),
            "reminder_type": "custom",
            "priority": "high",
            "repeat_rule": "none",
            "metadata_json": {
                "token": "LAB",
                "event": "pre_unlock_warning",
                "days_before": 7,
            },
        },
        # === 每月解锁提醒 (2~6批) ===
        {
            "title": "🔓 LAB 第2批解锁: +1,667 LAB (累计 33%)",
            "description": "第2个月线性释放，累计解锁 3,334 LAB。评估是否继续持有或卖出。",
            "remind_at": datetime(2026, 8, 14, 8, 0, 0),
            "reminder_type": "expiry",
            "priority": "high",
            "repeat_rule": "none",
            "metadata_json": {"token": "LAB", "batch": 2, "cumulative": 3334, "cumulative_pct": 33.3},
        },
        {
            "title": "🔓 LAB 第3批解锁: +1,667 LAB (累计 50%)",
            "description": "半数解锁。回顾持仓策略，关注项目进展和市场情绪。",
            "remind_at": datetime(2026, 9, 14, 8, 0, 0),
            "reminder_type": "expiry",
            "priority": "medium",
            "repeat_rule": "none",
            "metadata_json": {"token": "LAB", "batch": 3, "cumulative": 5001, "cumulative_pct": 50},
        },
        {
            "title": "🔓 LAB 第4批解锁: +1,667 LAB (累计 67%)",
            "description": "三分之二已解锁。如果还没卖出，认真评估剩余持仓风险。",
            "remind_at": datetime(2026, 10, 14, 8, 0, 0),
            "reminder_type": "expiry",
            "priority": "medium",
            "repeat_rule": "none",
            "metadata_json": {"token": "LAB", "batch": 4, "cumulative": 6668, "cumulative_pct": 66.7},
        },
        {
            "title": "🔓 LAB 第5批解锁: +1,667 LAB (累计 83%)",
            "description": "接近全部解锁。决定最后剩余部分的处理策略。",
            "remind_at": datetime(2026, 11, 14, 8, 0, 0),
            "reminder_type": "expiry",
            "priority": "medium",
            "repeat_rule": "none",
            "metadata_json": {"token": "LAB", "batch": 5, "cumulative": 8335, "cumulative_pct": 83.3},
        },
        {
            "title": "✅ LAB 全部解锁！10,000 LAB 100% 可用",
            "description": (
                "恭喜！你的 LAB 代币已全部解锁。\n"
                "总持仓: 10,000 LAB\n"
                "原始成本: $200\n"
                "回顾这笔投资的最终收益。"
            ),
            "remind_at": datetime(2027, 1, 14, 8, 0, 0),
            "reminder_type": "expiry",
            "priority": "high",
            "repeat_rule": "none",
            "metadata_json": {"token": "LAB", "batch": 6, "cumulative": 10000, "cumulative_pct": 100, "event": "fully_unlocked"},
        },
        # === 价格监控提醒 ===
        {
            "title": "💰 LAB 价格提醒: 关注解锁前价格走势",
            "description": (
                "从 6 月开始每周检查一次 LAB 价格\n"
                "关注: 是否有大幅下跌（内部人提前出货？）\n"
                "参考: CoinMarketCap / CoinGecko 上 LAB 价格\n"
                "如果 7 月解锁前价格已崩，可能需要调整策略"
            ),
            "remind_at": datetime(2026, 6, 1, 9, 0, 0),
            "reminder_type": "custom",
            "priority": "medium",
            "repeat_rule": "weekly",
            "metadata_json": {"token": "LAB", "event": "weekly_price_check"},
        },
    ]
    
    created_count = 0
    
    try:
        for data in reminders_data:
            reminder = Reminder(
                user_id=1,
                title=data["title"],
                description=data["description"],
                remind_at=data["remind_at"],
                reminder_type=data["reminder_type"],
                priority=data["priority"],
                repeat_rule=data["repeat_rule"],
                metadata_json=data["metadata_json"],
                notify_channels=["app", "email"],
            )
            db.add(reminder)
            created_count += 1
            print(f"  📅 {data['remind_at'].strftime('%Y-%m-%d')} | {data['title']}")
        
        db.commit()
        print(f"\n✅ 成功创建 {created_count} 个 LAB 解锁提醒！")
        print("\n时间线总结:")
        print("  2026-06-01  开始每周关注价格")
        print("  2026-07-07  解锁倒计时 7 天预警")
        print("  2026-07-14  🔓 第一批解锁 (16.7%)")
        print("  2026-08-14  🔓 第二批 (33.3%)")
        print("  2026-09-14  🔓 第三批 (50%)")
        print("  2026-10-14  🔓 第四批 (66.7%)")
        print("  2026-11-14  🔓 第五批 (83.3%)")
        print("  2027-01-14  ✅ 全部解锁 (100%)")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 创建提醒失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("📅 LAB Token 解锁提醒设置")
    print("=" * 60)
    print(f"持仓: ~10,000 LAB | 成本: $200 | IDO 价: ~$0.02")
    print(f"Vesting: 0% TGE → 9个月 Cliff → 6个月线性释放")
    print("=" * 60)
    print()
    create_lab_reminders()
