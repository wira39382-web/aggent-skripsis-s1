# Dashboard dan audit proposal — v0.3.0

Ini implementasi tahap proposal berdasarkan kontrak revisi 6, setelah alur jurnal berjalan. Tidak mengimplementasikan statistik, penulisan naskah, atau pengesahan akademik.

## Kemampuan yang tersedia

| Bagian | Perilaku |
|---|---|
| Dashboard | Navigasi Ringkasan, Proposal & audit, Literatur, Daftar revisi; jumlah dokumen dan revisi dari database, versi aplikasi, serta langkah berikutnya. Tidak ada persentase mutu/kelulusan buatan. |
| Jenis dokumen | Proposal, jurnal, pedoman. Dokumen lama tanpa metadata jenis tetap jurnal. Unggahan proposal terbaru menjadi aktif; versi sebelumnya dipertahankan dan tidak menerima audit/perubahan isu baru. |
| Struktur offline | Calon heading Bab I–III, lokasi halaman, cakupan keterbacaan. Heading belum terdeteksi tidak berarti bab tidak ada. Hasil bisa memuat daftar isi; tidak mengklaim segmentasi bab sempurna. |
| Audit substantif | Sepuluh kriteria wajib dalam satu keluaran/snapshot. AI memerlukan kredensial dan persetujuan pengiriman proposal/pedoman terpilih. Tanpa AI, tidak ada hasil audit tiruan. |
| Bukti | Document ID, halaman fisik PDF, kutipan persis; dipadankan terhadap teks terbaca sumber yang dipilih. Penilaian memadai/perlu revisi wajib menunjuk proposal. Temuan kepatuhan juga wajib menunjuk aturan dalam pedoman. |
| Ketidakpastian | Status unknown dipertahankan. Kepatuhan tanpa pedoman tidak boleh dianggap memadai. Isi sumber jurnal asli tidak disertakan: kriteria literatur tidak boleh berstatus adequate; masalah tertulis yang berbukti boleh ditandai perlu revisi, selain itu unknown. |
| Temuan manual | Dapat dicatat tanpa AI, dengan kriteria, tingkat masalah, ringkasan, tindakan, aktor lokal, kutipan dan halaman. Identitas/otoritas pencatat tidak diautentikasi. |
| Isu dan riwayat | ID stabil per proposal, kriteria, dan asal (manual/AI). Temuan baru pada kombinasi sama memperbarui deskripsi dan menambah event beserta snapshot, bukan menghapus riwayat. Temuan AI yang muncul lagi dibuka kembali. |
| Tindak lanjut | Terbuka → sedang dikerjakan → ditandai ditangani (bisa dibuka kembali), dengan aktor dan alasan wajib. Bukan status selesai terverifikasi/persetujuan. Formulir event lama ditolak HTTP 409. |
| Pergantian sumber | Proposal baru mengarsipkan status aktif versi sebelumnya. PDF/pedoman hilang/berubah membuat snapshot usang. Hasil audit tidak diterapkan jika sumber berubah selama permintaan AI. |
| Jurnal | Analisis dan tinjauan versi-terikat sebelumnya tetap berjalan pada ruang Literatur. Proposal tidak diproses sebagai jurnal. |

Rubrik: pedoman/struktur, masalah/kontribusi, keselarasan, teori/literatur, pengukuran, sampling, dasar ukuran sampel, rencana analisis, etika/izin, argumentasi/atribusi. Audit bukan detektor plagiarisme, verifikasi DOI, konfirmasi izin yang benar-benar berlaku, atau penetapan kelayakan metode oleh otoritas akademik.

## API audit

`POST /api/documents/{id}/proposal/audits`:

```json
{"mode":"structure", "guideline_ids":[]}
```

Mode `ai` memerlukan `consent: true`. Pilih maksimal lima pedoman dari proyek yang sama. Hanya proposal dan pedoman terpilih dikirim, bukan seluruh dokumen proyek. Total teks maksimal 100.000 karakter; tidak dipotong diam-diam. Status belum dikonfigurasi mengembalikan HTTP 503 dan tidak membuat temuan.

Audit disimpan append-only. Riwayat UI/API menampilkan 20 audit terbaru dan audit substantif terakhir bila sudah lebih lama; seluruh arsip tetap di database. Riwayat struktur yang panjang tidak membuat audit substantif terakhir hilang dari tampilan. Kegagalan alat dicatat sebagai kegagalan, bukan kesimpulan isi proposal.

`POST /api/documents/{id}/proposal/issues` menerima `criterion`, `severity`, `summary`, `recommendation`, `actor`, `evidence` dan opsional `guideline_ids`. Bukti berupa array `{"document_id":"…", "pdf_page":1, "quote":"kutipan persis"}`. Kriteria berasal dari rubrik server. Tingkat masalah: minor/major/critical.

`POST /api/issues/{id}/events` menerima `status`, `actor`, `note`, dan `expected_event_id` dari event terakhir yang dilihat. Status hanya open/in_progress/addressed. Tidak tersedia operasi yang menyatakan proposal disetujui pembimbing.

## Konsistensi dan migrasi

Tabel jenis dokumen, audit, isu, dan event dibuat secara aditif. Proyek, analisis jurnal, review, dan PDF lama tidak dihapus. Metadata jenis yang tidak ada dibaca sebagai journal. Memperbarui jenis dokumen lama melalui UI belum tersedia; unggah proposal baru dengan jenis yang tepat.

Seluruh audit disimpan hanya jika proposal aktif dan hash PDF/ekstraksi seluruh masukan masih cocok. Pemeriksaan dan penyimpanan berada dalam transaksi. ID isu berdasarkan kriteria tetap stabil walau ringkasan/rekomendasi berubah; riwayat aktor/tindakan/sumber tidak direset. Ini belum merupakan engine retry/budget otomatis untuk semua tahap penelitian.

Status dashboard tidak pernah otomatis menjadi siap sidang/disetujui. Unknown, sumber usang, temuan belum ditangani, dan pembacaan parsial tetap tampak. Status addressed adalah catatan pekerjaan, bukan bukti bahwa klaim atau naskah telah diperbaiki. Unggah proposal revisi dan audit ulang untuk memeriksa versi baru.

## Validasi dan batas kesimpulan

Suite pengujian mencakup alur lama serta tambahan proposal/dashboard: role dan hitungan aktual, audit struktur offline, penolakan AI tanpa konfigurasi/persetujuan, kutipan rekaan, halaman salah, kriteria tidak lengkap, sumber pedoman lintas proyek/tidak dipilih, aturan kampus tanpa bukti, perubahan sumber selama audit, migrasi metadata lama, isu stabil/reopen, dan konflik perubahan status.

Browser memeriksa perubahan tampilan, judul panjang, lebar 390 px, versi server lama, unggah proposal, struktur tanpa AI, temuan manual, perubahan status/persistensi, arsip proposal, audit AI dengan mock, dan alur jurnal lama. Gambar dokumentasi berlabel proyek uji sintetis; tidak memuat data penelitian pengguna atau API key.

Tidak ada klaim kualitas analisis AI nyata: pengujian memakai respons penyedia tiruan. OCR, aturan kampus yang tidak dilampirkan, verifikasi isi jurnal untuk audit proposal, penyuntingan otomatis Bab I–III, ekspor DOCX, dan verifikasi penutupan isu oleh pihak berwenang belum tersedia. Kriteria/heading alternatif mengikuti keterbatasan deteksi teks; pengguna perlu meninjau PDF asli. Server tetap prototipe lokal.

Hasil akhir validasi v0.3.0: **61 tes lulus** pada Python 3.12.14 dan 3.13.5 di Linux, dengan ResourceWarning dijadikan error. Kedua skrip browser lulus. Startup CLI dan layanan yang berjalan pada port 8000 mengembalikan versi 0.3.0, stage proposal_workspace, AI not_configured, serta aset JavaScript HTTP 200. Pengujian langsung di Windows untuk versi ini belum dilakukan; gunakan perintah README dan periksa jumlah 61 tes.

[Tampilan dashboard pada proyek uji sintetis](../screenshots/dashboard-v030.png) · [Ruang audit proposal dengan respons AI tiruan berlabel](../screenshots/proposal-v030.png).
