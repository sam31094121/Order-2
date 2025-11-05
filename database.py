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
        # 根據日期和狀態（僅計算已完成訂單）過濾訂單
        if date_filter == "today":
            orders = Order.query.filter(
                Order.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
                Order.status == 'completed'
            ).all()
        elif date_filter == "yesterday":
            yesterday = datetime.utcnow() - timedelta(days=1)
            orders = Order.query.filter(
                Order.created_at >= yesterday.replace(hour=0, minute=0, second=0, microsecond=0),
                Order.created_at < datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
                Order.status == 'completed'
            ).all()
        elif date_filter == "last_7_days":
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            orders = Order.query.filter(
                Order.created_at >= seven_days_ago,
                Order.status == 'completed'
            ).all()
        else:
            try:
                custom_date = datetime.strptime(date_filter, '%Y-%m-%d')
                orders = Order.query.filter(
                    Order.created_at >= custom_date.replace(hour=0, minute=0, second=0, microsecond=0),
                    Order.created_at < (custom_date + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
                    Order.status == 'completed'
                ).all()
            except ValueError:
                return {"error": "無效的日期格式，應為 YYYY-MM-DD"}

        # 計算總訂單數和總銷售額
        total_orders = len(orders)
        total_revenue = sum(order.total_amount for order in orders)

        # 解析 items 並按 category 和 name 聚合，直接從 JSON 獲取 category
        item_stats = {}
        for order in orders:
            items = json.loads(order.items)
            for item in items:
                name = item.get("name")
                category = item.get("category", "unknown")  # 從 items JSON 直接獲取 category
                if category_filter != "all" and category != category_filter:
                    continue
                key = (name, category)
                if key not in item_stats:
                    item_stats[key] = {"quantity": 0, "total_price": 0}
                item_stats[key]["quantity"] += item.get("quantity", 1)
                item_stats[key]["total_price"] += item.get("price", 0) * item.get("quantity", 1)

        # 格式化回應數據
        response = {
            "total_orders": total_orders,
            "total_revenue": round(total_revenue, 2),
            "items": [
                {
                    "name": k[0],
                    "category": k[1],
                    "quantity": v["quantity"],
                    "total_price": v["total_price"],
                    "date": order.created_at.strftime("%Y-%m-%d")
                }
                for k, v in item_stats.items()
            ]
        }
        return response
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析錯誤: {str(e)}"}
    except Exception as e:
        return {"error": f"數據處理錯誤: {str(e)}"}

