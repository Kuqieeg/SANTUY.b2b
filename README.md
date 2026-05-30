# 🤝 SANTUY — Sahabat Antar Niaga Terhubung untuk You

Aplikasi web **marketplace B2B** yang menghubungkan **UMKM (Produsen/Vendor)**
dengan **Agen (Distributor/Konsumen)**. Dibangun dengan **Python (Flask)** +
**SQLAlchemy**, portabel **SQLite** (lokal) ↔ **PostgreSQL** (online), mengikuti
rancangan DFD proyek.

## ✨ Fitur

| Fitur | Keterangan |
|---|---|
| **Katalog produk** | Daftar produk grosir B2B lengkap dengan stok, berat, min. order, harga. |
| **Smart Categorizing** | Kategori & subkategori otomatis, **tier harga** (Hemat/Menengah/Premium), badge popularitas (Terlaris, Top Rated, Stok Terbatas). |
| **Smart Searching** | Pencarian + **auto-suggestion** real-time (produk, kategori, UMKM). |
| **Filter dinamis** | Daerah, kategori (termasuk subkategori), dan rentang harga. |
| **Sorting** | Termurah, termahal, rating, terpopuler, **terdekat**. |
| **Pencarian berbasis lokasi (GPS)** | Hitung jarak ke UMKM via koordinat browser (Haversine). |
| **Contact Person** | Komunikasi via telepon/email/WhatsApp UMKM — **bukan chat dalam aplikasi**, sesuai konsep. |
| **Akun & pengelolaan mandiri** | Daftar/login UMKM & Agen (Flask-Login, password di-hash). UMKM punya **dashboard CRUD** produk & profil sendiri. |
| **Sistem Rating dua arah** | **Agen** menilai **UMKM** (di halaman produk); **UMKM** menilai balik **Agen** (di direktori agen). Rating terhubung ke akun. |

## 🚀 Cara menjalankan (lokal)

```bash
cd app
pip install -r requirements.txt
python app.py
```

Lalu buka **http://127.0.0.1:5000**. Database `santuy.db` dibuat otomatis dan
diisi data contoh saat pertama dijalankan.

### Akun demo
Belum ada akun login bawaan — buat lewat halaman **Daftar**. Pilih peran
**UMKM** untuk mengakses dashboard CRUD, atau **Agen** untuk memberi rating UMKM.

## ☁️ Deploy online (Render / Railway)

1. Push folder `app/` ke repository Git (GitHub).
2. Buat **Web Service** baru di Render/Railway, arahkan ke repo tersebut.
3. Tambah database **PostgreSQL** di dashboard hosting, salin `DATABASE_URL`.
4. Set **Environment Variables**:
   - `SECRET_KEY` = string acak panjang
   - `DATABASE_URL` = URL Postgres dari langkah 3
5. **Start command**: `gunicorn wsgi:app` (sudah ada di `Procfile`).
6. Deploy → dapat link publik. Tabel + data seed dibuat otomatis saat start.

> Tanpa `DATABASE_URL`, aplikasi otomatis memakai SQLite lokal — jadi satu kode
> jalan di laptop maupun di server.

## 📁 Struktur

```
app/
├─ app.py            # Server Flask: pages, API, auth, dashboard CRUD, rating
├─ database.py       # Model SQLAlchemy + data seed (SQLite/PostgreSQL)
├─ wsgi.py           # Entry point gunicorn (buat skema + seed lalu serve)
├─ requirements.txt  # Flask, SQLAlchemy, Flask-Login, gunicorn, psycopg2
├─ Procfile          # web: gunicorn wsgi:app
├─ runtime.txt       # versi Python untuk hosting
├─ .env.example      # contoh SECRET_KEY & DATABASE_URL
├─ templates/
│  ├─ base.html       # Layout + navbar auth + flash
│  ├─ index.html      # Katalog + search + filter
│  ├─ product.html    # Detail produk + contact person + rating (Agen)
│  ├─ login.html / daftar.html
│  ├─ dashboard.html  # Dashboard UMKM
│  ├─ produk_form.html / profil.html  # CRUD produk & profil
│  └─ agen.html       # Direktori Agen + rating balik (UMKM)
└─ static/
   ├─ css/style.css
   └─ js/app.js       # Search, auto-suggest, filter, sorting, GPS
```

## 🔌 Ringkasan API & rute

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/api/products` | Cari produk. Param: `q, region, category, price_min, price_max, sort, lat, lng`. |
| GET | `/api/suggest?q=` | Auto-suggestion. |
| GET | `/api/categories` | Daftar kategori. |
| POST | `/api/rating` | Agen (login) menilai UMKM. Body JSON: `{umkm_id, stars(1-5), comment}`. |
| GET/POST | `/daftar`, `/login`, GET `/logout` | Autentikasi. |
| GET | `/dashboard` | Dashboard UMKM (CRUD produk + profil). |
| POST | `/agen/<id>/rating` | UMKM (login) menilai balik Agen. |

## ⚙️ Catatan

- Konfigurasi lewat environment variable: `DATABASE_URL`, `SECRET_KEY`.
- Seed hanya dijalankan saat database kosong (idempoten).

— Kelompok 2: Muhammad Djanitra, Nissa Aulia Nur'farida, Muhammad Raihan Pratama
