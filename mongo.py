import json
import random
import re
import pymongo
from pymongo.collection import Collection
import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
import time
from dotenv import load_dotenv
import os
import threading

# 加载环境变量
load_dotenv()

# ✅ 初始化日志系统
def init_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(f"{log_dir}/init.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logging.info("📌 日志系统初始化完成")

init_logging()

# ✅ 环境变量配置集中管理
class Config:
    # MongoDB 配置
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://127.0.0.1:27017/')
    MONGO_DB_BOT = os.getenv('MONGO_DB_BOT', 'xc1111bot')
    MONGO_DB_XCHP = os.getenv('MONGO_DB_XCHP', 'xc1111bot')
    MONGO_DB_MAIN = os.getenv('MONGO_DB_MAIN', 'qukuailian')
    
    # 客服联系方式
    CUSTOMER_SERVICE = os.getenv('CUSTOMER_SERVICE', '@lwmmm')
    OFFICIAL_CHANNEL = os.getenv('OFFICIAL_CHANNEL', '@XCZHCS')
    RESTOCK_GROUP = os.getenv('RESTOCK_GROUP', 'https://t.me/+EeTF1qOe_MoyMzQ0')
    
    # Bot 配置
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    BOT_USERNAME = os.getenv('BOT_USERNAME', 'xc1111bot')
    NOTIFY_CHANNEL_ID = int(os.getenv("NOTIFY_CHANNEL_ID", "0"))
    
    # 时间配置
    STOCK_NOTIFICATION_DELAY = int(os.getenv('STOCK_NOTIFICATION_DELAY', '3'))
    MESSAGE_DELETE_DELAY = int(os.getenv('MESSAGE_DELETE_DELAY', '3'))
    
    # 验证关键配置
    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError("❌ BOT_TOKEN 环境变量未设置")
        if cls.NOTIFY_CHANNEL_ID == 0:
            logging.warning("⚠️ NOTIFY_CHANNEL_ID 未设置，库存通知可能无法正常工作")

# 验证配置
Config.validate()

# ✅ 使用配置类的值
MONGO_URI = Config.MONGO_URI
MONGO_DB_BOT = Config.MONGO_DB_BOT
MONGO_DB_XCHP = Config.MONGO_DB_XCHP
MONGO_DB_MAIN = Config.MONGO_DB_MAIN
CUSTOMER_SERVICE = Config.CUSTOMER_SERVICE
OFFICIAL_CHANNEL = Config.OFFICIAL_CHANNEL
RESTOCK_GROUP = Config.RESTOCK_GROUP
BOT_TOKEN = Config.BOT_TOKEN
NOTIFY_CHANNEL_ID = Config.NOTIFY_CHANNEL_ID
STOCK_NOTIFICATION_DELAY = Config.STOCK_NOTIFICATION_DELAY
BOT_USERNAME = Config.BOT_USERNAME

# ✅ 数据库连接和集合管理优化
class DatabaseManager:
    def __init__(self):
        self.client = pymongo.MongoClient(MONGO_URI)
        
        # 主数据库
        self.main_db = self.client[MONGO_DB_MAIN]
        self.qukuai = self.main_db['qukuai']
        
        # 机器人数据库
        self.bot_db = self.client[MONGO_DB_BOT]
        self._init_collections()
        
        logging.info("✅ 数据库连接初始化完成")
    
    def _init_collections(self):
        """初始化所有集合"""
        self.user = self.bot_db['user']
        self.shangtext = self.bot_db['shangtext']
        self.get_key = self.bot_db['get_key']
        self.topup = self.bot_db['topup']
        self.get_kehuduan = self.bot_db['get_kehuduan']
        self.shiyong = self.bot_db['shiyong']
        self.user_log = self.bot_db['user_log']
        self.fenlei = self.bot_db['fenlei']
        self.ejfl = self.bot_db['ejfl']
        self.hb = self.bot_db['hb']
        self.xyh = self.bot_db['xyh']
        self.gmjlu = self.bot_db['gmjlu']
        self.fyb = self.bot_db['fyb']
        self.sftw = self.bot_db['sftw']
        self.hongbao = self.bot_db['hongbao']
        self.qb = self.bot_db['qb']
        self.zhuanz = self.bot_db['zhuanz']
        
        # New collections for multi-tenant agent architecture
        self.agents = self.bot_db['agents']
        self.agent_ledger = self.bot_db['agent_ledger']
        self.agent_withdrawals = self.bot_db['agent_withdrawals']
    
    def close(self):
        """关闭数据库连接"""
        self.client.close()
        logging.info("✅ 数据库连接已关闭")

# 初始化数据库管理器
db_manager = DatabaseManager()

# ✅ 为了向后兼容，保留原有变量名
teleclient = db_manager.client
main_db = db_manager.main_db
qukuai = db_manager.qukuai
bot_db = db_manager.bot_db
user = db_manager.user
shangtext = db_manager.shangtext
get_key = db_manager.get_key
topup = db_manager.topup
get_kehuduan = db_manager.get_kehuduan
shiyong = db_manager.shiyong
user_log = db_manager.user_log
fenlei = db_manager.fenlei
ejfl = db_manager.ejfl
hb = db_manager.hb
xyh = db_manager.xyh
gmjlu = db_manager.gmjlu
fyb = db_manager.fyb
sftw = db_manager.sftw
hongbao = db_manager.hongbao
qb = db_manager.qb
zhuanz = db_manager.zhuanz

# New collections for multi-tenant agent architecture
agents = db_manager.agents
agent_ledger = db_manager.agent_ledger
agent_withdrawals = db_manager.agent_withdrawals

# ✅ 库存通知管理优化
class StockNotificationManager:
    def __init__(self):
        self.notify_cache = {}
        self.last_notify_time = {}
        self.notification_lock = threading.Lock()
        self.bot_instance = None
    
    def get_bot(self):
        """获取或创建 Bot 实例"""
        if self.bot_instance is None:
            self.bot_instance = Bot(token=BOT_TOKEN)
        return self.bot_instance
    
    def add_stock_notification(self, nowuid: str, projectname: str):
        """添加库存通知"""
        with self.notification_lock:
            if nowuid not in self.notify_cache:
                self.notify_cache[nowuid] = {'projectname': projectname, 'count': 1}
            else:
                self.notify_cache[nowuid]['count'] += 1
    
    def send_notification(self, nowuid: str, projectname: str, price: float, stock: int, count: int):
        """发送单个商品的库存通知"""
        try:
            if count <= 0:
                logging.info(f"ℹ️ 补货数为0，跳过通知：nowuid={nowuid}")
                return
            
            # 分离一级分类和二级分类名称
            if "/" in projectname:
                parent_name, product_name = projectname.split("/", 1)
            else:
                parent_name = "未分类"
                product_name = projectname
            
            text = f"""
💎💎 库存更新 💎💎

📂 {parent_name}
├─ 📦 {product_name}
└─ 💰 {price:.2f} U

🆕 新增库存: {count} 个
📊 剩余库存: {stock} 个
🛒 点击下方按钮快速购买
            """.strip()

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 购买商品", url=f"https://t.me/{BOT_USERNAME}?start=buy_{nowuid}")]
            ])
            
            bot = self.get_bot()
            bot.send_message(
                chat_id=NOTIFY_CHANNEL_ID, 
                text=text, 
                parse_mode='HTML', 
                reply_markup=keyboard
            )
            logging.info(f"✅ 补货通知已发送：{projectname} (新增{count}个)")
        except Exception as e:
            logging.error(f"❌ 推送失败：{e}")
    
    def send_batched_notifications(self):
        """发送批量库存通知"""
        with self.notification_lock:
            if not self.notify_cache:
                return
            
            notifications_to_send = self.notify_cache.copy()
            self.notify_cache.clear()
        
        for nowuid, info in notifications_to_send.items():
            try:
                # 获取二级分类信息
                product = ejfl.find_one({'nowuid': nowuid})
                if not product:
                    logging.warning(f"❌ 未找到商品信息：nowuid={nowuid}")
                    continue
                
                # 获取一级分类信息
                uid = product.get('uid')
                parent_category = fenlei.find_one({'uid': uid})
                parent_name = parent_category['projectname'] if parent_category else "未知分类"
                
                # 构建完整的商品名称：一级分类/二级分类
                product_name = f"{parent_name}/{product['projectname']}"
                
                price = float(product.get('money', 0))
                stock = hb.count_documents({'nowuid': nowuid, 'state': 0})
                self.send_notification(nowuid, product_name, price, stock, info['count'])
                
            except Exception as e:
                logging.error(f"❌ 发送库存通知失败：nowuid={nowuid}, error={e}")
        
        logging.info(f"📢 批量库存通知完成，共发送 {len(notifications_to_send)} 个通知")
    
    def schedule_notification(self, nowuid: str, projectname: str):
        """安排延迟通知"""
        self.add_stock_notification(nowuid, projectname)
        
        def delayed_notify():
            time.sleep(STOCK_NOTIFICATION_DELAY)
            try:
                self.send_batched_notifications()
            except Exception as e:
                logging.error(f"❌ 延迟通知失败：{e}")
        
        threading.Thread(target=delayed_notify, daemon=True).start()
        logging.info(f"🔔 已启动库存通知延迟任务：{projectname} (nowuid={nowuid})")

# 初始化库存通知管理器
stock_manager = StockNotificationManager()

# ✅ 为了向后兼容，保留原有变量和函数
stock_notify_cache = stock_manager.notify_cache
last_notify_time = stock_manager.last_notify_time
notification_lock = stock_manager.notification_lock

def send_stock_notification(bot: Bot, channel_id: int, projectname: str, price: float, stock: int, nowuid: str, bot_username: str = None):
    """向后兼容的库存通知函数"""
    if bot_username is None:
        bot_username = BOT_USERNAME
    
    count = stock_notify_cache.get(nowuid, {}).get('count', 0)
    stock_manager.send_notification(nowuid, projectname, price, stock, count)

def send_batched_stock_notifications(bot: Bot, channel_id: int):
    """向后兼容的批量通知函数"""
    stock_manager.send_batched_notifications()

def shang_text(projectname, text):
    """统一的商店文本插入函数"""
    try:
        shangtext.insert_one({'projectname': projectname, 'text': text})
        logging.info(f"✅ 插入 shangtext：{projectname}")
    except Exception as e:
        logging.error(f"❌ 插入 shangtext 失败：{projectname} - {e}")

def sifatuwen(bot_id, projectname, text, file_id, key_text, keyboard, send_type):
    """司法图文插入函数"""
    try:
        sftw.insert_one({
            'bot_id': bot_id,
            'projectname': projectname,
            'text': text,
            'file_id': file_id,
            'key_text': key_text,
            'keyboard': keyboard,
            'send_type': send_type,
            'state': 1,
            'entities': b'\x80\x03]q\x00.'
        })
        logging.info(f"✅ 插入司法图文：{projectname}")
    except Exception as e:
        logging.error(f"❌ 插入司法图文失败：{projectname} - {e}")

def fanyibao(projectname, text, fanyi):
    """翻译包插入函数"""
    try:
        fyb.insert_one({
            'projectname': projectname,
            'text': text,
            'fanyi': fanyi
        })
        logging.info(f"✅ 插入翻译包：{projectname}")
    except Exception as e:
        logging.error(f"❌ 插入翻译包失败：{projectname} - {e}")

def goumaijilua(leixing, bianhao, user_id, projectname, text, ts, timer, count):
    """购买记录插入函数
    
    Returns:
        dict: The inserted order document
    """
    try:
        order_doc = {
            'leixing': leixing,
            'bianhao': bianhao,
            'user_id': user_id,
            'projectname': projectname,
            'text': text,
            'ts': ts,
            'timer': timer,
            'count': count   # ✅ 记录实际数量
        }
        gmjlu.insert_one(order_doc)
        logging.info(f"✅ 插入购买记录：{user_id} - {projectname}")
        return order_doc
    except Exception as e:
        logging.error(f"❌ 插入购买记录失败：{user_id} - {projectname} - {e}")
        return None

def xieyihaobaocun(uid, nowuid, hbid, projectname, timer):
    """协议号保存函数"""
    try:
        xyh.insert_one({
            'uid': uid,
            'nowuid': nowuid,
            'hbid': hbid,
            'projectname': projectname,
            'state': 0,
            'timer': timer
        })
        logging.info(f"✅ 保存协议号：{projectname} (nowuid={nowuid})")
    except Exception as e:
        logging.error(f"❌ 保存协议号失败：{projectname} - {e}")


def shangchuanhaobao(leixing, uid, nowuid, hbid, projectname, timer, remark=''):
    """优化的商品上架函数"""
    try:
        # 插入商品数据
        hb.insert_one({
            'leixing': leixing,
            'uid': uid,
            'nowuid': nowuid,
            'hbid': hbid,
            'projectname': projectname,
            'state': 0,
            'timer': timer,
            'remark': remark
        })
        logging.info(f"✅ 上架商品成功：{projectname} (nowuid={nowuid})")

        # ✅ 使用优化的库存通知管理器
        stock_manager.schedule_notification(nowuid, projectname)

    except Exception as e:
        logging.error(f"❌ 上架商品失败：{projectname} - {e}")




    
    
def erjifenleibiao(uid, nowuid, projectname, row):
    ejfl.insert_one({
        'uid': uid,
        'nowuid': nowuid,
        'projectname': projectname,
        'row': row,
        'text': f'''
<b>♻️ 账号正在打包，请稍等片刻！
‼️ 二级密码看文件夹里 json

➖➖➖➖➖➖➖➖
➖➖➖➖➖➖➖➖
☎️ 客服：{CUSTOMER_SERVICE}
📣 频道：{RESTOCK_GROUP}
➖➖➖➖➖➖➖➖</b>
        ''',
        'money': 0
    })


def fenleibiao(uid, projectname,row):
    fenlei.insert_one({
        'uid': uid,
        'projectname': projectname,
        'row': row
    })

def user_logging(uid, projectname , user_id, today_money, today_time):
    log_data = {
        'uid': uid,
        'projectname': projectname,
        'user_id': user_id,
        'today_money': today_money,
        'today_time': today_time,
        'log_time': datetime.now()
    }
    try:
        user_log.insert_one(log_data)
        print(f"✅ 日志已记录: {log_data}")
        logging.info(f"日志已记录: {log_data}")
    except Exception as e:
        error_msg = f"❌ 日志记录失败: {e}"
        print(error_msg)
        logging.error(error_msg)

def sydata(tranhash):
    """使用数据插入函数"""
    try:
        shiyong.insert_one({'tranhash': tranhash})
        logging.info(f"✅ 插入使用数据：{tranhash}")
    except Exception as e:
        logging.error(f"❌ 插入使用数据失败：{tranhash} - {e}")

def kehuduanurl(api, key):
    """客户端URL插入函数"""
    try:
        get_kehuduan.insert_one({
            'api': api,
            'key': key,
            'tcid': 0,
        })
        logging.info(f"✅ 插入客户端URL：{api}")
    except Exception as e:
        logging.error(f"❌ 插入客户端URL失败：{api} - {e}")

# ✅ 新增：实用工具函数
def get_product_stock(nowuid: str) -> int:
    """获取商品库存数量"""
    try:
        return hb.count_documents({'nowuid': nowuid, 'state': 0})
    except Exception as e:
        logging.error(f"❌ 获取库存失败：nowuid={nowuid} - {e}")
        return 0

def get_user_info(user_id: int) -> dict:
    """获取用户信息"""
    try:
        return user.find_one({'user_id': user_id}) or {}
    except Exception as e:
        logging.error(f"❌ 获取用户信息失败：user_id={user_id} - {e}")
        return {}

def update_user_balance(user_id: int, amount: float, balance_type: str = 'USDT') -> bool:
    """更新用户余额"""
    try:
        result = user.update_one(
            {'user_id': user_id},
            {'$inc': {balance_type: amount}}
        )
        if result.modified_count > 0:
            logging.info(f"✅ 更新用户余额：user_id={user_id}, {balance_type}+={amount}")
            return True
        else:
            logging.warning(f"⚠️ 用户余额更新无变化：user_id={user_id}")
            return False
    except Exception as e:
        logging.error(f"❌ 更新用户余额失败：user_id={user_id} - {e}")
        return False
    
    
def keybutton(Row, first):
    """按钮模板插入函数"""
    try:
        get_key.insert_one({
            'Row': Row,
            'first': first,
            'projectname': '点击修改内容',
            'text': '',
            'file_id': '',
            'file_type': '',
            'key_text': '',
            'keyboard': b'\x80\x03]q\x00.',
            'entities': b'\x80\x03]q\x00.'
        })
        logging.info(f"✅ 插入按钮模板 Row={Row}, first={first}")
    except Exception as e:
        logging.error(f"❌ 插入按钮模板失败：{e}")
    
    
def user_data(key_id, user_id, username, fullname, lastname, state, creation_time, last_contact_time):
    try:
        user.insert_one({
            'count_id': key_id,
            'user_id': user_id,
            'username': username,
            'fullname': fullname,
            'lastname': lastname,
            'state': state,
            'creation_time': creation_time,
            'last_contact_time': last_contact_time,
            'USDT': 0,
            'zgje': 0,
            'zgsl': 0,
            'sign': 0,
            'lang': 'zh',
            'verified': False   # ✅ 添加这一行
        })
        logging.info(f"✅ 新增用户：{user_id} ({username})")
    except Exception as e:
        logging.error(f"❌ 用户写入失败：{user_id} - {e}")

if shangtext.find_one({}) is None:
    logging.info("🔧 初始化 shangtext 数据")
    fstext = '''
 💎本店业务💎 

飞机号，协议号,  直登号(tdata) 批发/零售 !
开通飞机会员,  能量租用&TRX兑换 , 老号老群老频道 !

❗️ 未使用过的本店商品的，请先少量购买测试，以免造成不必要的争执！谢谢合作！

❗️ 免责声明：本店所有商品，仅用于娱乐测试，不得用于违法活动！ 请遵守当地法律法规！

⚙️ /start   ⬅️点击命令打开底部菜单!
    '''.strip()
    shang_text('欢迎语', fstext)
    shang_text('欢迎语样式', b'\x80\x03]q\x00.')
    shang_text('充值地址', '')
    shang_text('营业状态', 1)
    logging.info("✅ shangtext 初始化完成")

if __name__ == '__main__':
    keybutton(4, 1)