# init_db.py
from app import app, db  # 導入 app 和 db
from database import MenuItem, Order  # 確保模型已定義

def init_db():
    with app.app_context():
        db.create_all()  # 創建所有表格
        print("Database tables created successfully!")

if __name__ == "__main__":
    init_db()
