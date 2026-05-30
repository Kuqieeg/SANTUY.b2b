"""Entry point untuk server produksi (gunicorn).
Memastikan skema dibuat + seed dijalankan sebelum melayani request.

Jalankan: gunicorn wsgi:app
"""
from app import app
from database import init_db

init_db(app)

if __name__ == "__main__":
    app.run()
