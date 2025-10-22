"""
自动好评管理器
负责在买家确认收货后自动给订单好评
"""

import asyncio
import time
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from loguru import logger


class AutoReviewManager:
    """自动好评管理器"""
    
    def __init__(self):
        """初始化自动好评管理器"""
        self.running = False
        self.check_task = None
        self.check_interval = 60  # 检查间隔（秒）
        
        logger.info("自动好评管理器初始化完成")
    
    async def start(self):
        """启动自动好评管理器"""
        if self.running:
            logger.warning("自动好评管理器已在运行中")
            return
        
        self.running = True
        self.check_task = asyncio.create_task(self._check_loop())
        logger.info("自动好评管理器已启动")
    
    async def stop(self):
        """停止自动好评管理器"""
        if not self.running:
            return
        
        self.running = False
        if self.check_task:
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
        
        logger.info("自动好评管理器已停止")
    
    async def _check_loop(self):
        """定期检查需要自动好评的订单"""
        logger.info("自动好评检查循环已启动")
        
        while self.running:
            try:
                await self._check_and_review_orders()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"自动好评检查循环出错: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_and_review_orders(self):
        """检查并处理需要自动好评的订单"""
        try:
            from db_manager import db_manager
            
            # 获取所有启用了自动好评的账号
            enabled_cookies = db_manager.get_auto_review_enabled_cookies()
            
            if not enabled_cookies:
                return
            
            logger.debug(f"检查到 {len(enabled_cookies)} 个启用自动好评的账号")
            
            for cookie_info in enabled_cookies:
                cookie_id = cookie_info['cookie_id']
                settings = cookie_info['settings']
                
                try:
                    # 获取该账号待好评的订单
                    pending_orders = db_manager.get_pending_review_orders(cookie_id)
                    
                    if not pending_orders:
                        continue
                    
                    logger.info(f"账号 {cookie_id} 有 {len(pending_orders)} 个待好评订单")
                    
                    for order in pending_orders:
                        try:
                            await self._process_review_order(order, settings, cookie_id)
                        except Exception as e:
                            logger.error(f"处理订单 {order['order_id']} 自动好评失败: {e}")
                
                except Exception as e:
                    logger.error(f"处理账号 {cookie_id} 自动好评失败: {e}")
        
        except Exception as e:
            logger.error(f"检查自动好评订单失败: {e}")
    
    async def _process_review_order(self, order: Dict, settings: Dict, cookie_id: str):
        """处理单个订单的自动好评
        
        Args:
            order: 订单信息
            settings: 自动好评设置
            cookie_id: Cookie ID
        """
        order_id = order['order_id']
        buyer_id = order.get('buyer_id', '')
        completed_time = order.get('completed_time')
        
        # 检查是否满足不评价条件
        if await self._should_skip_review(order, settings, cookie_id):
            logger.info(f"订单 {order_id} 满足不评价条件，跳过自动好评")
            # 更新记录状态为已跳过
            from db_manager import db_manager
            db_manager.update_auto_review_record_status(order_id, 'skipped', '满足不评价条件')
            return
        
        # 检查是否到达好评时间
        if not self._is_review_time_reached(completed_time, settings):
            return
        
        # 执行自动好评
        success = await self._send_review(order_id, cookie_id, settings)
        
        if success:
            logger.info(f"订单 {order_id} 自动好评成功")
        else:
            logger.error(f"订单 {order_id} 自动好评失败")
    
    async def _should_skip_review(self, order: Dict, settings: Dict, cookie_id: str) -> bool:
        """检查是否应该跳过自动好评
        
        Args:
            order: 订单信息
            settings: 自动好评设置
            cookie_id: Cookie ID
            
        Returns:
            bool: 是否应该跳过
        """
        from db_manager import db_manager
        
        order_id = order['order_id']
        buyer_id = order.get('buyer_id', '')
        
        # 检查买家差评
        if settings.get('exclude_bad_review', False):
            buyer_review = db_manager.get_buyer_review(order_id, cookie_id)
            if buyer_review and buyer_review.get('rating') == 'bad':
                logger.info(f"订单 {order_id} 买家已差评，跳过自动好评")
                return True
        
        # 检查买家中评
        if settings.get('exclude_medium_review', False):
            buyer_review = db_manager.get_buyer_review(order_id, cookie_id)
            if buyer_review and buyer_review.get('rating') == 'medium':
                logger.info(f"订单 {order_id} 买家已中评，跳过自动好评")
                return True
        
        # 检查黑名单用户
        if settings.get('exclude_blacklist', False):
            if db_manager.is_blacklist_user(cookie_id, buyer_id):
                logger.info(f"订单 {order_id} 买家在黑名单中，跳过自动好评")
                return True
        
        # 检查售后/投诉/纠纷记录
        if settings.get('exclude_dispute', False):
            if db_manager.has_dispute_record(order_id, cookie_id):
                logger.info(f"订单 {order_id} 存在售后/投诉/纠纷记录，跳过自动好评")
                return True
        
        # 检查同行用户
        if settings.get('exclude_competitor', False):
            if db_manager.is_competitor_user(cookie_id, buyer_id):
                logger.info(f"订单 {order_id} 买家是同行用户，跳过自动好评")
                return True
        
        # 检查敏感词
        sensitive_words = settings.get('sensitive_words', '')
        if sensitive_words:
            buyer_review = db_manager.get_buyer_review(order_id, cookie_id)
            if buyer_review:
                review_content = buyer_review.get('content', '')
                words_list = [w.strip() for w in sensitive_words.split('\\') if w.strip()]
                for word in words_list:
                    if word in review_content:
                        logger.info(f"订单 {order_id} 买家评价包含敏感词 '{word}'，跳过自动好评")
                        return True
        
        return False
    
    def _is_review_time_reached(self, completed_time: Optional[str], settings: Dict) -> bool:
        """检查是否到达好评时间
        
        Args:
            completed_time: 确认收货时间
            settings: 自动好评设置
            
        Returns:
            bool: 是否到达好评时间
        """
        if not completed_time:
            return False
        
        try:
            # 解析确认收货时间
            completed_dt = datetime.fromisoformat(completed_time.replace('Z', '+00:00'))
            
            # 获取延迟设置
            delay_value = settings.get('delay_value', 0)
            delay_unit = settings.get('delay_unit', 'seconds')
            
            # 计算延迟时间
            if delay_unit == 'seconds':
                delay = timedelta(seconds=delay_value)
            elif delay_unit == 'minutes':
                delay = timedelta(minutes=delay_value)
            elif delay_unit == 'hours':
                delay = timedelta(hours=delay_value)
            else:
                delay = timedelta(seconds=delay_value)
            
            # 计算目标好评时间
            review_time = completed_dt + delay
            
            # 检查是否到达好评时间
            return datetime.now() >= review_time
        
        except Exception as e:
            logger.error(f"检查好评时间失败: {e}")
            return False
    
    async def _send_review(self, order_id: str, cookie_id: str, settings: Dict) -> bool:
        """发送自动好评
        
        Args:
            order_id: 订单ID
            cookie_id: Cookie ID
            settings: 自动好评设置
            
        Returns:
            bool: 是否成功
        """
        try:
            from db_manager import db_manager
            import cookie_manager as cm
            
            # 获取随机好评模板
            template = db_manager.get_random_review_template(cookie_id)
            if not template:
                logger.error(f"账号 {cookie_id} 没有可用的好评模板")
                db_manager.update_auto_review_record_status(order_id, 'failed', '没有可用的好评模板')
                return False
            
            review_content = template['content']
            
            # 获取 XianyuAutoAsync 实例
            xianyu_instance = cm.manager.get_xianyu_instance(cookie_id)
            if not xianyu_instance:
                logger.error(f"无法获取账号 {cookie_id} 的 XianyuAutoAsync 实例")
                db_manager.update_auto_review_record_status(order_id, 'failed', '无法获取账号实例')
                return False
            
            # 调用闲鱼API发送好评
            success = await xianyu_instance.send_review(order_id, review_content)
            
            if success:
                # 更新记录状态
                db_manager.update_auto_review_record_status(
                    order_id, 
                    'completed', 
                    f'已使用模板: {template["id"]}'
                )
                logger.info(f"订单 {order_id} 自动好评成功: {review_content}")
                return True
            else:
                db_manager.update_auto_review_record_status(order_id, 'failed', 'API调用失败')
                return False
        
        except Exception as e:
            logger.error(f"发送自动好评失败: {e}")
            from db_manager import db_manager
            db_manager.update_auto_review_record_status(order_id, 'failed', str(e))
            return False
    
    def on_order_completed(self, order_id: str, cookie_id: str, buyer_id: str):
        """订单完成时的回调
        
        Args:
            order_id: 订单ID
            cookie_id: Cookie ID
            buyer_id: 买家ID
        """
        try:
            from db_manager import db_manager
            
            # 检查是否启用了自动好评
            settings = db_manager.get_auto_review_settings(cookie_id)
            if not settings or not settings.get('enabled', False):
                return
            
            # 创建自动好评记录
            db_manager.create_auto_review_record(
                order_id=order_id,
                cookie_id=cookie_id,
                buyer_id=buyer_id,
                completed_time=datetime.now().isoformat()
            )
            
            logger.info(f"订单 {order_id} 已创建自动好评记录")
        
        except Exception as e:
            logger.error(f"创建自动好评记录失败: {e}")


# 全局实例
auto_review_manager = AutoReviewManager()
