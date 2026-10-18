# Asisten Skripsi S1

Fondasi aplikasi lokal untuk asisten penelitian kuantitatif. Ini belum agent skripsi lengkap.

## Persyaratan dan startup

Python 3.11 atau lebih baru. Versi awal hanya menggunakan standard library, sehingga tidak ada dependensi pihak ketiga yang perlu diinstal.

```sh
python3 --version
python3 -m unittest discover -s tests -v
python3 app.py --port 8000
```

Buka http://127.0.0.1:8000. Pada Windows gunakan `python` jika `python3` tidak tersedia. Hentikan dengan Ctrl+C. Port dapat diganti menggunakan `--port 8001`.

Data tersimpan di `data/projects.sqlite3`. Gunakan `--data-dir /path/tujuan` untuk lokasi lain. Jangan menghapus direktori ini bila ingin mempertahankan proyek. Direktori data tidak masuk Git.

## Tersedia

- Antarmuka membuat dan menampilkan proyek penelitian.
- Penyimpanan SQLite yang bertahan setelah restart.
- Health endpoint `/api/health` dan API proyek `/api/projects`.
- Pengujian HTTP dan penyimpanan.
- Spesifikasi alur pada `docs/alur-agent-skripsi.mmd`.

## Belum tersedia

Unggah/ekstraksi PDF, OCR, pencarian jurnal, verifikasi klaim, integrasi AI, analisis statistik dan ekspor DOCX. Tidak ada hasil penelitian contoh yang ditampilkan sebagai hasil nyata.

## Batas penggunaan

Server standard library ini hanya untuk pengembangan lokal dan mengikat localhost. Belum ada autentikasi, otorisasi multi-pengguna, atau kesiapan deployment publik. Jangan memasukkan data responden sensitif. Jangan menyimpan API key atau PDF penelitian di repository publik.

## Tahap implementasi berikutnya

1. Unggah PDF dengan validasi ukuran/jenis, penyimpanan di luar Git, ekstraksi teks per halaman dan penanda kegagalan OCR.
2. Analisis satu jurnal dengan lokasi bukti; status AI belum dikonfigurasi bila kredensial belum tersedia.
3. Pencarian dan verifikasi metadata dengan pembedaan ditemukan/dibaca/mendukung klaim.
4. Rancangan penelitian, analisis kuantitatif tervalidasi, penulisan dan audit berdasarkan diagram.

Perubahan metode, instrumen, data, atau sumber harus menandai hasil turunannya untuk diperiksa ulang. Draf siap ditinjau bukan persetujuan pembimbing.
