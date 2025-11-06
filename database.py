from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import json

# 初始化 SQLAlchemy 資料庫實例
db = SQLAlchemy()

# 菜單項目模型
class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    available = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """將 MenuItem 物件轉為字典格式"""
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'description': self.description,
            'category': self.category,
            'available': self.available,
            'created_at': self.created_at.isoformat()[:19] + 'Z' if self.created_at else None
        }

# 訂單模型
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    items = db.Column(db.Text, nullable=False)  # 儲存 JSON 字串
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """將 Order 物件轉為字典格式，移除毫秒以確保穩定性"""
        return {
            'id': self.id,
            'order_number': self.order_number,
            'items': json.loads(self.items) if self.items else [],
            'total_amount': self.total_amount,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat()[:19] + 'Z' if self.created_at else None,
            'updated_at': self.updated_at.isoformat()[:19] + 'Z' if self.updated_at else None
        }

# 銷售分析函數
def get_sales_analytics(date_filter, category_filter):
    """獲取銷售分析數據
    參數：
        date_filter: 'today', 'yesterday', 'last_7_days' 或自訂日期 (e.g., '2025-11-05')
        category_filter: 'all' 或特定類別 (e.g., 'main_dish')
    返回：
        dict 包含 total_orders, total_revenue, items
    """
    try:
        # 根據日期過濾訂單
        current_time = datetime.utcnow()
        if date_filter == "today":
            start_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            orders = Order.query.filter(Order.created_at >= start_time).all()
        elif date_filter == "yesterday":
            yesterday = current_time - timedelta(days=1)
            start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            orders = Order.query.filter(Order.created_at >= start_time, Order.created_at < end_time).all()
        elif date_filter == "last_7_days":
            start_time = current_time - timedelta(days=7)
            orders = Order.query.filter(Order.created_at >= start_time).all()
        else:
            try:
                custom_date = datetime.strptime(date_filter, '%Y-%m-%d')
                start_time = custom_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = (custom_date + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                orders = Order.query.filter(Order.created_at >= start_time, Order.created_at < end_time).all()
            except ValueError:
                return {"error": "無效的日期格式，應為 YYYY-MM-DD"}

        # 如果無訂單，返回空數據
        if not orders:
            return {"total_orders": 0, "total_revenue": 0.0, "items": []}

        # 計算總訂單數和總銷售額（僅包含 completed 狀態）
        completed_orders = [o for o in orders if o.status == 'completed']
        total_orders = len(completed_orders)
        total_revenue = sum(o.total_amount for o in completed_orders)

        # 解析 items 並按 category 和 name 聚合
        item_stats = {}
        for order in completed_orders:
            items = json.loads(order.items)
            for item in items:
                name = item.get("name", "未知")
                category = item.get("category", "unknown")  # 預設 unknown，如果無 category
                if category_filter != "all" and category != category_filter:
                    continue
                key = (name, category)
                if key not in item_stats:
                    item_stats[key] = {"quantity": 0, "total_price": 0.0}
                quantity = item.get("quantity", 1)
                price = item.get("price", 0.0)
                if not isinstance(quantity, (int, float)) or not isinstance(price, (int, float)):
                    continue  # 跳過無效數據
                item_stats[key]["quantity"] += quantity
                item_stats[key]["total_price"] += price * quantity

        # 格式化回應數據，使用日期範圍的起點作為參考
        response = {
            "total_orders": total_orders,
            "total_revenue": round(total_revenue, 2),
            "items": [
                {
                    "name": k[0],
                    "category": k[1],
                    "quantity": v["quantity"],
                    "total_price": round(v["total_price"], 2),
                    "date": start_time.strftime("%Y-%m-%d")  # 使用日期範圍起點
                }
                for k, v in item_stats.items()
            ]
        }
        return response
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析錯誤: {str(e)}", "details": str(e)}
    except Exception as e:
        return {"error": f"數據處理錯誤: {str(e)}", "details": str(e)}


