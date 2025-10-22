"""
验证自动提醒收货功能的数据库表是否创建成功
"""

import sqlite3
import os

def check_tables():
    """检查数据库表是否存在"""
    db_path = 'xianyu_data.db'
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查的表列表
    tables_to_check = [
        'reminder_settings',
        'reminder_records',
        'blacklist_users',
        'competitor_users'
    ]
    
    print("=== 检查数据库表 ===\n")
    
    all_exist = True
    for table_name in tables_to_check:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        result = cursor.fetchone()
        
        if result:
            print(f"✅ 表 {table_name} 存在")
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            print(f"   字段数量: {len(columns)}")
            print(f"   字段列表: {[col[1] for col[1:6] in columns]}")
            print()
        else:
            print(f"❌ 表 {table_name} 不存在")
            all_exist = False
    
    conn.close()
    
    if all_exist:
        print("\n✅ 所有提醒功能相关的表都已创建成功！")
    else:
        print("\n❌ 部分表未创建，请检查数据库初始化")
    
    return all_exist


def check_db_manager_methods():
    """检查db_manager是否有新增的方法"""
    print("\n=== 检查 db_manager 新增方法 ===\n")
    
    try:
        from db_manager import db_manager
        
        methods_to_check = [
            'get_reminder_settings',
            'save_reminder_settings',
            'get_enabled_reminder_cookies',
            'create_reminder_record',
            'get_pending_reminders',
            'update_reminder_record',
            'update_reminder_status',
            'is_blacklist_user',
            'add_blacklist_user',
            'remove_blacklist_user',
            'get_blacklist_users',
            'is_competitor_user',
            'add_competitor_user',
            'remove_competitor_user',
            'get_competitor_users',
            'has_dispute_record',
            'get_reminder_records'
        ]
        
        all_exist = True
        for method_name in methods_to_check:
            if hasattr(db_manager, method_name):
                print(f"✅ 方法 {method_name} 存在")
            else:
                print(f"❌ 方法 {method_name} 不存在")
                all_exist = False
        
        if all_exist:
            print("\n✅ 所有新增方法都已添加成功！")
        else:
            print("\n❌ 部分方法未添加")
        
        return all_exist
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False


def check_reminder_manager():
    """检查reminder_manager模块"""
    print("\n=== 检查 reminder_manager 模块 ===\n")
    
    try:
        from reminder_manager import reminder_manager
        
        print(f"✅ reminder_manager 模块导入成功")
        print(f"   类型: {type(reminder_manager)}")
        print(f"   方法: {[m for m in dir(reminder_manager) if not m.startswith('_')]}")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("自动提醒收货功能验证")
    print("=" * 60)
    
    # 检查数据库表
    tables_ok = check_tables()
    
    # 检查db_manager方法
    methods_ok = check_db_manager_methods()
    
    # 检查reminder_manager模块
    manager_ok = check_reminder_manager()
    
    # 总结
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    print(f"数据库表: {'✅ 通过' if tables_ok else '❌ 失败'}")
    print(f"数据库方法: {'✅ 通过' if methods_ok else '❌ 失败'}")
    print(f"提醒管理器: {'✅ 通过' if manager_ok else '❌ 失败'}")
    
    if tables_ok and methods_ok and manager_ok:
        print("\n🎉 自动提醒收货功能集成成功！")
        print("\n下一步:")
        print("1. 启动系统: python Start.py")
        print("2. 在Web界面中配置提醒设置")
        print("3. 查看提醒记录和统计")
    else:
        print("\n⚠️ 部分功能未正确集成，请检查错误信息")


if __name__ == '__main__':
    main()
