"""
SANTUY - Sahabat Antar Niaga Terhubung untuk You
Aplikasi B2B yang menghubungkan UMKM (Produsen/Vendor) dengan Agen (Distributor).

Tahap 2 (universal):
  - Akun & pengelolaan mandiri: daftar/login (Flask-Login + werkzeug hash),
    dashboard UMKM untuk CRUD produk & profil sendiri.
  - Rating dua arah terhubung akun: Agen menilai UMKM, UMKM menilai balik Agen.
  - Portabel SQLite (lokal) <-> PostgreSQL (online) lewat SQLAlchemy + DATABASE_URL.

Fitur inti tahap 1 tetap ada: katalog + smart categorizing, smart searching
(auto-suggestion, filter dinamis, sorting, pencarian lokasi GPS), contact person.
"""
import os
from functools import wraps

from flask import (Flask, render_template, request, jsonify, abort,
                   redirect, url_for, flash)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from sqlalchemy import or_

from database import (db, database_url, init_db, haversine, price_tier,
                      Category, Umkm, Product, Agen, Rating, User)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "santuy-dev-secret-ganti-di-produksi")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Silakan login terlebih dahulu."


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


# ----------------------------- Helper -----------------------------
def umkm_rating(umkm_id):
    rows = Rating.query.filter_by(target_type="umkm", target_id=umkm_id).all()
    if not rows:
        return 0, 0
    return round(sum(r.stars for r in rows) / len(rows), 1), len(rows)


def agen_rating(agen_id):
    rows = Rating.query.filter_by(target_type="agen", target_id=agen_id).all()
    if not rows:
        return 0, 0
    return round(sum(r.stars for r in rows) / len(rows), 1), len(rows)


def product_to_dict(p, user_lat=None, user_lng=None):
    avg, n = umkm_rating(p.umkm_id)
    u = p.umkm
    dist = haversine(user_lat, user_lng, u.lat, u.lng) if user_lat is not None else None
    badges = []
    if p.sold and p.sold >= 400:
        badges.append("Terlaris")
    if avg >= 4.5 and n >= 2:
        badges.append("Top Rated")
    if p.stock <= 100:
        badges.append("Stok Terbatas")
    return {
        "id": p.id,
        "name": p.name,
        "emoji": p.emoji,
        "price": p.price,
        "price_str": f"Rp{p.price:,}".replace(",", "."),
        "unit": p.unit,
        "stock": p.stock,
        "min_order": p.min_order,
        "weight_gram": p.weight_gram,
        "category": p.category.name if p.category else "Lainnya",
        "price_tier": price_tier(p.price),
        "umkm_id": p.umkm_id,
        "umkm_name": u.name,
        "region": u.region,
        "city": u.city,
        "verified": bool(u.verified),
        "rating": avg,
        "rating_count": n,
        "sold": p.sold,
        "views": p.views,
        "distance_km": dist,
        "badges": badges,
    }


def umkm_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "umkm":
            flash("Halaman ini khusus akun UMKM.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def agen_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "agen":
            flash("Halaman ini khusus akun Agen.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Halaman khusus admin.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ----------------------------- Pages -----------------------------
@app.route("/")
def index():
    regions = [r[0] for r in db.session.query(Umkm.region).distinct()
               .order_by(Umkm.region).all() if r[0]]
    cats = Category.query.order_by(Category.parent_id.isnot(None), Category.name).all()
    return render_template("index.html", regions=regions, categories=cats)


@app.route("/produk/<int:pid>")
def product_detail(pid):
    p = db.session.get(Product, pid)
    if not p:
        abort(404)
    p.views = (p.views or 0) + 1
    db.session.commit()
    prod = product_to_dict(p)
    u = p.umkm
    avg, n = umkm_rating(u.id)
    reviews = (Rating.query.filter_by(target_type="umkm", target_id=u.id)
               .order_by(Rating.id.desc()).all())
    related = (Product.query.filter(Product.category_id == p.category_id,
                                    Product.id != pid).limit(4).all())
    related = [product_to_dict(r) for r in related]
    return render_template("product.html", p=prod, umkm=u, umkm_rating=avg,
                           umkm_rating_count=n, reviews=reviews, related=related)


# ----------------------------- API: Smart Search -----------------------------
@app.route("/api/products")
def api_products():
    """Smart searching: query + filter dinamis + sorting + lokasi."""
    q = request.args.get("q", "").strip()
    region = request.args.get("region", "").strip()
    category = request.args.get("category", "").strip()
    price_min = request.args.get("price_min", type=int)
    price_max = request.args.get("price_max", type=int)
    sort = request.args.get("sort", "relevan")
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)

    query = Product.query.join(Umkm, Product.umkm_id == Umkm.id) \
        .outerjoin(Category, Product.category_id == Category.id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Product.name.ilike(like),
                                 Product.description.ilike(like),
                                 Category.name.ilike(like),
                                 Umkm.name.ilike(like)))
    if region:
        query = query.filter(Umkm.region == region)
    if category:
        sub = db.session.query(Category.id).filter(
            Category.parent_id == db.session.query(Category.id)
            .filter(Category.name == category).scalar_subquery())
        query = query.filter(or_(Category.name == category,
                                 Product.category_id.in_(sub)))
    if price_min is not None:
        query = query.filter(Product.price >= price_min)
    if price_max is not None:
        query = query.filter(Product.price <= price_max)

    items = [product_to_dict(p, lat, lng) for p in query.all()]

    if sort == "termurah":
        items.sort(key=lambda x: x["price"])
    elif sort == "termahal":
        items.sort(key=lambda x: x["price"], reverse=True)
    elif sort == "rating":
        items.sort(key=lambda x: (x["rating"], x["rating_count"]), reverse=True)
    elif sort == "terpopuler":
        items.sort(key=lambda x: (x["sold"], x["views"]), reverse=True)
    elif sort == "terdekat":
        if lat is not None and lng is not None:
            items.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] or 1e9))
        else:
            items.sort(key=lambda x: x["sold"], reverse=True)
    return jsonify({"count": len(items), "items": items, "located": lat is not None})


@app.route("/api/suggest")
def api_suggest():
    """Auto-suggestion untuk smart searching."""
    q = request.args.get("q", "").strip()
    out = []
    if len(q) >= 1:
        like = f"%{q}%"
        for r in Product.query.filter(Product.name.ilike(like)).limit(6):
            out.append({"type": "Produk", "text": r.name, "icon": "🔍"})
        for r in Category.query.filter(Category.name.ilike(like)).limit(4):
            out.append({"type": "Kategori", "text": r.name, "icon": r.icon})
        for r in Umkm.query.filter(Umkm.name.ilike(like)).limit(4):
            out.append({"type": "UMKM", "text": r.name, "icon": "🏪"})
    return jsonify(out[:10])


@app.route("/api/categories")
def api_categories():
    cats = Category.query.order_by(Category.parent_id.isnot(None), Category.name).all()
    return jsonify([{"id": c.id, "name": c.name, "parent_id": c.parent_id, "icon": c.icon}
                    for c in cats])


# ----------------------------- API: Rating (Agen -> UMKM) -----------------------------
@app.route("/api/rating", methods=["POST"])
@login_required
def api_add_rating():
    if current_user.role != "agen":
        return jsonify({"ok": False, "error": "Hanya akun Agen yang dapat menilai UMKM."}), 403
    data = request.get_json(force=True)
    try:
        stars = int(data["stars"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"ok": False, "error": "stars wajib 1-5"}), 400
    if not (1 <= stars <= 5):
        return jsonify({"ok": False, "error": "stars harus 1-5"}), 400
    umkm_id = data.get("umkm_id")
    comment = (data.get("comment") or "").strip()
    if not db.session.get(Umkm, umkm_id):
        return jsonify({"ok": False, "error": "UMKM tidak ditemukan"}), 404
    author = current_user.agen.name if current_user.agen else current_user.name
    db.session.add(Rating(target_type="umkm", target_id=umkm_id, author_type="agen",
                          author_name=author, author_user_id=current_user.id,
                          stars=stars, comment=comment))
    db.session.commit()
    avg, n = umkm_rating(umkm_id)
    return jsonify({"ok": True, "rating": avg, "count": n, "author": author})


# ----------------------------- Auth -----------------------------
@app.route("/daftar", methods=["GET", "POST"])
def daftar():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        f = request.form
        email = (f.get("email") or "").strip().lower()
        password = f.get("password") or ""
        role = f.get("role")
        name = (f.get("name") or "").strip()
        if role not in ("umkm", "agen") or not email or len(password) < 6 or not name:
            flash("Lengkapi data. Password minimal 6 karakter.")
            return render_template("daftar.html", form=f)
        if User.query.filter_by(email=email).first():
            flash("Email sudah terdaftar. Silakan login.")
            return render_template("daftar.html", form=f)

        user = User(email=email, role=role, name=name)
        user.set_password(password)
        if role == "umkm":
            profile = Umkm(name=name, owner=name,
                           description=(f.get("description") or "").strip(),
                           region=(f.get("region") or "").strip(),
                           city=(f.get("city") or "").strip(),
                           contact_name=(f.get("contact_name") or name).strip(),
                           contact_phone=(f.get("contact_phone") or "").strip(),
                           contact_whatsapp=(f.get("contact_whatsapp") or "").strip(),
                           contact_email=email, verified=0)
            db.session.add(profile)
            db.session.flush()
            user.umkm_id = profile.id
        else:
            profile = Agen(name=name,
                           description=(f.get("description") or "").strip(),
                           region=(f.get("region") or "").strip(),
                           city=(f.get("city") or "").strip(),
                           contact_name=(f.get("contact_name") or name).strip(),
                           contact_phone=(f.get("contact_phone") or "").strip(),
                           contact_whatsapp=(f.get("contact_whatsapp") or "").strip(),
                           contact_email=email)
            db.session.add(profile)
            db.session.flush()
            user.agen_id = profile.id
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f"Selamat datang, {name}! Akun {role.upper()} berhasil dibuat.")
        return redirect(url_for("dashboard" if role == "umkm" else "agen_dashboard"))
    return render_template("daftar.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            nxt = request.args.get("next")
            flash(f"Halo {user.name}!")
            if nxt:
                return redirect(nxt)
            if user.is_admin:
                return redirect(url_for("admin_panel"))
            return redirect(url_for("dashboard" if user.role == "umkm" else "agen_dashboard"))
        flash("Email atau password salah.")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Anda telah keluar.")
    return redirect(url_for("index"))


# ----------------------------- Dashboard UMKM (CRUD) -----------------------------
@app.route("/dashboard")
@umkm_required
def dashboard():
    u = current_user.umkm
    products = Product.query.filter_by(umkm_id=u.id).order_by(Product.id.desc()).all()
    avg, n = umkm_rating(u.id)
    return render_template("dashboard.html", umkm=u, products=products,
                           rating=avg, rating_count=n)


def _categories_for_select():
    return Category.query.order_by(Category.parent_id.isnot(None), Category.name).all()


@app.route("/dashboard/produk/baru", methods=["GET", "POST"])
@umkm_required
def produk_baru():
    if request.method == "POST":
        ok, err = _save_product(None)
        if ok:
            flash("Produk berhasil ditambahkan.")
            return redirect(url_for("dashboard"))
        flash(err)
    return render_template("produk_form.html", product=None,
                           categories=_categories_for_select())


@app.route("/dashboard/produk/<int:pid>/edit", methods=["GET", "POST"])
@umkm_required
def produk_edit(pid):
    p = db.session.get(Product, pid)
    if not p or p.umkm_id != current_user.umkm_id:
        abort(404)
    if request.method == "POST":
        ok, err = _save_product(p)
        if ok:
            flash("Produk berhasil diperbarui.")
            return redirect(url_for("dashboard"))
        flash(err)
    return render_template("produk_form.html", product=p,
                           categories=_categories_for_select())


@app.route("/dashboard/produk/<int:pid>/hapus", methods=["POST"])
@umkm_required
def produk_hapus(pid):
    p = db.session.get(Product, pid)
    if not p or p.umkm_id != current_user.umkm_id:
        abort(404)
    db.session.delete(p)
    db.session.commit()
    flash("Produk dihapus.")
    return redirect(url_for("dashboard"))


def _save_product(p):
    """Buat (p=None) atau perbarui produk dari form. Return (ok, error)."""
    f = request.form
    name = (f.get("name") or "").strip()
    if not name:
        return False, "Nama produk wajib diisi."
    try:
        price = int(f.get("price") or 0)
    except ValueError:
        return False, "Harga harus angka."
    if price <= 0:
        return False, "Harga harus lebih dari 0."
    cat_id = f.get("category_id")
    cat_id = int(cat_id) if cat_id else None

    def _int(key, default=0):
        try:
            return int(f.get(key) or default)
        except ValueError:
            return default

    if p is None:
        p = Product(umkm_id=current_user.umkm_id)
        db.session.add(p)
    p.name = name
    p.description = (f.get("description") or "").strip()
    p.price = price
    p.category_id = cat_id
    p.unit = (f.get("unit") or "pcs").strip()
    p.stock = _int("stock")
    p.weight_gram = _int("weight_gram")
    p.min_order = _int("min_order", 1)
    p.sold = _int("sold", p.sold or 0)
    p.emoji = (f.get("emoji") or "📦").strip() or "📦"
    db.session.commit()
    return True, None


@app.route("/dashboard/profil", methods=["GET", "POST"])
@umkm_required
def profil():
    u = current_user.umkm
    if request.method == "POST":
        f = request.form
        u.name = (f.get("name") or u.name).strip()
        u.description = (f.get("description") or "").strip()
        u.region = (f.get("region") or "").strip()
        u.city = (f.get("city") or "").strip()
        u.contact_name = (f.get("contact_name") or "").strip()
        u.contact_phone = (f.get("contact_phone") or "").strip()
        u.contact_whatsapp = (f.get("contact_whatsapp") or "").strip()
        u.contact_email = (f.get("contact_email") or "").strip()
        try:
            u.lat = float(f.get("lat")) if f.get("lat") else None
            u.lng = float(f.get("lng")) if f.get("lng") else None
        except ValueError:
            flash("Koordinat lat/lng harus angka.")
            return render_template("profil.html", umkm=u)
        current_user.name = u.name
        db.session.commit()
        flash("Profil diperbarui.")
        return redirect(url_for("dashboard"))
    return render_template("profil.html", umkm=u)


# ----------------------------- Direktori Agen + rating balik -----------------------------
@app.route("/agen")
def agen_list():
    agens = Agen.query.order_by(Agen.name).all()
    data = []
    for a in agens:
        avg, n = agen_rating(a.id)
        data.append({"a": a, "rating": avg, "count": n})
    regions = sorted({a.region for a in agens if a.region})
    return render_template("agen.html", agens=data, regions=regions)


@app.route("/produsen")
def produsen_list():
    umkms = Umkm.query.order_by(Umkm.name).all()
    data = []
    for u in umkms:
        avg, n = umkm_rating(u.id)
        cnt = Product.query.filter_by(umkm_id=u.id).count()
        data.append({"u": u, "rating": avg, "count": n, "products": cnt})
    regions = sorted({u.region for u in umkms if u.region})
    return render_template("produsen.html", umkms=data, regions=regions)


@app.route("/agen/<int:aid>/rating", methods=["POST"])
@login_required
def rate_agen(aid):
    if current_user.role != "umkm":
        flash("Hanya akun UMKM yang dapat menilai Agen.")
        return redirect(url_for("agen_list"))
    a = db.session.get(Agen, aid)
    if not a:
        abort(404)
    try:
        stars = int(request.form.get("stars") or 0)
    except ValueError:
        stars = 0
    if not (1 <= stars <= 5):
        flash("Pilih bintang 1-5.")
        return redirect(url_for("agen_list"))
    comment = (request.form.get("comment") or "").strip()
    author = current_user.umkm.name if current_user.umkm else current_user.name
    db.session.add(Rating(target_type="agen", target_id=aid, author_type="umkm",
                          author_name=author, author_user_id=current_user.id,
                          stars=stars, comment=comment))
    db.session.commit()
    flash(f"Rating untuk {a.name} terkirim.")
    return redirect(url_for("agen_list"))


# ----------------------------- Dashboard Agen (distributor) -----------------------------
@app.route("/agen/dashboard")
@agen_required
def agen_dashboard():
    a = current_user.agen
    avg, n = agen_rating(a.id)
    reviews = (Rating.query.filter_by(target_type="agen", target_id=a.id)
               .order_by(Rating.id.desc()).all())
    given = (Rating.query.filter_by(author_type="agen", author_user_id=current_user.id)
             .order_by(Rating.id.desc()).all())
    targets = {u.id: u.name for u in Umkm.query.all()}
    history = [{"name": targets.get(r.target_id, "UMKM"), "stars": r.stars,
                "comment": r.comment, "created": r.created} for r in given]
    return render_template("dashboard_agen.html", agen=a, rating=avg,
                           rating_count=n, reviews=reviews, history=history)


@app.route("/agen/profil", methods=["GET", "POST"])
@agen_required
def agen_profil():
    a = current_user.agen
    if request.method == "POST":
        f = request.form
        a.name = (f.get("name") or a.name).strip()
        a.description = (f.get("description") or "").strip()
        a.region = (f.get("region") or "").strip()
        a.city = (f.get("city") or "").strip()
        a.contact_name = (f.get("contact_name") or "").strip()
        a.contact_phone = (f.get("contact_phone") or "").strip()
        a.contact_whatsapp = (f.get("contact_whatsapp") or "").strip()
        a.contact_email = (f.get("contact_email") or "").strip()
        current_user.name = a.name
        db.session.commit()
        flash("Profil diperbarui.")
        return redirect(url_for("agen_dashboard"))
    return render_template("profil_agen.html", agen=a)


# ----------------------------- Panel Admin -----------------------------
@app.route("/admin")
@admin_required
def admin_panel():
    umkms = Umkm.query.order_by(Umkm.name).all()
    agens = Agen.query.order_by(Agen.name).all()
    return render_template("admin.html", umkms=umkms, agens=agens)


@app.route("/admin/umkm/<int:uid>/verify", methods=["POST"])
@admin_required
def admin_toggle_umkm(uid):
    u = db.session.get(Umkm, uid)
    if not u:
        abort(404)
    u.verified = 0 if u.verified else 1
    db.session.commit()
    flash(("Verifikasi diberikan ke " if u.verified else "Verifikasi dicabut dari ") + u.name)
    return redirect(url_for("admin_panel"))


@app.route("/admin/agen/<int:aid>/verify", methods=["POST"])
@admin_required
def admin_toggle_agen(aid):
    a = db.session.get(Agen, aid)
    if not a:
        abort(404)
    a.verified = 0 if a.verified else 1
    db.session.commit()
    flash(("Verifikasi diberikan ke " if a.verified else "Verifikasi dicabut dari ") + a.name)
    return redirect(url_for("admin_panel"))


if __name__ == "__main__":
    init_db(app)
    print("SANTUY berjalan di http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
