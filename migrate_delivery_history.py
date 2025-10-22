#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：添加发货历史记录表
用于记录每次发货的详细信息，支持今日发货统计功能
"""

import sqlite3
from pathlib import Path
from loguru import logger

def migrate_database():
    """执行数据库迁移"""
    db_path = Path(__file__).parent / "xianyu_data.db"
    
    if not db_path.exists():
        logger.error(f"数据库文件不存在: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 检查表是否已存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='delivery_history'
        """)
        
        if cursor.fetchone():
            logger.info("发货历史表已存在，跳过创建")
            return True
        
        # 创建发货历史记录表
        logger.info("开始创建发货历史记录表...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS delivery_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL,
                cookie_id TEXT NOT NULL,
                order_id TEXT,
                item_id TEXT,
                user_id TEXT,
                delivery_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rule_id) REFERENCES delivery_rules(id) ON DELETE CASCADE,
                FOREIGN KEY (cookie_id) REFERENCES cookies(id) ON DELETE CASCADE
            )
        ''')
        
        # 创建索引以提高查询性能
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_delivery_history_created_at 
            ON delivery_history(created_at)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_delivery_history_cookie_id 
            ON delivery_history(cookie_id)
        ''')
        
        conn.commit()
        logger.info("✅ 发货历史记录表创建成功")
        
        # 显示表结构
        cursor.execute("PRAGMA table_info(delivery_history)")
        columns = cursor.fetchall()
        logger.info("表结构:")
        for col in columns:
            logger.info(f"  - {col[1]} ({col[2]})")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"数据库迁移失败: {e}")
        return False

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("开始执行数据库迁移：添加发货历史记录表")
    logger.info("=" * 60)
    
    success = migrate_database()
    
    if success:
        logger.info("=" * 60)
        logger.info("✅ 数据库迁移完成")
        logger.info("=" * 60)
        logger.info("现在可以正常使用今日发货统计功能了")
    else:
        logger.error("=" * 60)
        logger.error("❌ 数据库迁移失败")
        logger.error("=" * 60)
