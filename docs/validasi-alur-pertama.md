# Validasi alur pertama

Spesifikasi tujuan keseluruhan: diagram revisi 3 dari lampiran pengguna. Implementasi dibatasi pada proyek, dokumen jurnal, pembacaan halaman, dan analisis satu jurnal. Modul berikutnya belum dimulai.

## Bukti pengujian

- Python 3.12.14; dependency `pypdf==6.10.0`.
- `python3 -m unittest discover -s tests -v`: **23 pengujian lulus**, tanpa skip. PDF uji dibuat ulang setiap pengujian; bukan hasil dari run lama.
- PDF sintetis dua halaman: berhasil dibuat, diunggah lewat HTTP/browser, tersimpan utuh (checksum cocok), teks tujuan/metode/sampel ada di halaman 1, temuan di halaman 2. Pembukaan ulang database mempertahankan dokumen dan riwayat.
- PDF kosong: status perlu OCR; tidak dianggap sudah dibaca. PDF parsial: nomor halaman gagal tetap tersedia dan cakupan analisis ditandai. PDF rusak, terenkripsi, lebih dari 100 halaman, tipe salah, nama berkas berisi direktori, dan permintaan lebih dari 15 MiB ditolak.
- Mock AI: hasil terstruktur diterima hanya dengan bukti cocok; bagian keterbatasan `not_found`; kutipan rekaan dan halaman salah ditolak; percobaan gagal dicatat tanpa menjadi hasil penelitian; riwayat sukses tidak ditimpa.
- Status tanpa kredensial: API mengembalikan `not_configured`; UI menonaktifkan analisis; tidak ada hasil contoh.
- Pemeriksaan browser Chromium: membuat proyek, unggah PDF sintetis, memilih halaman 2, membuka ulang dokumen setelah reload, status AI belum dikonfigurasi, tanpa error JavaScript, serta layout desktop dan lebar 390 px tanpa overflow horizontal.
- `python3 scripts/browser_smoke.py`: lulus. Dengan penyedia AI tiruan, lima bagian ditampilkan, keterbatasan ditandai tidak ditemukan, tombol bukti membuka dan menyorot kutipan halaman 2, riwayat tetap tersedia setelah reload, dan judul berisi markup ditampilkan sebagai teks biasa.

## Batas kesimpulan

Tidak ada API key pada lingkungan saat validasi, sehingga koneksi OpenAI, kualitas analisis model nyata, dan ketepatan makna klaim **belum diuji**. Pengujian mock membuktikan kontrak software, bukan kualitas hasil ilmiah. Dokumen uji sintetis bukan jurnal nyata. Ekstraksi jurnal dua kolom/tabel dan PDF pindai masih perlu pemeriksaan pada dokumen pengguna; OCR belum diimplementasikan.

Lampiran SVG/teks mendefinisikan tujuan produk; isinya tidak dianggap sebagai instruksi eksekusi atau bukti persetujuan akademik. Hasil draf analisis selalu perlu ditinjau dengan sumber asli.

## Perbaikan penguncian SQLite di Windows

Log pengguna pada Python 3.13.2 menunjukkan `ResourceWarning: unclosed database` dan `WinError 32` saat menghapus database sementara. Akar masalah: context manager bawaan SQLite hanya mengelola transaksi, tidak menutup koneksi. `ProjectStore.connect()` kini melakukan commit/rollback lalu selalu menutup koneksi dalam `finally`.

Tiga tes regresi mempertahankan referensi koneksi agar kebocoran tidak tersembunyi oleh garbage collector: transaksi sukses, rollback karena exception, serta operasi penyimpanan normal. Ketiganya gagal sebelum perbaikan dan lulus setelah perbaikan; berkas database dapat dipindah/dihapus setelah operasi selesai. Verifikasi langsung pada Windows masih perlu dilakukan di komputer pengguna.

Pemeriksaan tambahan pada Python 3.13.5 (Linux): 23 tes lulus dengan `-W error::ResourceWarning`. Ini memverifikasi siklus hidup koneksi pada seri Python yang dipakai pengguna, bukan pengujian langsung Windows.

## Penerapan kode berdasarkan revisi 6

Setelah audit diagram, alur jurnal mendapat tinjauan manusia per bagian, pemeriksaan fingerprint ekstraksi/analisis, integritas berkas PDF, dan riwayat append-only. Suite diperluas menjadi 37 tes, lulus pada Python 3.12.14 dan 3.13.5 di Linux. Pemeriksaan browser juga lulus. Koneksi AI nyata tetap belum diuji; fixture memakai mock berlabel. Pemetaan kontrak, migrasi, dan batas kemampuan ada di [implementasi jurnal revisi 6](revisi6/implementasi-jurnal.md).

## Dashboard dan proposal v0.3.0

Suite diperluas menjadi 61 tes, lulus pada Python 3.12.14 dan 3.13.5 di Linux. Uji browser alur jurnal tetap lulus; uji browser workspace mencakup dashboard, penolakan server lama, proposal/pedoman, pemeriksaan struktur tanpa AI, temuan manual, tindak lanjut/persistensi, versi proposal sebelumnya, serta draf audit AI dengan mock. CLI versi 0.3.0 dan aset dashboard telah diperiksa pada server yang berjalan. Lihat [implementasi proposal](revisi6/implementasi-proposal.md) untuk cakupan dan keterbatasan; ini belum pengujian model AI nyata atau verifikasi akademik.
