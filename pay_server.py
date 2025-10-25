from flask import Flask, request
from datetime import datetime
import random, string
import pymongo
import telegram
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import os
import logging
from telegram.ext import CallbackContext
from dotenv import load_dotenv

# 日志设置
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f"{log_dir}/flask_callback.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logging.info("Flask 回调服务已启动")

# 加载环境变量
load_dotenv()

# --- 新增：容错解析整型列表（忽略行内注释/空白/非法项） ---
def _parse_int_list_env(key: str, default=None):
    """
    解析形如 '12345, 67890  # 注释' 的整型ID列表环境变量：
    - 去掉行内 # 注释
    - 逗号分隔并 strip
    - 仅保留纯数字（可带负号）的项，转换为 int
    """
    raw = os.getenv(key, "")
    if raw is None:
        return default or []
    # 去掉行内注释
    raw = str(raw).split('#', 1)[0]
    ids = []
    for part in raw.split(','):
        p = part.strip()
        if not p:
            continue
        if p.lstrip('-').isdigit():
            try:
                ids.append(int(p))
            except Exception:
                logging.warning(f"{key}: 跳过无法转换的项: {p}")
        else:
            logging.warning(f"{key}: 跳过非数字项: {p}")
    return ids or (default or [])

# ✅ 配置类集中管理
class Config:
    # Bot 配置
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    # 原：ADMIN_IDS = list(map(int, filter(None, os.getenv("ADMIN_IDS", "").split(","))))
    ADMIN_IDS = _parse_int_list_env("ADMIN_IDS", default=[])
    
    # 数据库配置
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "xc1111bot")
    
    # Flask 配置
    FLASK_PORT = int(os.getenv("FLASK_PORT", 8000))
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    
    # 订单配置
    ORDER_EXPIRE_MINUTES = int(os.getenv("ORDER_EXPIRE_MINUTES", 10))
    CLEANUP_INTERVAL_MINUTES = int(os.getenv("CLEANUP_INTERVAL_MINUTES", 3))
    
    # 金额匹配容差
    MONEY_TOLERANCE = float(os.getenv("MONEY_TOLERANCE", "0.01"))
    
    @classmethod
    def validate(cls):
        """验证必要的配置"""
        if not cls.BOT_TOKEN:
            raise ValueError("❌ BOT_TOKEN 环境变量未设置")
        if not cls.ADMIN_IDS:
            logging.warning("⚠️ ADMIN_IDS 未设置，无法发送管理员通知（支持形如：ADMIN_IDS=\"123,456\"）")
        logging.info("✅ 配置验证通过")

# 验证配置
Config.validate()

# ✅ 数据库和 Bot 初始化优化
class DatabaseManager:
    def __init__(self):
        self.client = pymongo.MongoClient(Config.MONGO_URI)
        self.db = self.client[Config.MONGO_DB_NAME]
        self.topup = self.db['topup']
        self.user = self.db['user']
        logging.info("✅ 数据库连接初始化完成")
    
    def close(self):
        self.client.close()
        logging.info("✅ 数据库连接已关闭")

class BotManager:
    def __init__(self):
        self.bot = telegram.Bot(token=Config.BOT_TOKEN)
        logging.info("✅ Telegram Bot 初始化完成")
    
    def send_message_safe(self, chat_id, text, **kwargs):
        """安全发送消息，带错误处理"""
        try:
            return self.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except Exception as e:
            logging.error(f"❌ 发送消息失败 (chat_id={chat_id}): {e}")
            return None
    
    def delete_message_safe(self, chat_id, message_id):
        """安全删除消息，带错误处理"""
        try:
            return self.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logging.warning(f"⚠️ 删除消息失败 (chat_id={chat_id}, msg_id={message_id}): {e}")
            return None

# 初始化管理器
db_manager = DatabaseManager()
bot_manager = BotManager()

# ✅ 为了向后兼容，保留原有变量名
client = db_manager.client
db = db_manager.db
topup = db_manager.topup
user = db_manager.user
bot = bot_manager.bot
app = Flask(__name__)

# 根路由，用于健康检查
@app.route("/")
def index():
    return "机器人回调服务正在运行", 200

# ✅ 订单处理工具类
class OrderProcessor:
    @staticmethod
    def generate_order_id():
        """生成唯一订单号"""
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        rand = ''.join(random.choices(string.digits, k=6))
        return now + rand
    
    @staticmethod
    def find_matching_order(orderid, money):
        """查找匹配的订单"""
        try:
            # 🔧 每次都创建新的数据库连接，避免使用已关闭的连接
            mongo_client = pymongo.MongoClient(Config.MONGO_URI)
            mongo_db = mongo_client[Config.MONGO_DB_NAME]
            mongo_topup = mongo_db['topup']
            
            tolerance = Config.MONEY_TOLERANCE
            order = mongo_topup.find_one({
                'bianhao': orderid,
                'status': 'pending',
                'money': {
                    '$gte': round(money - tolerance, 2), 
                    '$lte': round(money + tolerance, 2)
                }
            })
            
            # 查询完成后关闭连接
            mongo_client.close()
            
            if order:
                logging.info(f"✅ 找到匹配订单：{orderid}, 金额：{money}")
            else:
                logging.warning(f"❌ 未找到匹配订单：{orderid}, 金额：{money}")
            
            return order
        except Exception as e:
            logging.error(f"❌ 查找订单时发生错误：{e}")
            return None
    
    @staticmethod
    def process_payment(order, money):
        """处理支付逻辑（幂等：仅处理 pending 订单）"""
        try:
            # 🔧 每次都创建新的数据库连接，避免使用已关闭的连接
            mongo_client = pymongo.MongoClient(Config.MONGO_URI)
            mongo_db = mongo_client[Config.MONGO_DB_NAME]
            mongo_topup = mongo_db['topup']
            mongo_user = mongo_db['user']
            
            # 再读一遍订单，确保 status 仍是 pending，避免并发重复入账
            fresh = mongo_topup.find_one({'_id': order['_id']})
            if not fresh or fresh.get('status') != 'pending':
                logging.warning(f"⏩ 订单已处理或不存在，跳过：{order.get('bianhao')}")
                mongo_client.close()
                return None

            user_id = fresh['user_id']
            usdt = float(fresh['usdt'])
            
            # 获取用户信息
            user_doc = mongo_user.find_one({'user_id': user_id})
            if not user_doc:
                logging.error(f"❌ 未找到用户记录 user_id={user_id}")
                mongo_client.close()
                return None
            
            old_balance = float(user_doc.get('USDT', 0))
            new_balance = round(old_balance + usdt, 2)
            
            # 原子更新：将订单置成功
            mongo_topup.update_one(
                {'_id': fresh['_id'], 'status': 'pending'},
                {
                    '$set': {
                        'status': 'success',
                        'cz_type': fresh.get('cz_type', 'usdt'),
                        'time': datetime.now(),
                        'actual_money': money  # 记录实际支付金额
                    }
                }
            )
            
            # 更新用户余额
            mongo_user.update_one({'user_id': user_id}, {'$inc': {'USDT': usdt}})
            
            # 处理完成后关闭连接
            mongo_client.close()
            
            logging.info(f"✅ 支付处理成功：订单号 {fresh['bianhao']}，金额 {usdt}，新余额 {new_balance}")
            
            return {
                'user_id': user_id,
                'usdt': usdt,
                'old_balance': old_balance,
                'new_balance': new_balance,
                'user_doc': user_doc,
                'order': fresh
            }
        except Exception as e:
            logging.error(f"❌ 支付处理失败：{e}")
            return None

# 生成订单号（向后兼容）
def generate_order_id():
    return OrderProcessor.generate_order_id()

# ✅ 通知管理类
class NotificationManager:
    @staticmethod
    def create_payment_success_message(user_info, payment_info):
        """创建支付成功消息"""
        user_doc = user_info['user_doc']
        username = user_doc.get('username', '未知')
        fullname = user_doc.get('fullname', f'用户{user_info["user_id"]}')
        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return (
            "<b>充值成功通知</b>\n"
            "------------------------\n"
            f"<b>用户昵称：</b>{fullname} @{username}\n"
            f"<b>用户 ID：</b><code>{user_info['user_id']}</code>\n"
            f"<b>充值金额：</b>{user_info['usdt']:.2f} USDT\n"
            f"<b>充值前余额：</b>{user_info['old_balance']:.2f} USDT\n"
            f"<b>充值后余额：</b>{user_info['new_balance']:.2f} USDT\n"
            f"<b>订单编号：</b><code>{user_info['order']['bianhao']}</code>\n"
            f"<b>到账时间：</b>{now_time}\n"
        )
    
    @staticmethod
    def send_user_notification(user_info):
        """发送用户通知"""
        message = NotificationManager.create_payment_success_message(user_info, None)
        
        return bot_manager.send_message_safe(
            chat_id=user_info['user_id'],
            text=message,
            parse_mode='HTML',
            reply_markup=telegram.InlineKeyboardMarkup([
                [telegram.InlineKeyboardButton("已读", callback_data=f"close {user_info['user_id']}")]
            ])
        )
    
    @staticmethod
    def send_admin_notifications(user_info):
        """发送管理员通知"""
        message = NotificationManager.create_payment_success_message(user_info, None)
        admin_message = message.replace("充值成功通知", "用户充值到账通知")
        
        success_count = 0
        for admin_id in Config.ADMIN_IDS:
            result = bot_manager.send_message_safe(
                chat_id=admin_id,
                text=admin_message,
                parse_mode='HTML',
                reply_markup=telegram.InlineKeyboardMarkup([
                    [telegram.InlineKeyboardButton("已读", callback_data=f"close {user_info['user_id']}")]
                ])
            )
            if result:
                success_count += 1
                logging.info(f"✅ 管理员通知成功：{admin_id}")
        
        logging.info(f"📢 管理员通知完成：{success_count}/{len(Config.ADMIN_IDS)}")
    
    @staticmethod
    def delete_payment_message(order):
        """删除支付消息"""
        msg_id = order.get('message_id') or order.get('msg_id')
        if msg_id:
            bot_manager.delete_message_safe(order['user_id'], msg_id)

# 导入签名验证函数
from utils import verify_easypay_sign

# 回调接口
@app.route("/callback", methods=["GET", "POST"])
def callback():
    try:
        data = request.values.to_dict()
        logging.info(f"📥 收到回调数据：{data}")

        # 🔐 第一步：验证签名（重要安全检查）
        easypay_key = os.getenv("EASYPAY_KEY")
        if not verify_easypay_sign(data, easypay_key):
            logging.warning(f"❌ 签名验证失败：{data}")
            return "invalid signature", 403

        # 🔍 第二步：提取关键参数
        orderid = data.get("out_trade_no") or data.get("orderid")
        money = float(data.get("money", 0))
        trade_status = data.get("trade_status", "")
        
        # 检查参数有效性
        if not orderid or money <= 0:
            logging.warning("❌ 无效的回调数据")
            return "invalid data", 400

        # 检查交易状态（只处理成功的支付）
        if trade_status.upper() != "TRADE_SUCCESS":
            logging.warning(f"❌ 交易状态异常：{trade_status}")
            return "trade status error", 400

        logging.info(f"🔍 正在匹配订单号：{orderid}，金额：{money}，状态：{trade_status}")

        # 🔄 第三步：查找匹配订单
        order = OrderProcessor.find_matching_order(orderid, money)
        if not order:
            logging.warning(f"❌ 未找到匹配订单：{orderid}")
            return "order not found", 404

        # 🏦 第四步：处理支付
        payment_info = OrderProcessor.process_payment(order, money)
        if not payment_info:
            logging.error(f"❌ 支付处理失败：{orderid}")
            return "payment processing failed", 500

        # 🗑️ 第五步：删除原支付消息
        NotificationManager.delete_payment_message(order)

        # 📢 第六步：发送通知
        NotificationManager.send_user_notification(payment_info)
        NotificationManager.send_admin_notifications(payment_info)

        logging.info(f"🎉 支付回调处理完成：{orderid}")
        return "success"
        
    except Exception as e:
        logging.error(f"❌ 回调处理失败：{e}")
        return "internal error", 500

# ✅ 订单清理管理类
class OrderCleanupManager:
    @staticmethod
    def clear_expired_orders():
        """清理超时订单"""
        try:
            now = datetime.now()
            expired_query = {'status': 'pending', 'expire_time': {'$lt': now}}
            
            # 统计超时订单数量
            count = topup.count_documents(expired_query)
            if count == 0:
                return
            
            logging.info(f"🧹 发现 {count} 条超时订单，开始清理")
            
            # 获取超时订单
            expired_orders = topup.find(expired_query)
            processed_count = 0
            
            for order in expired_orders:
                try:
                    # 更新订单状态
                    topup.update_one(
                        {'_id': order['_id']}, 
                        {'$set': {'status': 'expired', 'expired_at': now}}
                    )
                    
                    # 删除支付消息
                    NotificationManager.delete_payment_message(order)
                    
                    # 发送超时通知
                    OrderCleanupManager._send_timeout_notification(order)
                    
                    processed_count += 1
                    
                except Exception as e:
                    logging.error(f"❌ 处理超时订单失败 {order.get('bianhao', '未知')}: {e}")
            
            logging.info(f"✅ 超时订单清理完成：{processed_count}/{count}")
            
        except Exception as e:
            logging.error(f"❌ 订单清理失败：{e}")
    
    @staticmethod
    def _send_timeout_notification(order):
        """发送超时通知"""
        try:
            timeout_message = (
                "<b>充值订单已超时</b>\n"
                "------------------------\n"
                f"<b>订单号：</b><code>{order['bianhao']}</code>\n"
                f"<b>金额：</b>{order.get('money', '?')} 元\n"
                f"<b>USDT金额：</b>{order.get('usdt', '?')} USDT\n"
                f"<b>创建时间：</b>{order.get('create_time', '未知')}\n"
                f"<b>到期时间：</b>{order.get('expire_time', '未知')}\n"
                "------------------------\n"
                f"由于超过 {Config.ORDER_EXPIRE_MINUTES} 分钟未支付，订单已被系统自动取消。\n"
                "如需继续充值，请重新发起充值请求。"
            )
            
            result = bot_manager.send_message_safe(
                chat_id=order['user_id'],
                text=timeout_message,
                parse_mode='HTML',
                reply_markup=telegram.InlineKeyboardMarkup([
                    [telegram.InlineKeyboardButton("已读", callback_data=f"close {order['user_id']}")]
                ])
            )
            
            if result:
                logging.info(f"✅ 超时通知已发送：user_id={order['user_id']}")
            
        except Exception as e:
            logging.error(f"❌ 发送超时通知失败：{e}")

# 定时清理超时订单（向后兼容）
def clear_expired_orders():
    OrderCleanupManager.clear_expired_orders()

# ✅ 服务管理类
class FlaskServerManager:
    def __init__(self):
        self.scheduler = None
        
    def setup_scheduler(self):
        """设置定时任务"""
        try:
            self.scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Shanghai'))
            self.scheduler.add_job(
                clear_expired_orders, 
                'interval', 
                minutes=Config.CLEANUP_INTERVAL_MINUTES,
                id='cleanup_expired_orders',
                replace_existing=True
            )
            self.scheduler.start()
            logging.info(f"⏰ 定时任务启动，每 {Config.CLEANUP_INTERVAL_MINUTES} 分钟清理一次超时订单")
        except Exception as e:
            logging.error(f"❌ 定时任务启动失败：{e}")
    
    def start_server(self):
        """启动 Flask 服务"""
        try:
            self.setup_scheduler()
            logging.info(f"🚀 启动 Flask 服务：{Config.FLASK_HOST}:{Config.FLASK_PORT}")
            app.run(
                host=Config.FLASK_HOST, 
                port=Config.FLASK_PORT, 
                threaded=True,
                debug=False
            )
        except Exception as e:
            logging.error(f"❌ Flask 服务启动失败：{e}")
        finally:
            if self.scheduler:
                self.scheduler.shutdown()
                logging.info("⏰ 定时任务已停止")
            db_manager.close()

# 启动 Flask 服务及定时任务（向后兼容）
def start_flask_server():
    server_manager = FlaskServerManager()
    server_manager.start_server()

# ✅ 优雅关闭处理
import signal
import sys

def signal_handler(sig, frame):
    logging.info("📴 收到停止信号，正在优雅关闭...")
    db_manager.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ✅ 程序入口
if __name__ == "__main__":
    logging.info("🎯 支付回调服务启动中...")
    start_flask_server()
