"""
初始化脚本 - 创建默认管理员账户
"""

import sys
import os

# 添加后端路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.auth.user_manager import get_user_manager
from app.core.auth.rbac import get_role_manager, Role

def create_default_admin():
    """创建默认管理员账户"""
    user_manager = get_user_manager()
    role_manager = get_role_manager()
    
    # 检查是否已存在
    existing_user = user_manager.get_user_by_username('admin')
    if existing_user:
        print("✅ 管理员账户已存在")
        return existing_user
    
    # 创建管理员
    admin = user_manager.create_user(
        username='admin',
        email='admin@cryptoquant.com',
        password='admin123456',
        roles=['admin'],
    )
    
    # 分配管理员角色
    role_manager.assign_role(admin.id, Role.ADMIN)
    
    print("✅ 默认管理员账户创建成功！")
    print(f"用户名：admin")
    print(f"密码：admin123456")
    print(f"用户 ID: {admin.id}")
    
    return admin

def create_demo_user():
    """创建演示用户"""
    user_manager = get_user_manager()
    role_manager = get_role_manager()
    
    # 检查是否已存在
    existing_user = user_manager.get_user_by_username('demo')
    if existing_user:
        print("✅ 演示账户已存在")
        return existing_user
    
    # 创建演示用户
    demo = user_manager.create_user(
        username='demo',
        email='demo@cryptoquant.com',
        password='demo123456',
        roles=['trader'],
    )
    
    # 分配交易员角色
    role_manager.assign_role(demo.id, Role.TRADER)
    
    print("✅ 演示账户创建成功！")
    print(f"用户名：demo")
    print(f"密码：demo123456")
    
    return demo

if __name__ == '__main__':
    print("🚀 开始初始化账户...")
    print("=" * 50)
    
    create_default_admin()
    create_demo_user()
    
    print("=" * 50)
    print("✅ 初始化完成！")
    print("")
    print("📝 可用账户:")
    print("  超管账户：admin / admin123456")
    print("  演示账户：demo / demo123456")
    print("")
