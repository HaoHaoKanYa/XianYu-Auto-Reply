"""
自动提醒收货管理器
负责管理订单的自动提醒收货功能
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from loguru import logger
from db_manager import db_manager


class ReminderManager:
    """自动提醒收货管理器"""
    
    def __init__(self):
        """初始化提醒管理器"""
        self.reminder_tasks = {}  # {cookie_id: asyncio.Task}
        self.running = False
        logger.info("自动提醒收货管理器初始化完成")
    
    async def start(self):
        """启动提醒管理器"""
        if self.running:
            logger.warning("提醒管理器已经在运行中")
            return
        
        self.running = True
        logger.info("启动自动提醒收货管理器...")
        
        # 获取所有启用了提醒功能的账号
        enabled_cookies = db_manager.get_enabled_reminder_cookies()
        
        for cookie_id in enabled_cookies:
            await self.start_reminder_task(cookie_id)
        
        logger.info(f"自动提醒收货管理器启动完成，已启动 {len(enabled_cookies)} 个账号的提醒任务")
    
    async def stop(self):
        """停止提醒管理器"""
        if not self.running:
            return
        
        self.running = False
        logger.info("停止自动提醒收货管理器...")
        
        # 取消所有提醒任务
        for cookie_id, task in self.reminder_tasks.items():
            if task and not task.done():
                task.cancel()
                logger.info(f"已取消账号 {cookie_id} 的提醒任务")
        
        self.reminder_tasks.clear()
        logger.info("自动提醒收货管理器已停止")
    
    async def start_reminder_task(self, cookie_id: str):
        """启动指定账号的提醒任务
        
        Args:
            cookie_id: 账号ID
        """
        # 如果任务已存在且正在运行，先取消
        if cookie_id in self.reminder_tasks:
            old_task = self.reminder_tasks[cookie_id]
            if old_task and not old_task.done():
                old_task.cancel()
                logger.info(f"取消账号 {cookie_id} 的旧提醒任务")
        
        # 创建新任务
        task = asyncio.create_task(self.reminder_check_loop(cookie_id))
        self.reminder_tasks[cookie_id] = task
        logger.info(f"已启动账号 {cookie_id} 的提醒任务")
    
    async def stop_reminder_task(self, cookie_id: str):
        """停止指定账号的提醒任务
        
        Args:
            cookie_id: 账号ID
        """
        if cookie_id in self.reminder_tasks:
            task = self.reminder_tasks[cookie_id]
            if task and not task.done():
                task.cancel()
                logger.info(f"已停止账号 {cookie_id} 的提醒任务")
            del self.reminder_tasks[cookie_id]
    
    async def reminder_check_loop(self, cookie_id: str):
        """提醒检查循环（每分钟执行一次）
        
        Args:
            cookie_id: 账号ID
        """
        logger.info(f"【{cookie_id}】提醒检查循环已启动")
        
        while self.running:
            try:
                # 检查并发送提醒
                await self.check_and_send_reminders(cookie_id)
                
                # 每分钟检查一次
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info(f"【{cookie_id}】提醒检查循环被取消")
                break
            except Exception as e:
                logger.error(f"【{cookie_id}】提醒检查失败: {e}")
                # 出错后等待1分钟再继续
                await asyncio.sleep(60)
    
    async def check_and_send_reminders(self, cookie_id: str):
        """检查并发送提醒
        
        Args:
            cookie_id: 账号ID
        """
        try:
            # 1. 获取该账号的提醒设置
            settings = db_manager.get_reminder_settings(cookie_id)
            if not settings or not settings.get('enabled'):
                return
            
            # 2. 获取需要提醒的订单列表
            current_time = datetime.now()
            pending_reminders = db_manager.get_pending_reminders(cookie_id, current_time)
            
            if not pending_reminders:
                return
            
            logger.info(f"【{cookie_id}】发现 {len(pending_reminders)} 个待提醒订单")
            
            # 3. 逐个处理提醒
            for reminder in pending_reminders:
                try:
                    # 检查是否应该提醒
                    if not self.should_remind(reminder, settings):
                        logger.info(f"【{cookie_id}】订单 {reminder['order_id']} 不满足提醒条件，跳过")
                        # 标记为已取消
                        db_manager.update_reminder_status(reminder['order_id'], 'cancelled')
                        continue
                    
                    # 发送提醒消息
                    success = await self.send_reminder_message(
                        order_id=reminder['order_id'],
                        buyer_id=reminder['buyer_id'],
                        cookie_id=cookie_id,
                        reminder_count=reminder['reminder_count']
                    )
                    
                    if success:
                        # 更新提醒记录
                        new_count = reminder['reminder_count'] + 1
                        next_time = self.calculate_next_reminder_time(
                            last_time=current_time,
                            settings=settings,
                            reminder_count=new_count
                        )
                        
                        # 检查是否达到最大提醒次数
                        if new_count >= settings['max_reminder_count']:
                            db_manager.update_reminder_record(
                                order_id=reminder['order_id'],
                                reminder_count=new_count,
                                last_reminder_time=current_time,
                                next_reminder_time=None,
                                status='completed'
                            )
                            logger.info(f"【{cookie_id}】订单 {reminder['order_id']} 已达到最大提醒次数，标记为完成")
                        else:
                            db_manager.update_reminder_record(
                                order_id=reminder['order_id'],
                                reminder_count=new_count,
                                last_reminder_time=current_time,
                                next_reminder_time=next_time,
                                status='pending'
                            )
                            logger.info(f"【{cookie_id}】订单 {reminder['order_id']} 提醒成功，下次提醒时间: {next_time}")
                    else:
                        logger.warning(f"【{cookie_id}】订单 {reminder['order_id']} 提醒发送失败")
                    
                    # 避免发送过快，间隔2秒
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"【{cookie_id}】处理订单 {reminder.get('order_id')} 提醒时出错: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"【{cookie_id}】检查并发送提醒时出错: {e}")
    
    def should_remind(self, reminder: Dict, settings: Dict) -> bool:
        """判断订单是否应该提醒
        
        Args:
            reminder: 提醒记录
            settings: 提醒设置
            
        Returns:
            bool: 是否应该提醒
        """
        try:
            order_id = reminder['order_id']
            buyer_id = reminder['buyer_id']
            cookie_id = reminder['cookie_id']
            
            # 1. 检查黑名单
            if settings.get('exclude_blacklist', True):
                if db_manager.is_blacklist_user(cookie_id, buyer_id):
                    logger.info(f"订单 {order_id} 的买家 {buyer_id} 在黑名单中，跳过提醒")
                    return False
            
            # 2. 检查是否有售后/投诉/纠纷
            if settings.get('exclude_dispute', True):
                if db_manager.has_dispute_record(order_id):
                    logger.info(f"订单 {order_id} 存在售后/投诉/纠纷记录，跳过提醒")
                    return False
            
            # 3. 检查是否是同行用户
            if settings.get('exclude_competitor', True):
                if db_manager.is_competitor_user(cookie_id, buyer_id):
                    logger.info(f"订单 {order_id} 的买家 {buyer_id} 是同行用户，跳过提醒")
                    return False
            
            # 4. 检查订单状态（必须是已发货状态）
            order = db_manager.get_order_by_id(order_id)
            if not order or order.get('order_status') != 'shipped':
                logger.info(f"订单 {order_id} 状态不是已发货，跳过提醒")
                return False
            
            # 5. 检查是否已经确认收货（订单状态变为completed）
            if order.get('order_status') == 'completed':
                logger.info(f"订单 {order_id} 已确认收货，跳过提醒")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"判断是否应该提醒时出错: {e}")
            return False
    
    async def send_reminder_message(self, order_id: str, buyer_id: str, 
                                   cookie_id: str, reminder_count: int) -> bool:
        """发送提醒消息
        
        Args:
            order_id: 订单ID
            buyer_id: 买家ID
            cookie_id: 账号ID
            reminder_count: 当前提醒次数
            
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
                logger.warning(f"【{cookie_id}】WebSocket连接未建立或已关闭，无法发送提醒")
                return False
            
            # 构造提醒消息（可以根据提醒次数调整消息内容）
            if reminder_count == 0:
                message = "亲，您的宝贝已经发货啦，记得及时确认收货哦~😊"
            elif reminder_count == 1:
                message = "亲，宝贝应该已经收到了吧？记得确认收货哦~🎁"
            else:
                message = "亲，如果宝贝已经收到，麻烦确认一下收货哦，谢谢~🙏"
            
            # 获取订单信息以获取item_id和chat_id
            order = db_manager.get_order_by_id(order_id)
            if not order:
                logger.error(f"【{cookie_id}】找不到订单信息: {order_id}")
                return False
            
            item_id = order.get('item_id', '')
            
            # 使用现有的WebSocket连接发送消息
            # 使用send_msg方法，这个方法使用已建立的WebSocket连接
            chat_id = f"{buyer_id}_{item_id}"  # 构造chat_id
            await instance.send_msg(instance.ws, chat_id, buyer_id, message)
            
            logger.info(f"【{cookie_id}】成功向买家 {buyer_id} 发送提醒消息（订单: {order_id}，第 {reminder_count + 1} 次提醒）")
            return True
            
        except Exception as e:
            logger.error(f"【{cookie_id}】发送提醒消息时出错: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def calculate_next_reminder_time(self, last_time: datetime, 
                                    settings: Dict, reminder_count: int) -> Optional[datetime]:
        """计算下次提醒时间
        
        Args:
            last_time: 上次提醒时间（或发货时间）
            settings: 提醒设置
            reminder_count: 当前提醒次数
            
        Returns:
            datetime: 下次提醒时间，如果不需要再提醒则返回None
        """
        try:
            # 检查是否达到最大提醒次数
            if reminder_count >= settings['max_reminder_count']:
                return None
            
            # 计算延迟时间
            if reminder_count == 0:
                # 首次提醒：使用首次延迟设置
                delay_value = settings.get('first_delay_value', 3)
                delay_unit = settings.get('first_delay_unit', 'days')
                
                if delay_unit == 'hours':
                    delay = timedelta(hours=delay_value)
                else:  # days
                    delay = timedelta(days=delay_value)
            else:
                # 后续提醒：使用提醒间隔
                interval_days = settings.get('reminder_interval', 2)
                delay = timedelta(days=interval_days)
            
            next_time = last_time + delay
            return next_time
            
        except Exception as e:
            logger.error(f"计算下次提醒时间时出错: {e}")
            return None
    
    def on_order_shipped(self, order_id: str, cookie_id: str, buyer_id: str, ship_time: datetime):
        """订单发货时的回调
        
        Args:
            order_id: 订单ID
            cookie_id: 账号ID
            buyer_id: 买家ID
            ship_time: 发货时间
        """
        try:
            # 获取提醒设置
            settings = db_manager.get_reminder_settings(cookie_id)
            if not settings or not settings.get('enabled'):
                logger.debug(f"【{cookie_id}】未启用自动提醒收货功能")
                return
            
            # 计算首次提醒时间
            next_reminder_time = self.calculate_next_reminder_time(
                last_time=ship_time,
                settings=settings,
                reminder_count=0
            )
            
            # 创建提醒记录
            db_manager.create_reminder_record(
                order_id=order_id,
                cookie_id=cookie_id,
                buyer_id=buyer_id,
                ship_time=ship_time,
                next_reminder_time=next_reminder_time
            )
            
            logger.info(f"【{cookie_id}】订单 {order_id} 已创建提醒记录，首次提醒时间: {next_reminder_time}")
            
        except Exception as e:
            logger.error(f"【{cookie_id}】创建提醒记录时出错: {e}")
    
    def on_order_completed(self, order_id: str):
        """订单完成时的回调（买家确认收货）
        
        Args:
            order_id: 订单ID
        """
        try:
            # 更新提醒记录状态为已完成
            db_manager.update_reminder_status(order_id, 'completed')
            logger.info(f"订单 {order_id} 已确认收货，提醒记录已标记为完成")
            
        except Exception as e:
            logger.error(f"更新提醒记录状态时出错: {e}")
    
    def scan_shipped_orders(self, cookie_id: str) -> Dict[str, int]:
        """扫描已发货订单并创建提醒记录
        
        Args:
            cookie_id: 账号ID
            
        Returns:
            Dict: 扫描结果统计 {'total': 总数, 'created': 新建数, 'skipped': 跳过数}
        """
        try:
            logger.info(f"【{cookie_id}】开始扫描已发货订单...")
            
            # 获取提醒设置
            settings = db_manager.get_reminder_settings(cookie_id)
            if not settings or not settings.get('enabled'):
                logger.warning(f"【{cookie_id}】未启用自动提醒收货功能")
                return {'total': 0, 'created': 0, 'skipped': 0, 'error': '未启用提醒功能'}
            
            # 获取该账号所有已发货的订单
            shipped_orders = db_manager.get_shipped_orders(cookie_id)
            
            total = len(shipped_orders)
            created = 0
            skipped = 0
            
            logger.info(f"【{cookie_id}】找到 {total} 个已发货订单")
            
            for order in shipped_orders:
                try:
                    order_id = order.get('order_id')
                    buyer_id = order.get('buyer_id')
                    ship_time_str = order.get('ship_time')
                    
                    # 检查是否已存在提醒记录
                    existing_record = db_manager.get_reminder_record(order_id)
                    if existing_record:
                        skipped += 1
                        continue
                    
                    # 解析发货时间
                    if ship_time_str:
                        try:
                            ship_time = datetime.fromisoformat(ship_time_str)
                        except:
                            ship_time = datetime.now()
                    else:
                        ship_time = datetime.now()
                    
                    # 计算首次提醒时间
                    next_reminder_time = self.calculate_next_reminder_time(
                        last_time=ship_time,
                        settings=settings,
                        reminder_count=0
                    )
                    
                    # 创建提醒记录
                    db_manager.create_reminder_record(
                        order_id=order_id,
                        cookie_id=cookie_id,
                        buyer_id=buyer_id,
                        ship_time=ship_time,
                        next_reminder_time=next_reminder_time
                    )
                    
                    created += 1
                    logger.debug(f"【{cookie_id}】为订单 {order_id} 创建提醒记录")
                    
                except Exception as e:
                    logger.error(f"【{cookie_id}】处理订单时出错: {e}")
                    skipped += 1
                    continue
            
            logger.info(f"【{cookie_id}】订单扫描完成: 总数={total}, 新建={created}, 跳过={skipped}")
            return {'total': total, 'created': created, 'skipped': skipped}
            
        except Exception as e:
            logger.error(f"【{cookie_id}】扫描已发货订单时出错: {e}")
            return {'total': 0, 'created': 0, 'skipped': 0, 'error': str(e)}


# 创建全局提醒管理器实例
reminder_manager = ReminderManager()
