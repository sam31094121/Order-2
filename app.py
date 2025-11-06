import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from flask_socketio import SocketIO
from datetime import datetime
import json
from urllib.parse import urlparse
import logging
import csv
import io

# 初始化 Flask 應用程式
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))

# 禁用 JSON 轉義，確保 UTF-8 編碼
app.config['JSON_AS_ASCII'] = False  # 關鍵修正 1：防止非 ASCII 字元轉義

# 資料庫配置
database_url = os.getenv('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif not database_url.startswith('postgresql+psycopg2://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orders.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_size': 5,
    'max_overflow': 10,
    'pool_timeout': 30
}

# 導入資料庫和模型
from flask_sqlalchemy import SQLAlchemy
from database import db, MenuItem, Order, get_sales_analytics
db.init_app(app)
socketio = SocketIO(app, async_mode='gevent')

# 設定日誌
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 創建資料庫表
with app.app_context():
    db.create_all()

# 根路由
@app.route("/")
def index():
    return render_template("index.html")

# 服務員頁面路由
@app.route("/waiter")
def waiter():
    return render_template("waiter.html")

# 廚房頁面路由
@app.route("/kitchen")
def kitchen():
    return render_template("kitchen.html")

# 管理員頁面路由
@app.route("/admin", methods=["GET", "POST"])
def admin_menu():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_or_update":
            name = request.form.get("name")
            price = float(request.form.get("price"))
            description = request.form.get("description")
            category = request.form.get("category")
            new_item = MenuItem(name=name, price=price, description=description, category=category)
            db.session.add(new_item)
            db.session.commit()
            return redirect(url_for("admin_menu"))
        elif action == "delete":
            item_id = request.form.get("item_id")
            item = MenuItem.query.get(item_id)
            if item:
                db.session.delete(item)
                db.session.commit()
            return redirect(url_for("admin_menu"))
    items = MenuItem.query.order_by(MenuItem.category, MenuItem.id).all()
    menu_items = [item.to_dict() for item in items]
    return render_template("admin.html", menu_items=menu_items)

# API 端點：獲取菜單
@app.route("/api/menu", methods=["GET"])
def get_menu():
    try:
        items = MenuItem.query.filter_by(available=1).order_by(MenuItem.category, MenuItem.name).all()
        logger.debug(f"Retrieved {len(items)} menu items")
        return jsonify([item.to_dict() for item in items])
    except Exception as e:
        logger.error(f"Menu query error: {e}")
        return jsonify({"error": "無法獲取菜單"}), 500

# API 端點：管理訂單
@app.route("/api/orders", methods=["GET", "POST"])
def manage_orders():
    if request.method == "POST":
        try:
            data = request.get_json()
            if not data or "items" not in data or not data["items"]:
                return jsonify({"error": "訂單內容為空"}), 400
            order_number = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            items_json = json.dumps(data["items"], ensure_ascii=False)  # 確保 UTF-8 編碼
            total_amount = sum(item["price"] * item["quantity"] for item in data["items"])
            new_order = Order(
                order_number=order_number,
                items=items_json,
                total_amount=total_amount,
                status="pending",
                notes=data.get("notes", "")
            )
            db.session.add(new_order)
            db.session.commit()
            logger.info(f"New order created: {new_order.order_number}")
            socketio.emit("new_order", new_order.to_dict())
            return jsonify({"message": "訂單已送出", "order": new_order.to_dict()}), 201
        except Exception as e:
            db.session.rollback()
            logger.error(f"Order creation error: {e}")
            return jsonify({"error": "送出訂單失敗，請稍後重試"}), 500
    elif request.method == "GET":
        try:
            filter_status = request.args.get("filter", "all")
            logger.debug(f"Fetching orders with filter: {filter_status}")
            if filter_status == "all":
                orders = Order.query.all()
            else:
                orders = Order.query.filter_by(status=filter_status).all()
            logger.debug(f"Retrieved {len(orders)} orders")
            return jsonify([order.to_dict() for order in orders])
        except Exception as e:
            logger.error(f"Order query error: {e}")
            return jsonify({"error": "無法獲取訂單"}), 500

# API 端點：更新訂單狀態
@app.route("/api/orders/<int:order_id>/status", methods=["PUT"])
def update_order_status(order_id):
    try:
        data = request.get_json()
        new_status = data.get("status")
        if not new_status:
            return jsonify({"error": "未提供狀態"}), 400
        order = Order.query.get_or_404(order_id)
        order.status = new_status
        order.updated_at = datetime.utcnow()
        db.session.commit()
        logger.info(f"Order {order.order_number} status updated to {new_status}")
        socketio.emit("order_updated", order.to_dict())
        return jsonify(order.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f"Order status update error: {e}")
        return jsonify({"error": "更新訂單狀態失敗"}), 500

# API 端點：刪除訂單
@app.route("/api/orders/<int:order_id>", methods=["DELETE"])
def delete_order(order_id):
    try:
        order = Order.query.get_or_404(order_id)
        db.session.delete(order)
        db.session.commit()
        logger.info(f"Order {order.order_number} deleted")
        socketio.emit("order_deleted", {"order_id": order_id})
        return jsonify({"message": "訂單已刪除"}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Order deletion error: {e}")
        return jsonify({"error": "刪除訂單失敗"}), 500

# 數據頁面路由
@app.route("/data")
def data():
    return render_template("data.html")

# API 端點：獲取分析數據
@app.route("/api/analytics", methods=["GET"])
def get_analytics():
    date_filter = request.args.get("date", "today")
    category_filter = request.args.get("category", "all")
    logger.debug(f"Analytics request: date={date_filter}, category={category_filter}")
    try:
        analytics_data = get_sales_analytics(date_filter, category_filter)
        if not analytics_data.get("total_orders") and not analytics_data.get("items"):
            logger.warning("No analytics data found, returning default response")
            return jsonify({"total_orders": 0, "total_revenue": 0.00, "items": []}), 200
        return jsonify(analytics_data)
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return jsonify({"error": "獲取分析數據失敗"}), 500

# API 端點：匯出 CSV
@app.route("/api/export/orders", methods=["GET"])
def export_orders_csv():
    try:
        # 獲取所有訂單
        orders = Order.query.all()
        if not orders:
            return jsonify({"error": "無訂單數據可匯出"}), 404

        # 創建 CSV 緩衝區
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, encoding='utf-8')

        # 寫入 UTF-8 BOM
        output.write('\ufeff')  # 確保 Excel 識別 UTF-8

        # 寫入標題
        writer.writerow(["訂單號", "總金額", "狀態", "備註", "創建時間", "更新時間", "項目"])

        # 寫入數據
        for order in orders:
            items = json.loads(order.items)
            items_str = "; ".join([f"{item.get('name', '')} x{item.get('quantity', 1)}" for item in items])
            writer.writerow([
                order.order_number,
                order.total_amount,
                order.status,
                order.notes or "",
                order.created_at.isoformat() if order.created_at else "",
                order.updated_at.isoformat() if order.updated_at else "",
                items_str
            ])

        # 準備回應，明確指定 UTF-8 編碼
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv; charset=utf-8",  # 關鍵修正 2：明確聲明 UTF-8
            headers={"Content-Disposition": "attachment; filename=orders_export.csv"}
        )
    except Exception as e:
        logger.error(f"CSV export error: {e}")
        return jsonify({"error": "匯出 CSV 失敗"}), 500

# SocketIO 事件處理
@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

# 啟動應用程式
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=10000)
