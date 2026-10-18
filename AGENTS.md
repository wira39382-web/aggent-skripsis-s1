# Petunjuk pengembangan

- Baca README.md dan docs/alur-agent-skripsi.mmd sebelum mengubah cakupan.
- Setup awal: Python >=3.11; tidak ada dependency eksternal saat ini.
- Test: `python3 -m unittest discover -s tests -v`.
- Startup: `python3 app.py --port 8000` (localhost).
- Tambahkan dependency secara eksplisit beserta instruksi instalasi bila dibutuhkan.
- Jangan mengarang keluaran AI, referensi, atau hasil statistik saat integrasi belum tersedia.
- Semua data pengguna, PDF, database, dan secret berada di luar Git.
- Pertahankan data asli, riwayat keputusan, dan lokasi bukti.
- Simpan kunci API hanya di server; jangan menaruhnya di HTML/browser.
- Validasi modul statistik dengan hasil pembanding sebelum dinyatakan siap.
- Jangan menganggap prototipe server ini siap dipublikasikan. Autentikasi, batas upload dan server produksi perlu dirancang sebelum deployment.
- Implementasikan tahap berikutnya sebagai alur lengkap yang dapat diuji, bukan semua fitur sekaligus.
