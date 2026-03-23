#!/usr/bin/env python3
"""
量化系统进度自动汇报脚本
发送每日进度到飞书群
"""
import os
import re
import json
import requests
from pathlib import Path
from datetime import datetime

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
PROGRESS_FILE = PROJECT_ROOT / "PROGRESS.md"

# 飞书配置
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK_URL", "")
FEISHU_SECRET = os.getenv("FEISHU_WEBHOOK_SECRET", "")


def parse_progress_md():
    """解析 PROGRESS.md 文件，提取关键进度信息"""
    if not PROGRESS_FILE.exists():
        return None
    
    content = PROGRESS_FILE.read_text(encoding="utf-8")
    
    # 提取最新一天的完成情况
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 查找最新的 Day 记录
    day_pattern = r"## Day \d+ - ([\d-]+).*?(?=## Day|\Z)"
    matches = re.findall(day_pattern, content, re.DOTALL)
    
    if not matches:
        return None
    
    # 获取最后一个 Day 的内容
    last_day_match = re.search(r"(## Day \d+ - [\d-]+ [^\n]*\n.*?)(?=## Day|\Z)", content, re.DOTALL)
    if not last_day_match:
        return None
    
    day_content = last_day_match.group(1)
    
    # 提取 Phase 状态
    phase_status = {}
    for phase in ["Phase 1", "Phase 2", "Phase 3"]:
        match = re.search(rf"\*\*{phase} 状态：\*\*([^\n]+)", content)
        if match:
            phase_status[phase] = match.group(1).strip()
    
    # 提取代码统计
    stats_match = re.search(r"\*\*总计\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*~?(\d+)\s*行\*\*", content)
    total_files = int(stats_match.group(1)) if stats_match else 0
    total_lines = int(stats_match.group(2)) if stats_match else 0
    
    # 提取今日完成项
    completed_items = []
    for match in re.finditer(r"- \[x\] ([^\n]+)", day_content):
        item = match.group(1).strip()
        if item and not item.startswith("NEW"):
            completed_items.append(item)
    
    # 提取下一步计划
    plans = []
    plan_section = re.search(r"### 🎯 (?:明日计划|Phase \d+ 计划)[^\n]*\n(.*?)(?=###|## Day|\Z)", content, re.DOTALL)
    if plan_section:
        for match in re.finditer(r"\d+\. \[[ x]\] ([^\n]+)", plan_section.group(1)):
            plans.append(match.group(1).strip())
    
    return {
        "date": today,
        "phase_status": phase_status,
        "total_files": total_files,
        "total_lines": total_lines,
        "completed_today": completed_items[:5],  # 最多 5 项
        "next_plans": plans[:3],  # 最多 3 项
    }


def generate_feishu_message(data):
    """生成飞书卡片消息"""
    if not data:
        return None
    
    # 构建 Phase 状态文本
    phase_text = ""
    for phase, status in data["phase_status"].items():
        emoji = "✅" if "100%" in status else ("🚀" if "进行中" in status else "⏳")
        phase_text += f"{emoji} **{phase}**: {status}\n"
    
    # 构建今日完成列表
    completed_text = ""
    for item in data["completed_today"]:
        # 清理文本，去掉过长的描述
        item_clean = re.sub(r'\([^)]*\)', '', item)[:40]  # 去掉括号内容，限制长度
        completed_text += f"• {item_clean}\n"
    
    # 构建下一步计划
    plans_text = ""
    for plan in data["next_plans"]:
        plans_text += f"• {plan[:40]}\n"
    
    # 飞书富文本卡片
    message = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 量化系统进度汇报 - {data['date']}"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": phase_text.strip()
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"📈 **代码规模**: {data['total_files']} 文件 / ~{data['total_lines']} 行"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"✅ **今日完成**:\n{completed_text.strip() or '暂无'}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"🎯 **下一步**:\n{plans_text.strip() or '待定'}"
                    }
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "自动汇报 · 每早 9 点/午 14 点/晚 20 点"
                        }
                    ]
                }
            ]
        }
    }
    
    return message


def send_to_feishu(message):
    """发送消息到飞书群"""
    if not FEISHU_WEBHOOK:
        print("❌ 未配置飞书 Webhook URL")
        print("   请在 .env 文件中设置 FEISHU_WEBHOOK_URL")
        return False
    
    try:
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            FEISHU_WEBHOOK,
            json=message,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                print("✅ 消息发送成功")
                return True
            else:
                print(f"❌ 发送失败：{result}")
                return False
        else:
            print(f"❌ HTTP 错误：{response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ 发送异常：{e}")
        return False


def main():
    """主函数"""
    print("📊 量化系统进度汇报")
    print("=" * 40)
    
    # 解析进度文件
    data = parse_progress_md()
    if not data:
        print("❌ 无法解析 PROGRESS.md")
        return 1
    
    print(f"📅 日期：{data['date']}")
    print(f"📈 代码：{data['total_files']} 文件 / ~{data['total_lines']} 行")
    
    # 生成消息
    message = generate_feishu_message(data)
    if not message:
        print("❌ 无法生成消息")
        return 1
    
    # 发送消息
    if send_to_feishu(message):
        print("✅ 汇报完成")
        return 0
    else:
        print("⚠️  发送失败，请检查配置")
        return 1


if __name__ == "__main__":
    exit(main())
