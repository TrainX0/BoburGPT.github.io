from flask import Flask, render_template, request, redirect, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os, json, time, secrets

app = Flask(__name__)
app.secret_key = "super_neon_key_2025"

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MEDIA_DIR = os.path.join(BASE_DIR, "media")
DB_FILE = os.path.join(DATA_DIR, "db.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

# --- DATABASE ---
def load_db():
    if not os.path.exists(DB_FILE):
        init_db = {
            "users": {},
            "services": [], # Список услуг
            "orders": [],   # Список заказов
            "messages": []  # Общий список сообщений
        }
        with open(DB_FILE, "w", encoding='utf-8') as f:
            json.dump(init_db, f, ensure_ascii=False, indent=4)
        return init_db
    try:
        with open(DB_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"users":{}, "services":[], "orders":[], "messages":[]}

def save_db(db):
    with open(DB_FILE, "w", encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

# --- ADMIN ---
ADMIN_LOGIN = "Bobur2012.12"
ADMIN_PASS_RAW = "4348888b"

def check_admin():
    db = load_db()
    if ADMIN_LOGIN not in db["users"]:
        db["users"][ADMIN_LOGIN] = {
            "name": "Admin Support",
            "password": generate_password_hash(ADMIN_PASS_RAW),
            "role": "admin",
            "avatar": None,
            "lang": "ru"
        }
        save_db(db)
check_admin()

# --- ROUTES ---
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/panel.html")
def panel():
    if "user" not in session: return redirect("/")
    return send_from_directory(BASE_DIR, "panel.html")

@app.route("/media/<path:filename>")
def get_media(filename):
    return send_from_directory(MEDIA_DIR, filename)

# --- AUTH ---
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    login = data.get("login")
    password = data.get("password")
    name = data.get("name") # Имя обязательно
    lang = data.get("lang", "ru")

    if not login or not password or not name:
        return jsonify({"error": "Заполните все поля"}), 400

    db = load_db()
    if login in db["users"]:
        return jsonify({"error": "Пользователь уже существует"}), 400

    db["users"][login] = {
        "name": name,
        "password": generate_password_hash(password),
        "role": "user",
        "avatar": None,
        "lang": lang
    }
    save_db(db)
    session["user"] = login
    session["role"] = "user"
    return jsonify({"ok": True})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    login = data.get("login")
    password = data.get("password")
    
    db = load_db()
    user = db["users"].get(login)

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Неверный логин или пароль"}), 401
    
    session["user"] = login
    session["role"] = user["role"]
    return jsonify({"ok": True})

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/who")
def whoami():
    login = session.get("user")
    if not login: return jsonify({"logged": False})
    db = load_db()
    u = db["users"].get(login, {})
    return jsonify({
        "logged": True,
        "login": login,
        "name": u.get("name"),
        "role": u.get("role"),
        "avatar": u.get("avatar"),
        "lang": u.get("lang", "ru")
    })

# --- PROFILE UPDATE ---
@app.route("/api/profile", methods=["POST"])
def update_profile():
    if "user" not in session: return jsonify({"error": "Auth"}), 401
    login = session["user"]
    db = load_db()
    
    if "name" in request.form: db["users"][login]["name"] = request.form["name"]
    if "lang" in request.form: db["users"][login]["lang"] = request.form["lang"]
    
    if "avatar" in request.files:
        f = request.files["avatar"]
        if f.filename:
            fn = secure_filename(f"{time.time()}_{f.filename}")
            f.save(os.path.join(MEDIA_DIR, fn))
            db["users"][login]["avatar"] = fn
            
    save_db(db)
    return jsonify({"ok": True})

# --- SERVICES ---
@app.route("/api/services", methods=["GET", "POST"])
def services():
    db = load_db()
    if request.method == "GET":
        return jsonify(db["services"])
    
    # POST (Create)
    if session.get("role") != "admin": return jsonify({"error": "Forbidden"}), 403
    
    img_name = None
    if "image" in request.files:
        f = request.files["image"]
        if f.filename:
            img_name = secure_filename(f"{time.time()}_{f.filename}")
            f.save(os.path.join(MEDIA_DIR, img_name))

    new_svc = {
        "id": int(time.time()),
        "title": request.form["title"],
        "desc": request.form["desc"],
        "price": request.form["price"],
        "image": img_name
    }
    db["services"].append(new_svc)
    save_db(db)
    return jsonify({"ok": True})

@app.route("/api/services/delete", methods=["POST"])
def delete_service():
    if session.get("role") != "admin": return jsonify({"error": "Forbidden"}), 403
    sid = int(request.json.get("id"))
    db = load_db()
    db["services"] = [s for s in db["services"] if s["id"] != sid]
    save_db(db)
    return jsonify({"ok": True})

# --- ORDERS ---
@app.route("/api/orders", methods=["GET", "POST"])
def orders():
    if "user" not in session: return jsonify({"error": "Auth"}), 401
    db = load_db()
    user = session["user"]
    
    if request.method == "GET":
        if session["role"] == "admin":
            return jsonify(db["orders"])
        else:
            return jsonify([o for o in db["orders"] if o["user"] == user])

    # POST (Buy)
    if session["role"] == "admin": return jsonify({"error": "Admin cannot buy"}), 403
    data = request.get_json()
    new_order = {
        "id": int(time.time()),
        "user": user,
        "service": data.get("service"),
        "price": data.get("price"),
        "status": "waiting",
        "date": time.strftime("%Y-%m-%d %H:%M")
    }
    db["orders"].append(new_order)
    save_db(db)
    return jsonify({"ok": True})

# --- CHAT (FIXED) ---
@app.route("/api/messages", methods=["GET", "POST"])
def messages():
    if "user" not in session: return jsonify({"error": "Auth"}), 401
    user = session["user"]
    db = load_db()
    role = session["role"]

    if request.method == "POST":
        # Отправка
        text = request.form.get("text", "")
        to_user = request.form.get("to")
        
        # Если юзер пишет, получатель всегда админ
        if role == "user": to_user = ADMIN_LOGIN
        if not to_user: return jsonify({"error": "No recipient"}), 400

        file_name = None
        if "file" in request.files:
            f = request.files["file"]
            if f.filename:
                file_name = secure_filename(f"{time.time()}_msg_{f.filename}")
                f.save(os.path.join(MEDIA_DIR, file_name))

        msg = {
            "from": user,
            "to": to_user,
            "text": text,
            "file": file_name,
            "time": time.time()
        }
        db["messages"].append(msg)
        # Храним последние 2000 сообщений
        if len(db["messages"]) > 2000: db["messages"] = db["messages"][-2000:]
        save_db(db)
        return jsonify({"ok": True})

    else:
        # Получение (GET)
        target = request.args.get("target") # С кем переписка?
        
        # Если я юзер, я вижу только свои сообщения с админом
        if role == "user":
            filtered = [m for m in db["messages"] if (m["from"]==user and m["to"]==ADMIN_LOGIN) or (m["from"]==ADMIN_LOGIN and m["to"]==user)]
            return jsonify(filtered)
        
        # Если я админ, мне нужен target (с кем я говорю)
        if role == "admin":
            if not target: return jsonify([])
            filtered = [m for m in db["messages"] if (m["from"]==user and m["to"]==target) or (m["from"]==target and m["to"]==user)]
            return jsonify(filtered)

# Получить список юзеров для админа
@app.route("/api/users_list")
def users_list():
    if session.get("role") != "admin": return jsonify({"error": "Forbidden"}), 403
    db = load_db()
    # Вернем список всех, кроме админа
    users = []
    for login, data in db["users"].items():
        if data["role"] != "admin":
            users.append({"login": login, "name": data["name"], "avatar": data["avatar"]})
    return jsonify(users)

if __name__ == "__main__":
    app.run(debug=True, port=5000)