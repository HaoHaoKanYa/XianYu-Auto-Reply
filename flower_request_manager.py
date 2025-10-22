"""
自动求小红花管理器
负责管理订单的自动求小红花功能
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from loguru import logger
from db_manager import db_manager


class FlowerRequestManager:
    """自动求小红花管理器"""
    
    def __init__(self):
        """初始化求小红花管理器"""
        self.flower_tasks = {}  # {cookie_id: asyncio.Task}
        self.running = False
        logger.info("自动求小红花管理器初始化完成")
    
    async def start(self):
        """启动求小红花管理器"""
        if self.running:
            logger.warning("求小红花管理器已经在运行中")
            return
        
        self.running = True
        logger.info("启动自动求小红花管理器...")
        
        # 获取所有启用了求小红花功能的账号
        enabled_cookies = db_manager.get_enabled_flower_request_cookies()
        
        for cookie_id in enabled_cookies:
            await self.start_flower_task(cookie_id)
        
        logger.info(f"自动求小红花管理器启动完成，已启动 {len(enabled_cookies)} 个账号的求小红花任务")
    
    async def stop(self):
        """停止求小红花管理器"""
        if not self.running:
            return
        
        self.running = False
        logger.info("停止自动求小红花管理器...")
        
        # 取消所有求小红花任务
        for cookie_id, task in self.flower_tasks.items():
            if task and not task.done():
                task.cancel()
                logger.info(f"已取消账号 {cookie_id} 的求小红花任务")
        
        self.flower_tasks.clear()
        logger.info("自动求小红花管理器已停止")
    
    async def start_flower_task(self, cookie_id: str):
        """启动指定账号的求小红花任务
        
        Args:
            cookie_id: 账号ID
        """
        # 如果任务已存在且正在运行，先取消
        if cookie_id in self.flower_tasks:
            old_task = self.flower_tasks[cookie_id]
            if old_task and not old_task.done():
                old_task.cancel()
                logger.info(f"取消账号 {cookie_id} 的旧求小红花任务")
        
        # 创建新任务
        task = asyncio.create_task(self.flower_check_loop(cookie_id))
        self.flower_tasks[cookie_id] = task
        logger.info(f"已启动账号 {cookie_id} 的求小红花任务")
    
    async def stop_flower_task(self, cookie_id: str):
        """停止指定账号的求小红花任务
        
        Args:
            cookie_id: 账号ID
        """
        if cookie_id in self.flower_tasks:
            task = self.flower_tasks[cookie_id]
            if task and not task.done():
                task.cancel()
                logger.info(f"已停止账号 {cookie_id} 的求小红花任务")
            del self.flower_tasks[cookie_id]
    
    async def flower_check_loop(self, cookie_id: str):
        """求小红花检查循环（每分钟执行一次）
        
        Args:
            cookie_id: 账号ID
        """
        logger.info(f"【{cookie_id}】求小红花检查循环已启动")
        
        while self.running:
            try:
                # 检查并发送求小红花
                await self.check_and_send_flower_requests(cookie_id)
                
                # 每分钟检查一次
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info(f"【{cookie_id}】求小红花检查循环被取消")
                break
            except Exception as e:
                logger.error(f"【{cookie_id}】求小红花检查失败: {e}")
                # 出错后等待1分钟再继续
                await asyncio.sleep(60)
    
    async def check_and_send_flower_requests(self, cookie_id: str):
        """检查并发送求小红花
        
        Args:
            cookie_id: 账号ID
        """
        try:
            # 1. 获取该账号的求小红花设置
            settings = db_manager.get_flower_request_settings(cookie_id)
            if not settings or not settings.get('enabled'):
                return
            
            # 2. 获取需要求小红花的订单列表
            current_time = datetime.now()
            pending_requests = db_manager.get_pending_flower_requests(cookie_id, current_time)
            
            if not pending_requests:
                return
            
            logger.info(f"【{cookie_id}】发现 {len(pending_requests)} 个待求小红花订单")
            
            # 3. 逐个处理求小红花
            for request in pending_requests:
                try:
                    # 检查是否应该求小红花
                    if not self.should_request_flower(request, settings):
                        logger.info(f"【{cookie_id}】订单 {request['order_id']} 不满足求小红花条件，跳过")
                        # 标记为已取消
                        db_manager.update_flower_request_status(request['order_id'], 'cancelled')
                        continue
                    
                    # 发送求小红花消息
                    success = await self.send_flower_request_message(
                        order_id=request['order_id'],
                        buyer_id=request['buyer_id'],
                        cookie_id=cookie_id
                    )
                    
                    if success:
                        # 更新求小红花记录为已完成
                        db_manager.update_flower_request_record(
                            order_id=request['order_id'],
                            request_time=current_time,
                            status='completed'
                        )
                        logger.info(f"【{cookie_id}】订单 {request['order_id']} 求小红花成功")
                    else:
                        logger.warning(f"【{cookie_id}】订单 {request['order_id']} 求小红花发送失败")
                    
                    # 避免发送过快，间隔2秒
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"【{cookie_id}】处理订单 {request.get('order_id')} 求小红花时出错: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"【{cookie_id}】检查并发送求小红花时出错: {e}")
    
    def should_request_flower(self, request: Dict, settings: Dict) -> bool:
        """判断订单是否应该求小红花
        
        Args:
            request: 求小红花记录
            settings: 求小红花设置
            
        Returns:
            bool: 是否应该求小红花
        """
        try:
            order_id = request['order_id']
            buyer_id = request['buyer_id']
            cookie_id = request['cookie_id']
            
            # 1. 检查黑名单
            if settings.get('exclude_blacklist', True):
                if db_manager.is_blacklist_user(cookie_id, buyer_id):
                    logger.info(f"订单 {order_id} 的买家 {buyer_id} 在黑名单中，跳过求小红花")
                    return False
            
            # 2. 检查是否有售后/投诉/纠纷
            if settings.get('exclude_dispute', True):
                if db_manager.has_dispute_record(order_id):
                    logger.info(f"订单 {order_id} 存在售后/投诉/纠纷记录，跳过求小红花")
                    return False
            
            # 3. 检查是否是同行用户
            if settings.get('exclude_competitor', True):
                if db_manager.is_competitor_user(cookie_id, buyer_id):
                    logger.info(f"订单 {order_id} 的买家 {buyer_id} 是同行用户，跳过求小红花")
                    return False
            
            # 4. 检查订单状态（必须是已发货状态）
            order = db_manager.get_order_by_id(order_id)
            if not order or order.get('order_status') != 'shipped':
                logger.info(f"订单 {order_id} 状态不是已发货，跳过求小红花")
                return False
            
            # 5. 检查是否已经确认收货（订单状态变为completed）
            if order.get('order_status') == 'completed':
                logger.info(f"订单 {order_id} 已确认收货，跳过求小红花")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"判断是否应该求小红花时出错: {e}")
            return False
    
    async def send_flower_request_message(self, order_id: str, buyer_id: str, cookie_id: str) -> bool:
        """发送求小红花消息
        
        Args:
            order_id: 订单ID
            buyer_id: 买家ID
            cookie_id: 账号ID
            
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
                logger.warning(f"【{cookie_id}】WebSocket连接未建立或已关闭，无法发送求小红花")
                return False
            
            # 构造求小红花消息
            message = "亲，如果对宝贝满意的话，麻烦给个小红花好评哦~您的支持是我最大的动力！🌸😊"
            
            # 获取订单信息以获取item_id和chat_id
            order = db_manager.get_order_by_id(order_id)
            if not order:
                logger.error(f"【{cookie_id}】找不到订单信息: {order_id}")
                return False
            
            item_id = order.get('item_id', '')
            
            # 使用现有的WebSocket连接发送消息
            chat_id = f"{buyer_id}_{item_id}"  # 构造chat_id
            await instance.send_msg(instance.ws, chat_id, buyer_id, message)
            
            logger.info(f"【{cookie_id}】成功向买家 {buyer_id} 发送求小红花消息（订单: {order_id}）")
            return True
            
        except Exception as e:
            logger.error(f"【{cookie_id}】发送求小红花消息时出错: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def calculate_request_time(self, ship_time: datetime, settings: Dict) -> Optional[datetime]:
        """计算求小红花时间
        
        Args:
            ship_time: 发货时间
            settings: 求小红花设置
            
        Returns:
            datetime: 求小红花时间
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
            
            request_time = ship_time + delay
            return request_time
            
        except Exception as e:
            logger.error(f"计算求小红花时间时出错: {e}")
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
            # 获取求小红花设置
            settings = db_manager.get_flower_request_settings(cookie_id)
            if not settings or not settings.get('enabled'):
                logger.debug(f"【{cookie_id}】未启用自动求小红花功能")
                return
            
            # 计算求小红花时间
            request_time = self.calculate_request_time(
                ship_time=ship_time,
                settings=settings
            )
            
            # 创建求小红花记录
            db_manager.create_flower_request_record(
                order_id=order_id,
                cookie_id=cookie_id,
                buyer_id=buyer_id,
                ship_time=ship_time,
                request_time=request_time
            )
            
            logger.info(f"【{cookie_id}】订单 {order_id} 已创建求小红花记录，求小红花时间: {request_time}")
            
        except Exception as e:
            logger.error(f"【{cookie_id}】创建求小红花记录时出错: {e}")
    
    def on_order_completed(self, order_id: str):
        """订单完成时的回调（买家确认收货）
        
        Args:
            order_id: 订单ID
        """
        try:
            # 更新求小红花记录状态为已完成
            db_manager.update_flower_request_status(order_id, 'completed')
            logger.info(f"订单 {order_id} 已确认收货，求小红花记录已标记为完成")
            
        except Exception as e:
            logger.error(f"更新求小红花记录状态时出错: {e}")
    
    def scan_shipped_orders(self, cookie_id: str) -> Dict[str, int]:
        """扫描已发货订单并创建求小红花记录
        
        Args:
            cookie_id: 账号ID
            
        Returns:
            Dict: 扫描结果统计 {'total': 总数, 'created': 新建数, 'skipped': 跳过数}
        """
        try:
            logger.info(f"【{cookie_id}】开始扫描已发货订单...")
            
            # 获取求小红花设置
            settings = db_manager.get_flower_request_settings(cookie_id)
            if not settings or not settings.get('enabled'):
                logger.warning(f"【{cookie_id}】未启用自动求小红花功能")
                return {'total': 0, 'created': 0, 'skipped': 0, 'error': '未启用求小红花功能'}
            
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
                    
                    # 检查是否已存在求小红花记录
                    existing_record = db_manager.get_flower_request_record(order_id)
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
                    
                    # 计算求小红花时间
                    request_time = self.calculate_request_time(
                        ship_time=ship_time,
                        settings=settings
                    )
                    
                    # 创建求小红花记录
                    db_manager.create_flower_request_record(
                        order_id=order_id,
                        cookie_id=cookie_id,
                        buyer_id=buyer_id,
                        ship_time=ship_time,
                        request_time=request_time
                    )
                    
                    created += 1
                    logger.debug(f"【{cookie_id}】为订单 {order_id} 创建求小红花记录")
                    
                except Exception as e:
                    logger.error(f"【{cookie_id}】处理订单时出错: {e}")
                    skipped += 1
                    continue
            
            logger.info(f"【{cookie_id}】订单扫描完成: 总数={total}, 新建={created}, 跳过={skipped}")
            return {'total': total, 'created': created, 'skipped': skipped}
            
        except Exception as e:
            logger.error(f"【{cookie_id}】扫描已发货订单时出错: {e}")
            return {'total': 0, 'created': 0, 'skipped': 0, 'error': str(e)}


# 创建全局求小红花管理器实例
flower_request_manager = FlowerRequestManager()
