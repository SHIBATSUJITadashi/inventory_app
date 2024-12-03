from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from config import Config
from flask_migrate import Migrate
import pytz
import os

# Flaskアプリの設定
app = Flask(
    __name__,
    template_folder="templates",  # テンプレートフォルダの明示
    static_folder="static"       # 静的ファイルフォルダの明示
)
app.config.from_object(Config)

# データベースの設定
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# 日本時間（JST）の設定
JST = pytz.timezone('Asia/Tokyo')

# モデル定義
class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(128), nullable=False)

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    min_quantity = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(JST))

class Alerts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    triggered_at = db.Column(db.DateTime, default=lambda: datetime.now(JST))
    resolved_at = db.Column(db.DateTime, nullable=True)

    inventory = db.relationship('Inventory', backref=db.backref('alerts', lazy=True))

    def __repr__(self):
        return f'<Alert {self.id} for Inventory {self.inventory_id}>'

# ログインページ
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = Users.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["username"] = username
            return redirect(url_for("inventory_list"))
        flash("ログインに失敗しました。ユーザー名またはパスワードを確認してください。")
    return render_template("index.html")

# 在庫一覧ページ
@app.route("/inventory")
def inventory_list():
    if "username" not in session:
        return redirect(url_for("index"))

    inventory = Inventory.query.all()
    for item in inventory:
        item.alert = None
        if item.quantity < item.min_quantity:
            alert = Alerts.query.filter_by(inventory_id=item.id, status='ACTIVE').first()
            if alert:
                item.alert = 'alert'

    return render_template("inventory_list.html", inventory=inventory)

# 在庫追加ページ
@app.route("/inventory/add", methods=["GET", "POST"])
def add_inventory():
    if "username" not in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        name = request.form["name"]
        quantity = int(request.form["quantity"])
        unit = request.form["unit"]
        min_quantity = int(request.form["min_quantity"])

        new_item = Inventory(
            name=name,
            quantity=quantity,
            unit=unit,
            min_quantity=min_quantity,
            updated_at=datetime.now(JST)
        )
        db.session.add(new_item)
        db.session.commit()
        return redirect(url_for("inventory_list"))

    return render_template("add_inventory.html")

# ログアウト機能
@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("index"))

# 初回リクエスト時にユーザーを作成
@app.before_request
def create_user():
    if not Users.query.filter_by(username="test").first():
        hashed_password = generate_password_hash("testpassword", method='pbkdf2:sha256')
        new_user = Users(username="test", password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

# アラート一覧ページ
@app.route("/alerts")
def alert_list():
    if "username" not in session:
        return redirect(url_for("index"))

    alerts = Alerts.query.filter_by(status='ACTIVE').join(Inventory).all()
    return render_template("alert_list.html", alerts=alerts)

@app.route("/inventory/edit/<int:id>", methods=["GET", "POST"])
def edit_inventory(id):
    if "username" not in session:
        return redirect(url_for("index"))

    inventory_item = Inventory.query.get_or_404(id)
    if request.method == "POST":
        inventory_item.name = request.form["name"]
        inventory_item.quantity = int(request.form["quantity"])
        inventory_item.unit = request.form["unit"]
        inventory_item.min_quantity = int(request.form["min_quantity"])
        inventory_item.updated_at = datetime.now(JST)

        db.session.commit()
        return redirect(url_for("inventory_list"))

    return render_template("edit_inventory.html", inventory_item=inventory_item)

@app.route("/inventory/delete/<int:id>", methods=["POST"])
def delete_inventory(id):
    if "username" not in session:
        return redirect(url_for("index"))

    inventory_item = Inventory.query.get_or_404(id)

    db.session.delete(inventory_item)
    db.session.commit()

    return redirect(url_for("inventory_list"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
