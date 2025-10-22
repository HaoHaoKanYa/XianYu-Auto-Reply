"""
自动收小红花管理器
负责管理买家送出小红花后的自动收取功能
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from loguru import logger
from db_manager import db_manager


class FlowerCollectManager:
    """自动收小红花管理器"""
    
    def __init__(self):
        """初始化收小红花管理器"""
        self.collect_tasks = {}  # {cookie_id: asyncio.Task}
        self.running = False
        logger.info("自动收小红花管理器初始化完成")
    
    async def start(self):
        """启动收小红花管理器"""
        if self.running:
            logger.warning("收小红花管理器已经在运行中")
            return
        
        self.running = True
        logger.info("启动自动收小红花管理器...")
        
        # 获取所有启用了收小红花功能的账号
        enabled_cookies = db_manager.get_enabled_flower_collect_cookies()
        
        for cookie_id in enabled_cookies:
            await self.start_collect_task(cookie_id)
        
        logger.info(f"自动收小红花管理器启动完成，已启动 {len(enabled_cookies)} 个账号的收小红花任务")
    
    async def stop(self):
        """停止收小红花管理器"""
        if not self.running:
            return
        
        self.running = False
        logger.info("停止自动收小红花管理器...")
        
        # 取消所有收小红花任务
        for cookie_id, task in self.collect_tasks.items():
            if task and not task.done():
                task.cancel()
                logger.info(f"已取消账号 {cookie_id} 的收小红花任务")
        
        self.collect_tasks.clear()
        logger.info("自动收小红花管理器已停止")
    
    async def start_collect_task(self, cookie_id: str):
        """启动指定账号的收小红花任务
        
        Args:
            cookie_id: 账号ID
        """
        # 如果任务已存在且正在运行，先取消
        if cookie_id in self.collect_tasks:
            old_task = self.collect_tasks[cookie_id]
            if old_task and not old_task.done():
                old_task.cancel()
                logger.info(f"取消账号 {cookie_id} 的旧收小红花任务")
        
        # 创建新任务
        task = asyncio.create_task(self.collect_check_loop(cookie_id))
        self.collect_tasks[cookie_id] = task
        logger.info(f"已启动账号 {cookie_id} 的收小红花任务")
    
    async def stop_collect_task(self, cookie_id: str):
        """停止指定账号的收小红花任务
        
        Args:
            cookie_id: 账号ID
        """
        if cookie_id in self.collect_tasks:
            task = self.collect_tasks[cookie_id]
            if task and not task.done():
                task.cancel()
                logger.info(f"已停止账号 {cookie_id} 的收小红花任务")
            del self.collect_tasks[cookie_id]
    
    async def collect_check_loop(self, cookie_id: str):
        """收小红花检查循环（每分钟执行一次）
        
        Args:
            cookie_id: 账号ID
        """
        logger.info(f"【{cookie_id}】收小红花检查循环已启动")
        
        while self.running:
            try:
                # 检查并收取小红花
                await self.check_and_collect_flowers(cookie_id)
                
                # 每分钟检查一次
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info(f"【{cookie_id}】收小红花检查循环被取消")
                break
            except Exception as e:
                logger.error(f"【{cookie_id}】收小红花检查失败: {e}")
                # 出错后等待1分钟再继续
                await asyncio.sleep(60)
    
    async def check_and_collect_flowers(self, cookie_id: str):
        """检查并收取小红花
        
        Args:
            cookie_id: 账号ID
        """
        try:
            # 1. 获取该账号的收小红花设置
            settings = db_manager.get_flower_collect_settings(cookie_id)
            if not settings or not settings.get('enabled'):
                return
            
            # 2. 获取需要收取小红花的记录列表
            current_time = datetime.now()
            pending_collects = db_manager.get_pending_flower_collects(cookie_id, current_time)
            
            if not pending_collects:
                return
            
            logger.info(f"【{cookie_id}】发现 {len(pending_collects)} 个待收取小红花")
            
            # 3. 逐个处理收取小红花
            for collect in pending_collects:
                try:
                    # 收取小红花
                    success = await self.collect_flower(
                        order_id=collect['order_id'],
                        buyer_id=collect['buyer_id'],
                        cookie_id=cookie_id
                    )
                    
                    if success:
                        # 更新收小红花记录为已完成
                        db_manager.update_flower_collect_record(
                            order_id=collect['order_id'],
                            collect_time=current_time,
                            status='completed'
                        )
                        logger.info(f"【{cookie_id}】订单 {collect['order_id']} 收小红花成功")
                    else:
                        logger.warning(f"【{cookie_id}】订单 {collect['order_id']} 收小红花失败")
                    
                    # 避免操作过快，间隔2秒
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"【{cookie_id}】处理订单 {collect.get('order_id')} 收小红花时出错: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"【{cookie_id}】检查并收取小红花时出错: {e}")
    
    async def collect_flower(self, order_id: str, buyer_id: str, cookie_id: str) -> bool:
        """收取小红花
        
        Args:
            order_id: 订单ID
            buyer_id: 买家ID
            cookie_id: 账号ID
            
        Returns:
            bool: 是否收取成功
        """
        try:
            # 获取XianyuLive实例
            from XianyuAutoAsync import XianyuLive
            instance = XianyuLive.get_instance(cookie_id)
            
            if not instance:
                logger.error(f"【{cookie_id}】无法获取XianyuLive实例，账号可能未启动")
                return False
            
            # 调用闲鱼API收取小红花
            # 这里需要调用实际的闲鱼收小红花API
            # 暂时使用模拟实现
            logger.info(f"【{cookie_id}】正在收取订单 {order_id} 的小红花...")
            
            # TODO: 实现实际的收小红花API调用
            # 目前返回成功，实际需要调用闲鱼API
            
            logger.info(f"【{cookie_id}】成功收取订单 {order_id} 的小红花")
            return True
            
        except Exception as e:
            logger.error(f"【{cookie_id}】收取小红花时出错: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def calculate_collect_time(self, send_time: datetime, settings: Dict) -> Optional[datetime]:
        """计算收小红花时间
        
        Args:
            send_time: 买家送花时间
            settings: 收小红花设置
            
        Returns:
            datetime: 收小红花时间
        """
        try:
            # 获取延迟设置
            delay_value = settings.get('delay_value', 3)
            delay_unit = settings.get('delay_unit', 'days')
            
            if delay_unit == 'seconds':
                delay = timedelta(seconds=delay_value)
            elif delay_unit == 'minutes':
                delay = timedelta(minutes=delay_value)
            elif delay_unit == 'hours':
                delay = timedelta(hours=delay_value)
            else:  # days
                delay = timedelta(days=delay_value)
            
            collect_time = send_time + delay
            return collect_time
            
        except Exception as e:
            logger.error(f"计算收小红花时间时出错: {e}")
            return None
    
    def on_flower_received(self, order_id: str, cookie_id: str, buyer_id: str, send_time: datetime):
        """买家送出小红花时的回调
        
        Args:
            order_id: 订单ID
            cookie_id: 账号ID
            buyer_id: 买家ID
            send_time: 送花时间
        """
        try:
            # 获取收小红花设置
            settings = db_manager.get_flower_collect_settings(cookie_id)
            if not settings or not settings.get('enabled'):
                logger.debug(f"【{cookie_id}】未启用自动收小红花功能")
                return
            
            # 计算收小红花时间
            collect_time = self.calculate_collect_time(
                send_time=send_time,
                settings=settings
            )
            
            # 创建收小红花记录
            db_manager.create_flower_collect_record(
                order_id=order_id,
                cookie_id=cookie_id,
                buyer_id=buyer_id,
                send_time=send_time,
                collect_time=collect_time
            )
            
            logger.info(f"【{cookie_id}】订单 {order_id} 已创建收小红花记录，收取时间: {collect_time}")
            
        except Exception as e:
            logger.error(f"【{cookie_id}】创建收小红花记录时出错: {e}")


# 创建全局收小红花管理器实例
flower_collect_manager = FlowerCollectManager()
