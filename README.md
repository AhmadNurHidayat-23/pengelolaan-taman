# Pengelolaan Taman

Pendataan dan pemeliharaan taman kota. Prototipe portofolio independen, bukan aplikasi resmi pemerintah.

## Fitur utama

- CRUD taman, wilayah dan fasilitas, pencarian/filter serta arsip/pemulihan tanpa menghapus riwayat.
- Inspeksi kondisi fasilitas dengan riwayat menurut tanggal; status belum diperiksa ditampilkan secara jujur.
- Jadwal perawatan, kegiatan dan progres yang dicatat petugas, riwayat perawatan dan laporan CSV kondisi.
- Admin mengelola data induk/jadwal; Admin dan Petugas mencatat inspeksi serta kegiatan.

## Teknologi

Python 3.13, Flask, SQLite, HTML, CSS, JavaScript.

## Cara instalasi

~~~powershell
cd C:\laragon\www\pengelolaan-taman
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m core.users --role Admin
~~~

Ulangi perintah akun dengan --role Petugas. Kata sandi dimasukkan melalui prompt. Tidak ada akun bawaan.

## Cara menjalankan

~~~powershell
.venv\Scripts\python run.py
~~~

Buka http://127.0.0.1:5471. SQLite instance/app.sqlite dibuat otomatis, aman diinisialisasi ulang. APP_INSTANCE mengganti lokasi; SECURE_COOKIE=1 untuk HTTPS. Tes: .venv\Scripts\python -m pytest -q. Tanggal memakai WIB. Selesaikan atau batalkan jadwal sebelum mengarsipkan fasilitas, lalu arsipkan fasilitas sebelum taman. Perawatan tidak mengubah hasil inspeksi secara otomatis.
