"""
自动求好评管理器
负责管理订单的自动求好评功能
"""

import asyncio
import time
import random
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from loguru import logger
from db_manager import db_manager


class ReviewRequestManager:
    """自动求好评管理器"""
    
    def __init__(self):
        """初始化求好评管理器"""
        self.review_tasks = {}  # {cookie_id: asyncio.Task}
        self.running = False
        logger.info("自动求好评管理器初始化完成")
    
    async def start(self):
        """启动求好评管理器"""
        if self.running:
            logger.warning("求好评管理器已经在运行中")
            return
        
        self.running = True
        logger.info("启动自动求好评管理器...")
        
        # 获取所有启用了求好评功能的账号
        enabled_cookies = db_manager.get_enabled_review_request_cookies()
        
        for cookie_id in enabled_cookies:
            await self.start_review_task(cookie_id)
        
        logger.info(f"自动求好评管理器启动完成，已启动 {len(enabled_cookies)} 个账号的求好评任务")
    
    async def stop(self):
        """停止求好评管理器"""
        if not self.running:
            return
        
        self.running = False
        logger.info("停止自动求好评管理器...")
        
        # 取消所有求好评任务
        for cookie_id, task in self.review_tasks.items():
            if task and not task.done():
                task.cancel()
                logger.info(f"已取消账号 {cookie_id} 的求好评任务")
        
        self.review_tasks.clear()
        logger.info("自动求好评管理器已停止")
    
    async def start_review_task(self, cookie_id: str):
        """启动指定账号的求好评任务
        
        Args:
            cookie_id: 账号ID
        """
        # 如果任务已存在且正在运行，先取消
        if cookie_id in self.review_tasks:
            old_task = self.review_tasks[cookie_id]
            if old_task and not old_task.done():
                old_task.cancel()
                logger.info(f"取消账号 {cookie_id} 的旧求好评任务")
        
        # 创建新任务
        task = asyncio.create_task(self.review_check_loop(cookie_id))
        self.review_tasks[cookie_id] = task
        logger.info(f"已启动账号 {cookie_id} 的求好评任务")
    
    async def stop_review_task(self, cookie_id: str):
        """停止指定账号的求好评任务
        
        Args:
            cookie_id: 账号ID
        """
        if cookie_id in self.review_tasks:
            task = self.review_tasks[cookie_id]
            if task and not task.done():
                task.cancel()
                logger.info(f"已停止账号 {cookie_id} 的求好评任务")
            del self.review_tasks[cookie_id]
    
    async def review_check_loop(self, cookie_id: str):
        """求好评检查循环（每分钟执行一次）
        
        Args:
            cookie_id: 账号ID
        """
        logger.info(f"【{cookie_id}】求好评检查循环已启动")
        
        while self.running:
            try:
                # 检查并发送求好评
                await self.check_and_send_review_requests(cookie_id)
                
                # 每分钟检查一次
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info(f"【{cookie_id}】求好评检查循环被取消")
                break
            except Exception as e:
                logger.error(f"【{cookie_id}】求好评检查失败: {e}")
                # 出错后等待1分钟再继续
                await asyncio.sleep(60)
    
    async def check_and_send_review_requests(self, cookie_id: str):
        """检查并发送求好评
        
        Args:
            cookie_id: 账号ID
        """
        try:
            # 1. 获取该账号的求好评设置
            settings = db_manager.get_review_request_settings(cookie_id)
            if not settings or not settings.get('enabled'):
                return
            
            # 2. 获取需要求好评的订单列表
            current_time = datetime.now()
            pending_requests = db_manager.get_pending_review_requests(cookie_id, current_time)
            
            if not pending_requests:
                return
            
            logger.info(f"【{cookie_id}】发现 {len(pending_requests)} 个待求好评订单")
            
            # 3. 逐个处理求好评
            for request in pending_requests:
                try:
                    # 检查订单状态（必须是已完成状态）
                    order = db_manager.get_order_by_id(request['order_id'])
                    if not order or order.get('order_status') != 'completed':
                        logger.info(f"【{cookie_id}】订单 {request['order_id']} 状态不是已完成，跳过求好评")
                        # 标记为已取消
                        db_manager.update_review_request_status(request['order_id'], 'cancelled')
                        continue
                    
                    # 发送求好评消息
                    success = await self.send_review_request_message(
                        order_id=request['order_id'],
                        buyer_id=request['buyer_id'],
                        cookie_id=cookie_id,
                        settings=settings
                    )
                    
                    if success:
                        # 更新求好评记录为已完成
                        db_manager.update_review_request_record(
                            order_id=request['order_id'],
                            request_time=current_time,
                            status='completed'
                        )
                        logger.info(f"【{cookie_id}】订单 {request['order_id']} 求好评成功")
                    else:
                        logger.warning(f"【{cookie_id}】订单 {request['order_id']} 求好评发送失败")
                    
                    # 避免发送过快，间隔2秒
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"【{cookie_id}】处理订单 {request.get('order_id')} 求好评时出错: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"【{cookie_id}】检查并发送求好评时出错: {e}")
    
    async def send_review_request_message(self, order_id: str, buyer_id: str, 
                                         cookie_id: str, settings: Dict) -> bool:
        """发送求好评消息
        
        Args:
            order_id: 订单ID
            buyer_id: 买家ID
            cookie_id: 账号ID
            settings: 求好评设置
            
        Returns:
            bool: 是否发送成功
        """
        try:
            # 获取XianyuLive实例
            from XianyuAutoAsync import XianyuLive
            instance = XianyuLive.get_instance(cookie_id)
            
            if not instance:
                logger.error(f"【{cookie_id}】无法获取XianyuLive实例，账号可能未启动")
                return False
            
            # 检查WebSocket连接状态
            if not instance.ws or instance.ws.closed:
                logger.warning(f"【{cookie_id}】WebSocket连接未建立或已关闭，无法发送求好评")
                return False
            
            # 获取模板列表
            templates = db_manager.get_review_templates(cookie_id)
            
            # 如果没有模板，使用默认消息
            if not templates:
                message = "感谢惠顾~期待与您再次相遇，麻烦给小店来个好评或加个关注呀~😊"
            else:
                # 随机选择一个模板
                template = random.choice(templates)
                message = template['content']
            
            # 获取订单信息以获取item_id和chat_id
            order = db_manager.get_order_by_id(order_id)
            if not order:
                logger.error(f"【{cookie_id}】找不到订单信息: {order_id}")
                return False
            
            item_id = order.get('item_id', '')
            
            # 使用现有的WebSocket连接发送消息
            chat_id = f"{buyer_id}_{item_id}"  # 构造chat_id
            await instance.send_msg(instance.ws, chat_id, buyer_id, message)
            
            logger.info(f"【{cookie_id}】成功向买家 {buyer_id} 发送求好评消息（订单: {order_id}）")
            return True
            
        except Exception as e:
            logger.error(f"【{cookie_id}】发送求好评消息时出错: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def calculate_request_time(self, completed_time: datetime, settings: Dict) -> Optional[datetime]:
        """计算求好评时间
        
        Args:
            completed_time: 确认收货时间
            settings: 求好评设置
            
        Returns:
            datetime: 求好评时间
        """
        try:
            # 获取延迟设置
            delay_value = settings.get('delay_value', 3)
            delay_unit = settings.get('delay_unit', 'minutes')
            
            if delay_unit == 'seconds':
                delay = timedelta(seconds=delay_value)
            elif delay_unit == 'minutes':
                delay = timedelta(minutes=delay_value)
            elif delay_unit == 'hours':
                delay = timedelta(hours=delay_value)
            else:  # days
                delay = timedelta(days=delay_value)
            
            request_time = completed_time + delay
            return request_time
            
        except Exception as e:
            logger.error(f"计算求好评时间时出错: {e}")
            return None
    
    def on_order_completed(self, order_id: str, cookie_id: str, buyer_id: str, completed_time: datetime):
        """订单完成时的回调（买家确认收货）
        
        Args:
            order_id: 订单ID
            cookie_id: 账号ID
            buyer_id: 买家ID
            completed_time: 确认收货时间
        """
        try:
            # 获取求好评设置
            settings = db_manager.get_review_request_settings(cookie_id)
            if not settings or not settings.get('enabled'):
                logger.debug(f"【{cookie_id}】未启用自动求好评功能")
                return
            
            # 计算求好评时间
            request_time = self.calculate_request_time(
                completed_time=completed_time,
                settings=settings
            )
            
            # 创建求好评记录
            db_manager.create_review_request_record(
                order_id=order_id,
                cookie_id=cookie_id,
                buyer_id=buyer_id,
                completed_time=completed_time,
                request_time=request_time
            )
            
            logger.info(f"【{cookie_id}】订单 {order_id} 已创建求好评记录，求好评时间: {request_time}")
            
        except Exception as e:
            logger.error(f"【{cookie_id}】创建求好评记录时出错: {e}")


# 创建全局求好评管理器实例
review_request_manager = ReviewRequestManager()
