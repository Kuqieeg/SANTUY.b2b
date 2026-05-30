"""
SANTUY - Database layer (SQLAlchemy)
Satu kode jalan di SQLite (lokal) maupun PostgreSQL (online) lewat DATABASE_URL.

Skema mengikuti DFD: aktor UMKM (Produsen/Vendor) & Agen (Distributor),
proses Manajemen Pengguna/Kontak, Kelola Katalog & Smart Categorizing,
Smart Searching, dan Sistem Rating dua arah. Tahap 2 menambah akun (User)
dengan password di-hash + pengelolaan mandiri (CRUD).
"""
import os
import math
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect as sa_inspect, text
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ----------------------------- Helper murni -----------------------------
def haversine(lat1, lon1, lat2, lon2):
    """Jarak antar dua titik koordinat (km) untuk pencarian berbasis lokasi."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * R * math.asin(math.sqrt(a)), 1)


def price_tier(price):
    """Smart categorizing berdasarkan harga grosir B2B."""
    if price < 25000:
        return "Hemat"
    if price < 100000:
        return "Menengah"
    return "Premium"


def database_url():
    """Ambil DATABASE_URL; normalkan skema lama 'postgres://' -> 'postgresql://'.
    Default ke SQLite di samping file ini bila env tidak diset."""
    url = os.environ.get("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    return "sqlite:///" + os.path.join(os.path.dirname(os.path.abspath(__file__)), "santuy.db")


# ----------------------------- Model -----------------------------
class Category(db.Model):
    __tablename__ = "category"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    icon = db.Column(db.String(16), default="📦")


class Umkm(db.Model):
    __tablename__ = "umkm"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    owner = db.Column(db.String(160))
    description = db.Column(db.Text)
    region = db.Column(db.String(120))
    city = db.Column(db.String(120))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    contact_name = db.Column(db.String(160))
    contact_phone = db.Column(db.String(60))
    contact_whatsapp = db.Column(db.String(60))
    contact_email = db.Column(db.String(160))
    verified = db.Column(db.Integer, default=0)
    products = db.relationship("Product", backref="umkm", cascade="all, delete-orphan")


class Product(db.Model):
    __tablename__ = "product"
    id = db.Column(db.Integer, primary_key=True)
    umkm_id = db.Column(db.Integer, db.ForeignKey("umkm.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Integer, nullable=False)      # harga grosir B2B per unit
    unit = db.Column(db.String(40), default="pcs")
    stock = db.Column(db.Integer, default=0)
    weight_gram = db.Column(db.Integer, default=0)
    min_order = db.Column(db.Integer, default=1)
    views = db.Column(db.Integer, default=0)           # popularitas
    sold = db.Column(db.Integer, default=0)
    emoji = db.Column(db.String(16), default="📦")
    category = db.relationship("Category")


class Agen(db.Model):
    __tablename__ = "agen"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    region = db.Column(db.String(120))
    city = db.Column(db.String(120))
    contact_name = db.Column(db.String(160))
    contact_phone = db.Column(db.String(60))
    contact_whatsapp = db.Column(db.String(60))
    contact_email = db.Column(db.String(160))
    jenis = db.Column(db.String(20), default="Distributor")  # 'Agen' atau 'Distributor'
    verified = db.Column(db.Integer, default=0)


class Rating(db.Model):
    __tablename__ = "rating"
    id = db.Column(db.Integer, primary_key=True)
    target_type = db.Column(db.String(16), nullable=False)   # 'umkm' atau 'agen'
    target_id = db.Column(db.Integer, nullable=False)
    author_type = db.Column(db.String(16), nullable=False)   # 'agen' atau 'umkm'
    author_name = db.Column(db.String(160))
    author_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    stars = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created = db.Column(db.DateTime, default=datetime.utcnow)


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(16), nullable=False)          # 'umkm' atau 'agen'
    name = db.Column(db.String(160))
    umkm_id = db.Column(db.Integer, db.ForeignKey("umkm.id"))
    agen_id = db.Column(db.Integer, db.ForeignKey("agen.id"))
    created = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    umkm = db.relationship("Umkm")
    agen = db.relationship("Agen")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)


# ----------------------------- Init & Seed -----------------------------
def init_db(app):
    """Buat tabel bila belum ada, lalu seed jika kosong (idempoten)."""
    with app.app_context():
        db.create_all()
        _migrate()
        if Umkm.query.count() == 0:
            seed()
        ensure_admin()


def _migrate():
    """Migrasi ringan: tambah kolom baru pada DB lama tanpa kehilangan data."""
    insp = sa_inspect(db.engine)
    agen_cols = [c["name"] for c in insp.get_columns("agen")]
    if "jenis" not in agen_cols:
        db.session.execute(text(
            "ALTER TABLE agen ADD COLUMN jenis VARCHAR(20) DEFAULT 'Distributor'"))
    if "verified" not in agen_cols:
        db.session.execute(text("ALTER TABLE agen ADD COLUMN verified INTEGER DEFAULT 0"))
    user_cols = [c["name"] for c in insp.get_columns("user")]
    if "is_admin" not in user_cols:
        db.session.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
    db.session.commit()


def ensure_admin():
    """Pastikan ada satu akun admin (kredensial dari env, ada default untuk demo)."""
    email = os.environ.get("ADMIN_EMAIL", "admin@santuy.id").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    if User.query.filter_by(is_admin=True).first():
        return
    u = User.query.filter_by(email=email).first()
    if u:
        u.is_admin = True
    else:
        u = User(email=email, role="admin", name="Administrator", is_admin=True)
        u.set_password(password)
        db.session.add(u)
    db.session.commit()


def seed():
    categories = [
        Category(name="Makanan & Minuman", parent_id=None, icon="🍱"),
        Category(name="Camilan", parent_id=1, icon="🍪"),
        Category(name="Minuman", parent_id=1, icon="🥤"),
        Category(name="Bumbu & Rempah", parent_id=1, icon="🌶️"),
        Category(name="Fashion & Tekstil", parent_id=None, icon="👕"),
        Category(name="Pakaian", parent_id=5, icon="👗"),
        Category(name="Kain & Batik", parent_id=5, icon="🧵"),
        Category(name="Kerajinan", parent_id=None, icon="🎨"),
        Category(name="Anyaman", parent_id=8, icon="🧺"),
        Category(name="Dekorasi", parent_id=8, icon="🪔"),
        Category(name="Pertanian", parent_id=None, icon="🌾"),
        Category(name="Hasil Tani", parent_id=11, icon="🥬"),
    ]
    db.session.add_all(categories)
    db.session.flush()

    umkms = [
        Umkm(name="Keripik Mantul", owner="Bu Sari",
             description="Produsen aneka keripik singkong & pisang premium.",
             region="Jawa Barat", city="Bandung", lat=-6.9147, lng=107.6098,
             contact_name="Sari Wulandari", contact_phone="022-7301234",
             contact_whatsapp="6281234500001", contact_email="sari@keripikmantul.id", verified=1),
        Umkm(name="Kopi Nusantara Jaya", owner="Pak Budi",
             description="Roastery kopi arabika & robusta langsung dari petani.",
             region="Jawa Tengah", city="Temanggung", lat=-7.3148, lng=110.1721,
             contact_name="Budi Santoso", contact_phone="0293-491200",
             contact_whatsapp="6281234500002", contact_email="budi@kopinusantara.id", verified=1),
        Umkm(name="Batik Larasati", owner="Bu Endang",
             description="Batik tulis & cap khas Pekalongan untuk reseller.",
             region="Jawa Tengah", city="Pekalongan", lat=-6.8898, lng=109.6753,
             contact_name="Endang Pratiwi", contact_phone="0285-431987",
             contact_whatsapp="6281234500003", contact_email="cs@batiklarasati.id", verified=1),
        Umkm(name="Anyaman Rotan Bahari", owner="Pak Joko",
             description="Kerajinan anyaman rotan & bambu skala grosir.",
             region="Kalimantan Selatan", city="Banjarmasin", lat=-3.3186, lng=114.5944,
             contact_name="Joko Susilo", contact_phone="0511-335577",
             contact_whatsapp="6281234500004", contact_email="joko@rotanbahari.id", verified=0),
        Umkm(name="Sambal Juara", owner="Bu Rina",
             description="Sambal kemasan aneka level pedas, tahan 6 bulan.",
             region="Jawa Timur", city="Surabaya", lat=-7.2575, lng=112.7521,
             contact_name="Rina Hartati", contact_phone="031-5012345",
             contact_whatsapp="6281234500005", contact_email="rina@sambaljuara.id", verified=1),
        Umkm(name="Tani Segar Makmur", owner="Pak Anton",
             description="Distributor sayur & beras organik dari petani lokal.",
             region="Jawa Barat", city="Garut", lat=-7.2278, lng=107.9087,
             contact_name="Anton Wijaya", contact_phone="0262-231400",
             contact_whatsapp="6281234500006", contact_email="anton@tanisegar.id", verified=1),
        Umkm(name="Konveksi Maju Bersama", owner="Bu Lina",
             description="Konveksi kaos & seragam, terima partai besar.",
             region="DKI Jakarta", city="Jakarta Timur", lat=-6.2250, lng=106.9004,
             contact_name="Lina Marlina", contact_phone="021-8765432",
             contact_whatsapp="6281234500007", contact_email="order@konveksimaju.id", verified=0),
        Umkm(name="Teh Herbal Sehat", owner="Pak Hadi",
             description="Produsen teh herbal & jahe instan kemasan.",
             region="Jawa Tengah", city="Semarang", lat=-6.9667, lng=110.4167,
             contact_name="Hadi Kusuma", contact_phone="024-7601122",
             contact_whatsapp="6281234500008", contact_email="hadi@tehherbal.id", verified=1),
    ]
    db.session.add_all(umkms)
    db.session.flush()

    # (umkm_id, cat_id, name, desc, price, unit, stock, weight, min_order, views, sold, emoji)
    products = [
        (1, 2, "Keripik Singkong Original 1kg", "Renyah, gurih, kemasan grosir.", 32000, "pack", 500, 1000, 10, 1240, 320, "🥔"),
        (1, 2, "Keripik Pisang Cokelat 1kg", "Pisang pilihan lapis cokelat.", 38000, "pack", 300, 1000, 10, 980, 210, "🍌"),
        (1, 2, "Basreng Pedas 500g", "Baso goreng pedas daun jeruk.", 21000, "pack", 800, 500, 20, 1600, 540, "🌶️"),
        (2, 3, "Kopi Arabika Gayo 1kg", "Roasted beans, medium roast.", 145000, "kg", 120, 1000, 5, 2100, 410, "☕"),
        (2, 3, "Kopi Robusta Temanggung 1kg", "Body tebal, cocok espresso.", 98000, "kg", 200, 1000, 5, 1750, 360, "☕"),
        (2, 3, "Kopi Drip Bag isi 50", "Praktis untuk kafe & kantor.", 75000, "box", 90, 600, 3, 640, 120, "📦"),
        (3, 7, "Batik Tulis Premium", "Kain batik tulis 2.4m.", 285000, "lembar", 60, 400, 3, 1320, 95, "🧵"),
        (3, 7, "Batik Cap Katun", "Kain batik cap halus 2m.", 95000, "lembar", 150, 350, 5, 870, 180, "🧵"),
        (4, 9, "Keranjang Rotan Set 3", "Set keranjang serbaguna.", 120000, "set", 80, 1500, 5, 430, 60, "🧺"),
        (4, 10, "Lampu Hias Bambu", "Dekorasi cahaya hangat.", 65000, "pcs", 110, 800, 6, 520, 88, "🪔"),
        (5, 4, "Sambal Bawang Level 5", "Pedas nampol, botol 200g.", 24000, "botol", 600, 250, 24, 1980, 720, "🌶️"),
        (5, 4, "Sambal Matah Bali 200g", "Segar khas Bali.", 27000, "botol", 400, 250, 24, 1450, 510, "🌶️"),
        (6, 12, "Beras Organik 5kg", "Pulen, bebas pestisida.", 78000, "karung", 250, 5000, 4, 760, 140, "🌾"),
        (6, 12, "Sayur Box Mingguan", "Aneka sayur segar petani.", 55000, "box", 180, 4000, 5, 690, 130, "🥬"),
        (7, 6, "Kaos Polos Cotton 30s", "Bahan adem, lusinan.", 35000, "pcs", 1000, 180, 12, 540, 300, "👕"),
        (7, 6, "Seragam Kerja Custom", "Bordir logo gratis >50pcs.", 89000, "pcs", 400, 300, 50, 410, 90, "👔"),
        (8, 3, "Teh Herbal Celup isi 25", "Campuran rempah menyehatkan.", 18000, "box", 700, 120, 24, 880, 260, "🍵"),
        (8, 3, "Jahe Merah Instan 250g", "Hangat, tanpa pengawet.", 22000, "pack", 520, 280, 20, 1120, 340, "🫚"),
    ]
    for p in products:
        db.session.add(Product(
            umkm_id=p[0], category_id=p[1], name=p[2], description=p[3], price=p[4],
            unit=p[5], stock=p[6], weight_gram=p[7], min_order=p[8],
            views=p[9], sold=p[10], emoji=p[11]))

    agens = [
        Agen(name="Toko Berkah Jaya", description="Toko grosir sembako & camilan.",
             region="DKI Jakarta", city="Jakarta Pusat", contact_name="Hendra",
             contact_phone="6281299900001", contact_whatsapp="6281299900001",
             contact_email="berkahjaya@agen.id", jenis="Agen"),
        Agen(name="Grosir Amanah", description="Distributor produk UMKM Jawa Barat.",
             region="Jawa Barat", city="Bandung", contact_name="Maya",
             contact_phone="6281299900002", contact_whatsapp="6281299900002",
             contact_email="amanah@agen.id", jenis="Distributor"),
        Agen(name="Distributor Sukses Mandiri", description="Jaringan distribusi Jawa Timur.",
             region="Jawa Timur", city="Surabaya", contact_name="Bambang",
             contact_phone="6281299900003", contact_whatsapp="6281299900003",
             contact_email="sukses@agen.id", jenis="Distributor"),
    ]
    db.session.add_all(agens)
    db.session.flush()

    ratings = [
        ("umkm", 1, "agen", "Toko Berkah Jaya", 5, "Keripik selalu fresh, packing rapi!"),
        ("umkm", 1, "agen", "Grosir Amanah", 4, "Respons cepat, harga grosir oke."),
        ("umkm", 2, "agen", "Distributor Sukses Mandiri", 5, "Kopinya juara, pelanggan suka."),
        ("umkm", 2, "agen", "Toko Berkah Jaya", 5, "Aroma mantap, repeat order."),
        ("umkm", 3, "agen", "Grosir Amanah", 4, "Motif batik bagus, pengiriman agak lama."),
        ("umkm", 5, "agen", "Toko Berkah Jaya", 5, "Sambal laris keras di toko saya."),
        ("umkm", 5, "agen", "Distributor Sukses Mandiri", 5, "Pedasnya pas, tahan lama."),
        ("umkm", 6, "agen", "Grosir Amanah", 4, "Sayur segar, kadang stok kosong."),
        ("umkm", 8, "agen", "Distributor Sukses Mandiri", 4, "Teh herbal disukai pelanggan."),
        ("agen", 1, "umkm", "Keripik Mantul", 5, "Pembayaran lancar, komunikatif."),
        ("agen", 2, "umkm", "Batik Larasati", 4, "Order rutin, terpercaya."),
        ("agen", 3, "umkm", "Kopi Nusantara Jaya", 5, "Agen profesional."),
    ]
    for r in ratings:
        db.session.add(Rating(target_type=r[0], target_id=r[1], author_type=r[2],
                              author_name=r[3], stars=r[4], comment=r[5]))

    db.session.commit()


if __name__ == "__main__":
    # Util CLI: buat skema + seed memakai app sementara.
    from flask import Flask
    a = Flask(__name__)
    a.config["SQLALCHEMY_DATABASE_URI"] = database_url()
    a.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(a)
    init_db(a)
    print("Database siap:", database_url())
