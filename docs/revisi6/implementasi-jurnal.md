# Penerapan revisi 6 pada alur jurnal

Bagian pertama kontrak revisi 6 kini diterapkan pada alur aplikasi yang sudah tersedia. Ini belum mengimplementasikan audit proposal, statistik, persetujuan akademik, atau seluruh state machine diagram.

| Kontrak | Implementasi yang tersedia |
|---|---|
| Status bukti berbeda dari dukungan makna | Kutipan tetap diperiksa terhadap halaman; pengguna memberi keputusan makna per bagian, mencakup seluruh klaim dalam bagian tersebut. |
| Ketidakpastian tidak dianggap lolos | Salah satu bagian `unknown` membuat status tinjauan keseluruhan `unknown`; `needs_revision` pada bagian mana pun memerlukan revisi. |
| Cakupan pembacaan terbatas | Bagian tidak ditemukan menggunakan keputusan `not_found_in_readable_text`; jika ada halaman gagal/kosong, hasil tinjauan tetap `reviewed_partial`. |
| Keputusan terikat versi | Catatan mengacu ID analisis, hash PDF dan fingerprint JSON ekstraksi. Tinjauan tidak diwariskan ke analisis baru. |
| Input/output berubah | Integritas berkas PDF diperiksa terhadap ukuran dan hash tersimpan. PDF hilang/berubah atau fingerprint ekstraksi berbeda menghasilkan `stale`; analisis dan tinjauan baru ditolak. Analisis sebelumnya setelah analisis baru menjadi `superseded`. Riwayat tidak dihapus. |
| Kendali konkurensi | Pemeriksaan versi dan penambahan review berada dalam satu transaksi SQLite; pembacaan dokumen/hasil/review memakai satu snapshot. Formulir basi ditolak HTTP 409. |
| Aktor dan kewenangan jelas | Nama peninjau merupakan catatan lokal yang dideklarasikan pengguna, bukan autentikasi atau bukti persetujuan pembimbing. Tidak ada label siap sidang/disetujui akademik. |
| Migrasi tidak merusak sumber | Tabel review ditambahkan tanpa menghapus/mengubah PDF, proyek, atau hasil lama. Hasil lama tanpa snapshot ekstraksi perlu dianalisis ulang sebelum menerima review baru. |

## Alur penggunaan

1. Pilih proyek dan unggah/pilih PDF.
2. Jika AI dikonfigurasi, jalankan analisis dengan persetujuan pengiriman teks. Tanpa kunci, status tetap belum dikonfigurasi.
3. Baca klaim, kutipan, halaman, dan konteks sumber. Untuk bagian berisi beberapa klaim, keputusan “didukung” berarti seluruh klaim di bagian itu diperiksa. Jika hanya sebagian didukung, pilih perlu revisi dan jelaskan bagian yang bermasalah.
4. Pilih keputusan kelima bagian, isi nama peninjau serta alasan/batas, lalu simpan.
5. Tinjauan baru menambah riwayat; keputusan lama tidak ditimpa. Analisis ulang dimulai dengan status belum ditinjau.

Nama dan catatan ditampilkan sebagai teks. Input pengguna bukan instruksi sistem atau HTML untuk dijalankan. Tinjauan parsial tidak mengeklaim halaman yang gagal sudah dibaca.

## API tinjauan

`POST /api/documents/{id}/reviews`, `Content-Type: application/json`:

```json
{
  "analysis_id": "ID analisis terbaru",
  "source_sha256": "hash PDF dari hasil analisis",
  "extraction_sha256": "fingerprint ekstraksi dari hasil analisis",
  "reviewer": "Nama peninjau",
  "note": "Alasan, bukti yang diperiksa, dan batas tinjauan",
  "decisions": {
    "tujuan": "supported",
    "metode": "supported",
    "sampel": "supported",
    "temuan": "needs_revision",
    "keterbatasan": "not_found_in_readable_text"
  }
}
```

Nilai di atas adalah contoh format permintaan, bukan hasil penelitian. Kelima bagian wajib ada. Pilihan `supported` hanya berlaku pada bagian berisi klaim; `not_found_in_readable_text` hanya pada bagian tidak ditemukan. Pilihan lain untuk setiap bagian: `needs_revision` atau `unknown`.

`GET /api/documents/{id}` menyediakan `analyses[].reviews` dan `analyses[].review_state`. Keluaran AI asli tetap `needs_review` sebagai catatan immutable; status tinjauan efektif berada pada `review_state`. Riwayat berurut penambahan, bukan semata jam dinding.

## Validasi dan batas

Suite menjadi **37 tes**. Empat belas tes review memeriksa keputusan wajib, migrasi, riwayat append-only, konflik ID/hash, perubahan ekstraksi, pembacaan parsial, catatan Unicode, penolakan lintas origin, serta kegagalan penyedia yang tidak menghapus tinjauan sah sebelumnya. Tiga tes lifecycle SQLite tetap memeriksa commit/rollback dan penutupan koneksi.

Browser smoke test memeriksa form tinjauan, status perlu revisi lalu tinjauan tercatat, persistensi setelah reload, reset tinjauan saat analisis ulang, serta rendering nama peninjau berisi markup sebagai teks. Penyedia AI memakai mock berlabel; tidak ada analisis penelitian nyata atau penilaian kualitas model yang diklaim.

Pemeriksaan otomatis masih sebatas kecocokan kutipan. Penilaian semantik berasal dari keputusan pengguna, bukan verifier AI independen. Review per klaim individual, edit klaim, penggantian/re-ekstraksi versi PDF melalui UI, engine isu/budget lintas seluruh tahap, serta modul statistik belum tersedia. Dashboard dan audit proposal v0.3.0 dijelaskan terpisah pada [implementasi proposal](implementasi-proposal.md). Unggahan PDF baru adalah dokumen terpisah; tidak otomatis menggantikan dokumen lama. Data asli dipertahankan.

Pemeriksaan akhir: 37 tes lulus pada Python 3.12.14 dan 3.13.5 (Linux), dengan ResourceWarning dijadikan error. Browser Chromium juga lulus, termasuk PDF yang diubah setelah analisis: form tinjauan dan analisis baru diblokir, PDF asli tidak ditawarkan, dan riwayat tetap tersedia. Pengujian langsung kode revisi ini di Windows masih perlu dilakukan pada komputer pengguna; tes Windows 23/23 yang dilaporkan sebelumnya adalah untuk versi sebelum penambahan tinjauan.
