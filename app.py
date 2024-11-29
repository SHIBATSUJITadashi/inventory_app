from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timezone, timedelta
from config import Config

# Flaskアプリの初期設定
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "your_secret_key"  # セッション用の秘密鍵

# データベースとマイグレーションの設定
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# 日本時間に変換する関数
def to_jst(utc_time):
    if utc_time is None:
        return None
    jst = timezone(timedelta(hours=9))  # 日本標準時（UTC+9）
    return utc_time.astimezone(jst)

# データベースモデル
class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    min_quantity = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

class Alerts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    inventory = db.relationship('Inventory', backref='alerts')
    status = db.Column(db.String(20), nullable=False)  # ACTIVE, RESOLVED
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

# ホームページ（名前入力後、在庫一覧へリダイレクト）
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("name")  # プルダウンから選択された名前を取得
        session["name"] = name  # セッションに保存
        return redirect(url_for("inventory_list"))  # 在庫一覧へリダイレクト
    return render_template("index.html")

# 在庫一覧ページ
@app.route("/inventory")
def inventory_list():
    # セッションから名前を取得
    name = session.get("name", None)
    
    inventory = Inventory.query.all()
    result = [
        {
            "id": item.id,
            "name": item.name or "不明な商品",
            "quantity": item.quantity or 0,
            "unit": item.unit or "不明",
            "min_quantity": item.min_quantity or 0,
            "updated_at": to_jst(item.updated_at).strftime("%Y-%m-%d %H:%M") if item.updated_at else "不明",
        }
        for item in inventory
    ]
    return render_template("inventory_list.html", inventory=result, name=name)

# 在庫追加フォーム
@app.route("/inventory/add", methods=["GET", "POST"])
def add_inventory():
    # セッションから名前を取得
    name = session.get("name", None)

    if request.method == "POST":
        data = request.form
        new_item = Inventory(
            name=data["name"],
            quantity=int(data["quantity"]),
            unit=data["unit"],
            min_quantity=int(data["min_quantity"]),
        )
        db.session.add(new_item)
        db.session.commit()

        # アラートの登録
        if new_item.quantity < new_item.min_quantity:
            alert = Alerts(
                inventory_id=new_item.id,
                status="ACTIVE",
                triggered_at=datetime.now(timezone(timedelta(hours=9)))
            )
            db.session.add(alert)
            db.session.commit()

        return redirect(url_for("inventory_list"))
    return render_template("add_inventory.html", name=name)

# 在庫編集フォーム
@app.route("/inventory/edit/<int:id>", methods=["GET", "POST"])
def edit_inventory(id):
    item = Inventory.query.get(id)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    if request.method == "POST":
        data = request.form
        item.name = data["name"]
        item.quantity = int(data["quantity"])
        item.unit = data["unit"]
        item.min_quantity = int(data["min_quantity"])
        item.updated_at = datetime.now(timezone(timedelta(hours=9)))

        # アラートチェック
        if item.quantity < item.min_quantity:
            # 既存アラートがなければ新規登録
            existing_alert = Alerts.query.filter_by(inventory_id=item.id, status="ACTIVE").first()
            if not existing_alert:
                alert = Alerts(
                    inventory_id=item.id,
                    status="ACTIVE",
                    triggered_at=datetime.now(timezone(timedelta(hours=9)))
                )
                db.session.add(alert)
        else:
            # 在庫が正常値の場合、アラートを解決
            existing_alert = Alerts.query.filter_by(inventory_id=item.id, status="ACTIVE").first()
            if existing_alert:
                existing_alert.status = "RESOLVED"
                existing_alert.resolved_at = datetime.now(timezone(timedelta(hours=9)))
        db.session.commit()
        return redirect(url_for("inventory_list"))

    return render_template("edit_inventory.html", item=item)

# 在庫削除
@app.route("/inventory/delete/<int:id>")
def delete_inventory(id):
    item = Inventory.query.get(id)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("inventory_list"))

# アラート一覧ページ
@app.route("/alerts")
def alerts():
    # セッションから名前を取得
    name = session.get("name", None)

    active_alerts = Alerts.query.filter_by(status="ACTIVE").all()
    return render_template("alerts.html", alerts=active_alerts, name=name)

if __name__ == "__main__":
    app.run(debug=True)
