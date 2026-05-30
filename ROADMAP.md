# 🗺️ ROADMAP SANTUY

Tujuan (pilihan **C**): data permanen + login pengelolaan sendiri **DAN** bisa
diakses online lewat link.

## Tahap 1 — selesai
Web app Flask + SQLite: katalog, smart search + auto-suggest, filter dinamis,
sorting, pencarian lokasi (GPS), contact person, rating dua arah. Data seed.

## Tahap 2 (universal) — selesai

### A. Akun & pengelolaan mandiri
- [x] Tabel `user` (peran: UMKM / Agen) dengan password di-hash (werkzeug).
- [x] Halaman Daftar & Login + session (Flask-Login).
- [x] Dashboard UMKM: tambah / edit / hapus produk & profil sendiri (CRUD).
- [x] Hubungkan produk & rating ke akun (bukan data seed statis).
- [x] Agen login untuk memberi rating; UMKM beri rating balik ke Agen.

### B. Deployment online
- [x] Production server (gunicorn) + `Procfile` + `wsgi.py`.
- [x] Migrasi DB ke SQLAlchemy → portabel SQLite ↔ PostgreSQL.
- [x] Variabel environment: `DATABASE_URL`, `SECRET_KEY` (+ `.env.example`).
- [x] File siap deploy: `requirements.txt`, `runtime.txt`, `Procfile`.
- [ ] Langkah manual: push ke Git + buat Web Service & PostgreSQL di
      Render/Railway, set env vars → dapat link publik (butuh akun hosting).

### Catatan teknis
- `database.py` kini memakai model SQLAlchemy; satu kode jalan di SQLite (lokal)
  maupun PostgreSQL (online) lewat `DATABASE_URL`.
- Seed otomatis hanya saat DB kosong (idempoten).

## Ide tahap 3 (opsional)
- Verifikasi UMKM oleh admin, upload foto produk, statistik dashboard,
  notifikasi email, pagination katalog.
