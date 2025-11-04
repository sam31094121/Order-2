import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO
from datetime import datetime
import json
from urllib.parse import urlparse

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))

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

from database import db, MenuItem, Order
db.init_app(app)

socketio = SocketIO(app, async_mode='gevent')

with app.app_context():
    db.create_all()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/waiter")
def waiter():
    return render_template("waiter.html")

@app.route("/kitchen")
def kitchen():
    return render_template("kitchen.html")

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

@app.route("/api/menu", methods=["GET"])
def get_menu():
    try:
        items = MenuItem.query.filter_by(available=1).order_by(MenuItem.category, MenuItem.name).all()
        print(f"Retrieved {len(items)} menu items")
        return jsonify([item.to_dict() for item in items])
    except Exception as e:
        print(f"Menu query error: {e}")
        return jsonify({"error": "無法獲取菜單"}), 500

@app.route("/api/orders", methods=["GET", "POST"])
def manage_orders():
    if request.method == "POST":
        try:
            data = request.get_json()
            if not data or "items" not in data or not data["items"]:
                return jsonify({"error": "訂單內容為空"}), 400

            order_number = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            items_json = json.dumps(data["items"])
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

            print(f"New order created: {new_order.order_number}")
            socketio.emit("new_order", new_order.to_dict())  # 移除 broadcast=True
            return jsonify({"message": "訂單已送出", "order": new_order.to_dict()}), 201
        except Exception as e:
            db.session.rollback()
            print(f"Order creation error: {e}")
            return jsonify({"error": "送出訂單失敗，請稍後重試"}), 500
    elif request.method == "GET":
        try:
            filter_status = request.args.get("filter", "all")
            print(f"Fetching orders with filter: {filter_status}")
            if filter_status == "all":
                orders = Order.query.all()
            else:
                orders = Order.query.filter_by(status=filter_status).all()
            print(f"Retrieved {len(orders)} orders")
            return jsonify([order.to_dict() for order in orders])
        except Exception as e:
            print(f"Order query error: {e}")
            return jsonify({"error": "無法獲取訂單"}), 500

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

        print(f"Order {order.order_number} status updated to {new_status}")
        socketio.emit("order_updated", order.to_dict())  # 移除 broadcast=True
        return jsonify(order.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"Order status update error: {e}")
        return jsonify({"error": "更新訂單狀態失敗"}), 500

@app.route("/api/orders/<int:order_id>", methods=["DELETE"])
def delete_order(order_id):
    try:
        order = Order.query.get_or_404(order_id)
        db.session.delete(order)
        db.session.commit()

        print(f"Order {order.order_number} deleted")
        socketio.emit("order_deleted", {"order_id": order_id})  # 移除 broadcast=True
        return jsonify({"message": "訂單已刪除"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Order deletion error: {e}")
        return jsonify({"error": "刪除訂單失敗"}), 500

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=10000)

