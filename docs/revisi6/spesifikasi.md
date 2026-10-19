# Kontrak logika dan mutu — revisi 6

Dokumen ini adalah spesifikasi produk. Aturan kampus, etik, dan kewenangan persetujuan hanya berlaku setelah sumber dan lingkupnya diverifikasi; angka anggaran di bawah adalah kebijakan produk yang dapat diubah, bukan aturan akademik universal.

## 1. Bentuk proyek: keadaan aset, bukan satu nomor tahap

Inventaris menyimpan secara terpisah: ide, proposal, pedoman, literatur, instrumen, data, keluaran analisis, naskah, dan keputusan manusia. Beberapa dapat tersedia bersamaan. Proposal belum ada tidak menahan pembuatan proyek atau pembacaan jurnal. Data tersedia tidak berarti boleh langsung digunakan.

Setiap aset memiliki `artifact_id`, `version_id`, hash, jenis, asal, waktu, akses, dan dependensi versi. PDF dan data asli tidak ditimpa. Koreksi, ekstraksi ulang, transformasi, dan analisis ulang membuat versi baru. Keluaran yang bergantung pada versi berubah ditandai `stale`, termasuk kutipan, tabel, paragraf, dan kesimpulan; keluaran independen tidak ikut dibatalkan.

Penjadwal memilih satu tugas yang diperlukan untuk tujuan saat ini dan prasyaratnya terpenuhi. Aset yang masih sah digunakan kembali. Jika jenis penelitian tidak didukung, sistem menawarkan handoff atau pengembangan metode; tidak mengubah metode penelitian hanya agar sesuai kemampuan aplikasi.

## 2. Sumber aturan dan keputusan

Setiap aturan mencatat sumber, lokasi, penerbit/aktor, tanggal/versi, lingkup, dan status verifikasi. Pisahkan aturan kampus, arahan pembimbing, keputusan etik/izin, rekomendasi metodologis, serta kebijakan aplikasi.

Contoh proposal yang disetujui adalah bahan kalibrasi, bukan jaminan metodologis atau aturan baru. Konflik ditampilkan bersama dasar dan konsekuensinya; pihak yang berwenang menentukan penyelesaian. Aturan yang tidak ditemukan ditandai belum diketahui, bukan diisi dengan kebiasaan umum.

Setiap keputusan substantif mencatat `decision_id`, aktor/peran, waktu, alasan, versi yang disetujui, bukti, syarat, dan lingkup. Konfirmasi pengguna atas ringkasan tidak berarti persetujuan pembimbing. Perubahan signifikan pada desain/data/tujuan menilai ulang keputusan yang terdampak; persetujuan lama tetap ada sebagai riwayat, bukan otomatis berlaku untuk versi baru.

## 3. Kontrak setiap tugas dan gerbang

Tugas menyimpan tujuan, input beserta versi, prasyarat, capability yang diperlukan, keluaran, biaya/waktu, dan status. Status minimal:

| Status tugas | Arti dan tindakan |
|---|---|
| `ready` / `running` | Prasyarat terpenuhi / proses berjalan. |
| `blocked_input` | Bahan minimum tertentu belum tersedia; minta bahan itu, lanjutkan tugas independen. |
| `blocked_capability` | AI/OCR/alat/metode belum tersedia atau belum dikonfigurasi; tidak ada hasil pengganti rekaan. |
| `failed_tool` | Eksekusi gagal; diagnosis teknis, bukan kesimpulan penelitian. |
| `needs_revision` | Pemeriksaan menemukan masalah yang perlu diperbaiki pada target tertentu. |
| `awaiting_human` | Keputusan/bukti dari aktor tertentu diperlukan; pekerjaan independen boleh berjalan. |
| `passed` / `cancelled` | Kontrak keluaran dipenuhi / tugas dibatalkan dengan alasan. |

Setiap gerbang mencatat `gate_id`, scope, snapshot input, pemeriksa/metode, kriteria, evidence IDs, isu, dan keputusan. Hasil gerbang:

- **Memadai**: kriteria yang berlaku terpenuhi dan bukti cukup untuk lingkup ini.
- **Perlu revisi**: ada ketidaksesuaian yang teridentifikasi.
- **Belum dapat dinilai**: bukti atau capability wajib belum cukup.
- **Tidak relevan**: disertai alasan dan pihak penilai; bukan jalan pintas melewati persyaratan yang belum diketahui.

Audit paralel harus mengacu snapshot yang sama. Gerbang penggabungan menunggu status dari **seluruh audit yang berlaku**. Audit selesai dengan status “belum dapat dinilai” tidak membuat gerbang lolos. Status tidak relevan hanya diterima jika lingkup pengecualiannya dapat dibenarkan. Perubahan input selama audit membuat hasil audit terdampak usang dan perlu diperiksa ulang.

Keparahan isu dibedakan dari status: kritis, mayor, minor, belum dapat dinilai. `blocking` ditetapkan menurut pengaruh terhadap validitas/tujuan/izin; tidak semua masalah ejaan memblokir pekerjaan lain. Masalah kritis dan mayor yang memengaruhi validitas tidak dapat dikompensasi skor tinggi di aspek lain.

## 4. Rantai bukti: dari dokumen ke klaim

Setiap sumber memiliki status terpisah: identitas ditemukan, metadata diverifikasi, cakupan teks terbaca, dan penilaian dukungan terhadap klaim tertentu. Tidak ada satu status global “sumber valid” yang menggantikan semua pemeriksaan.

Untuk setiap klaim, simpan:

| Elemen | Isi minimum |
|---|---|
| Identitas klaim | Teks klaim, jenis (kutipan/ringkasan/inferensi), lingkup dan versi. |
| Sumber | Document/source ID, versi/hash, jenis sumber, akses full text/abstrak/bagian tertentu. |
| Lokasi | Halaman fisik PDF, halaman tercetak jika diketahui, kutipan atau rentang teks; tabel/sel/gambar bila relevan. |
| Cakupan pembacaan | Halaman sukses/gagal/OCR dan keterbatasan kualitas ekstraksi. |
| Dukungan makna | Mendukung, mendukung sebagian, bertentangan, tidak mendukung, atau belum dapat dinilai; sertakan alasan/pemeriksa. |
| Konteks | Artikel ini atau penelitian yang dikutip; populasi, variabel, desain, arah dan besaran hasil. |
| Pembatasan | Ketidakpastian, generalisasi, dan status perlu tinjauan. |

Kecocokan kutipan hanya membuktikan teks berada di lokasi itu. Periksa apakah kutipan benar-benar mendukung klaim, apakah konteksnya tidak dibalik, serta apakah tabel/angka dan populasi sesuai. Pernyataan hubungan tidak diubah menjadi sebab-akibat tanpa desain dan bukti yang memadai.

Untuk satu jurnal, keluaran minimum: tujuan, metode, sampel, temuan, keterbatasan. Setiap klaim yang diisi memiliki bukti. Bagian tidak ditemukan pada teks terbaca diberi `not_found_in_readable_text`; ini bukan bukti bahwa informasi tidak ada di artikel. Kegagalan alat diberi `extraction_failed` atau `provider_failed`, bukan `not_found`. Keterbatasan yang disimpulkan reviewer dipisahkan dari keterbatasan yang dilaporkan penulis.

Sumber yang hanya menyediakan abstrak tidak disebut sudah dibaca utuh. DOI/metadata cocok bukan validasi isi; pencarian kosong bukan bukti referensi palsu. Catat koreksi/retraksi yang diketahui dan sumber statusnya, tanpa mengklaim pencarian lengkap jika belum dilakukan.

Sintesis banyak jurnal membandingkan desain, populasi, definisi, pengukuran, kualitas, dan arah hasil; tidak hanya menghitung jumlah artikel yang “mendukung”. Waspadai satu kumpulan data yang dipakai beberapa publikasi. Research gap adalah usulan berbatas cakupan pencarian yang tercatat, bukan jaminan bahwa topik belum pernah diteliti di mana pun.

## 5. Penguatan proposal: perbaiki alasan sebelum kalimat

Urutan dependensi: masalah → pertanyaan → tujuan → konsep/teori → hipotesis bila relevan → pengukuran → data → analisis → batas kesimpulan. Struktur bab mengikuti pedoman aktual, bukan penomoran yang dipaksakan aplikasi.

Audit terpisah mencakup: aturan/format; masalah dan keselarasan; literatur dan bukti; desain/sampling/instrumen/analisis; etik/izin/privasi. Temuan memiliki lokasi, bukti, akibat, target perbaikan, serta kriteria penyelesaian. Reviewer menguji mata rantai terlemah dan alternatif penjelasan, bukan sekadar memberi penilaian bahasa yang positif.

Jika masalah inti ditemukan, tampilkan opsi yang layak beserta konsekuensi terhadap waktu, data, kemampuan, dan persetujuan. Pengguna memahami serta memutuskan perubahan substantif; keputusan akademik tambahan dicatat bila memang diperlukan. Koreksi format rutin tidak perlu memicu putaran persetujuan semua pihak.

Gerbang proposal minimal:

| Dimensi | Bukti penerimaan | Contoh penghambat |
|---|---|---|
| Masalah dan kontribusi | Masalah spesifik berbukti; pertanyaan dapat dijawab; kontribusi proporsional. | Gap dikarang atau hanya mengklaim “belum pernah diteliti”. |
| Keselarasan | Matriks pertanyaan–tujuan–variabel–data–analisis konsisten. | Tujuan kausal tetapi desain tidak mendukung klaim tersebut. |
| Literatur | Klaim penentu punya dukungan sumber yang dapat diperiksa; kontra-bukti dibahas. | Kutipan benar lokasinya tetapi tidak mendukung klaim. |
| Konsep dan pengukuran | Definisi, konstruk, indikator, skala, sumber/adaptasi jelas. | Indikator tidak mengukur konstruk atau sumber instrumen tidak diketahui. |
| Desain dan sampling | Populasi, unit analisis, cara sampling, kelayakan akses, keterbatasan dijelaskan. | Sampel tidak memungkinkan menjawab tujuan yang dinyatakan. |
| Ukuran sampel | Dasar sesuai tujuan/model: presisi/daya bila relevan, asumsi, nonrespons dan kelayakan. | Satu rumus universal atau rasio item tanpa dasar yang sesuai. |
| Rencana analisis | Estimand/parameter sasaran, estimator, penanganan missing, diagnostik, aturan keputusan. | Uji dipilih hanya karena tersedia dalam perangkat. |
| Etik dan prosedur | Ketentuan yang berlaku dipetakan; kebutuhan persetujuan dan privasi jelas. | Penggunaan data belum sah atau persetujuan wajib belum tersedia. |
| Penulisan dan atribusi | Argumen jelas, sumber teratribusi, aturan AI dipatuhi; perubahan tidak mengubah makna. | Pemeriksaan kemiripan/detektor AI dipakai sebagai satu-satunya bukti orisinalitas. |
| Pemahaman dan keterlacakan | Pengguna dapat menjelaskan alasan, alternatif, bukti, dan batas; tersedia sumber untuk mengecek. | Pengguna hanya mengulang keluaran AI tanpa memahami keputusan. |

Rubrik dapat menampilkan catatan/skor ordinal untuk membantu prioritas, tetapi tidak ada ambang rata-rata universal untuk menyatakan layak. Gerbang menggunakan kriteria wajib dan bukti; nilai minor tidak menutupi kegagalan kritis.

Dry run memakai data sintetis berlabel dalam ruang terpisah dan tidak pernah masuk tabel hasil penelitian. Dry run membuktikan jalur eksekusi; benchmark membuktikan kesesuaian perhitungan terhadap jawaban pembanding; audit metodologis menilai kesesuaian dengan pertanyaan dan data. Ketiganya berbeda.

Peninjau kritis boleh memakai konteks/model terpisah, tetapi temuannya tetap diverifikasi ke sumber. Klaim “independen” tidak dibuat hanya karena ada agent/model kedua. Latihan pemahaman memperbolehkan membuka naskah/sumber dan akomodasi yang sesuai; tidak menilai hafalan sebagai syarat mutu ilmiah.

## 6. Pelaksanaan dan analisis

Deteksi keberadaan data, asal, izin, dan keterpaparan hasil sejak inventaris. Untuk data lama, catat apa yang benar-benar diketahui tentang proses pengumpulan; jangan membuat riwayat persetujuan atau hipotesis prospektif secara retrospektif.

Sebelum rekrutmen/uji coba/pengumpulan baru, periksa persetujuan yang benar-benar diwajibkan untuk kegiatan itu. Persetujuan proposal, izin institusi, penilaian etik, dan persetujuan partisipan adalah objek terpisah. Syarat yang belum jelas ditahan pada tugas terkait sampai dapat dipastikan. Data dan persetujuan tidak boleh dikarang.

Rencana analisis diberi versi dan waktu; catat akses terhadap data/hasil sebelumnya. Amandemen dibolehkan dengan alasan, waktu, dampak, dan persetujuan yang relevan. Analisis tambahan setelah melihat hasil diberi label eksploratif bila sesuai, bukan dianggap rencana awal. Pengumpulan tambahan memerlukan alasan ilmiah dan aturan penghentian; tidak otomatis untuk mengejar p-value.

Data asli diberi hash dan dipertahankan. Buku kode, pembersihan, eksklusi, transformasi, penggabungan, dan missing-data handling menghasilkan versi/log baru. Pola jawaban mencurigakan menjadi isu pemeriksaan, bukan aturan otomatis membuang responden. Jejak keputusan tidak dihapus untuk membuat analisis tampak lebih baik.

Modul analisis hanya aktif untuk metode/parameter yang didukung dan lulus benchmark relevan. Rekam estimator, asumsi, skala, dependensi/klaster, parameter, versi perangkat, seed bila relevan, input/output hash, dan hasil pembanding. Modul belum tersedia berarti handoff, bukan mengganti rancangan demi alat.

Hasil eksternal dapat diimpor tetapi masuk audit provenance dan validitas. Catat perangkat asli dan pengaturan; jangan melabeli keluaran Python sebagai keluaran asli SPSS/SmartPLS. Ketidakmampuan mereproduksi seluruh detail harus tetap tampak sebagai batas verifikasi.

Audit hasil menilai perhitungan, diagnostik, ketidakpastian, ukuran efek/interval bila sesuai, sensitivitas, dan batas interpretasi. Tidak ada aturan otomatis menghapus indikator atau mengganti estimator saat asumsi bermasalah. Pilih penanganan yang beralasan dan catat dampaknya.

Hasil tidak signifikan, efek kecil, atau hipotesis yang tidak didukung tetap dapat lolos bila proses sah dan interpretasi proporsional. Retry tidak digunakan untuk mencari hasil yang disukai. Jika isu validitas tidak dapat ditangani, hasil dapat tetap disimpan/diekspor dengan label belum layak untuk klaim terkait.

## 7. Perbaikan, anggaran, dan perubahan versi

Setiap isu memiliki ID stabil, asal tahap, fingerprint masalah, bukti, dependensi, penanggung jawab, status, dan kriteria selesai. Perbaikan yang memunculkan isu sama tidak boleh mereset hitungan hanya dengan mengganti judul.

Contoh kebijakan awal: maksimal tiga upaya **otomatis** per isu dan anggaran waktu/biaya yang ditetapkan proyek. Upaya memerlukan masukan/diagnosis/perubahan berarti; pengulangan perintah yang sama tanpa diagnosis bukan strategi pemulihan. Deteksi stagnasi dari kriteria yang belum bergerak, bukan sekadar perubahan kata.

Jika anggaran habis, layanan belum tersedia, atau keputusan manusia diperlukan, jeda tugas terdampak. Simpan state dan bukti; lanjutkan pekerjaan independen. Masukan pembimbing baru tetap diterima. Kelanjutan upaya mesin setelah batas habis memerlukan keputusan dan budget baru, tanpa menghapus riwayat.

Router memilih **satu target per isu per iterasi** berdasarkan akar masalah, bukan menjalankan semua panah sekaligus. Dependensi menentukan urutan pekerjaan berikutnya. Catatan pembimbing/penguji juga masuk registry isu ini; komentar bukan pembenaran otomatis untuk merekayasa data atau klaim.

Resume menggunakan `scope`, `issue_id`, `target_task_id`, checkpoint, dan versi masukan yang masih berlaku. Guard setiap panah harus diperiksa, bukan dipilih bebas oleh model. Kedatangan bukti keputusan sidang kembali ke pemeriksaan keputusan, bukan mengulang sidang; bukti pengesahan kembali ke pemeriksaan kelengkapan final. Jika prasyarat checkpoint tidak lagi sah, jadwalkan ulang tugas yang terdampak. Menunggu perubahan tanpa tugas siap tidak menjalankan loop aktif atau menghabiskan budget AI.

## 8. Paket dan keputusan per fase

Bedakan tiga tingkat:

1. **Draf tersimpan / dapat diekspor**: boleh belum lolos, dengan label isu dan keterbatasan yang tampak pada paket.
2. **Siap ditinjau**: pemeriksaan internal untuk jenis paket terpenuhi; bukan persetujuan pembimbing.
3. **Disetujui oleh aktor tertentu**: ada bukti keputusan yang mengacu versi dan lingkup yang tepat.

`ready_for_review(scope, version)` hanya benar jika seluruh gerbang wajib untuk lingkup itu memadai (atau tidak relevan dengan alasan sah), bukti minimum tersedia, dependensi yang digunakan masih berlaku, serta tidak ada isu penghambat terbuka. Persetujuan reviewer yang akan diminta **bukan** prasyarat siap dikirim kepadanya; ini menghindari gerbang melingkar.

Ekspor memiliki manifest versi dan daftar berkas. Periksa hasil render, tabel/gambar/paginasi, kutipan, dan kelengkapan; kode ekspor yang sukses belum membuktikan paket dapat dibaca. Perubahan setelah ekspor menghasilkan paket versi baru.

### Jalur proposal

Paket proposal → tinjauan pembimbing → seminar proposal **jika diwajibkan oleh ketentuan terverifikasi** → revisi bila perlu → bukti keputusan atas versi yang berlaku. Jalur tanpa seminar tetap memerlukan bukti keputusan yang memang ditetapkan kampus. Persetujuan proposal hanya memenuhi milestone terkait; izin rekrutmen/pengumpulan/penggunaan data tetap diperiksa secara terpisah.

### Jalur akhir

Paket akhir → tinjauan → sidang akhir sesuai ketentuan → keputusan aktual. Keputusan “lulus dengan revisi” masuk revisi akhir dan verifikasi pihak yang berwenang; tidak otomatis masuk arsip final. Setelah seluruh syarat yang berlaku, versi akhir, bukti pengesahan, dan kelengkapan cocok, arsipkan sebagai versi disetujui. Salinan arsip draf tetap boleh disimpan dengan labelnya sendiri.

Menunggu keputusan tidak membatalkan pekerjaan independen, termasuk latihan penjelasan hasil. Keputusan akhir hanya dicatat sesuai bukti yang diberikan; aplikasi tidak mengarang izin atau persetujuan.

## 9. Ketahanan, privasi, dan AI

Dokumen pengguna adalah data tidak tepercaya. Instruksi di PDF tidak boleh mengubah aturan sistem, mengeksekusi kode, mengakses secret, atau memulai pengiriman data. Model hanya diberi masukan dan capability yang dibutuhkan tugas. Kunci API berada di backend, tidak di browser/Git/log.

Jelaskan tujuan pengiriman teks dan minta izin yang sesuai sebelum mengirim ke penyedia. Terapkan batas ukuran, halaman, waktu, biaya, dan akses; jangan menyimpan respons berisi rahasia dalam log. Catat penggunaan AI, model/versi jika tersedia, versi prompt, masukan/output yang boleh disimpan, serta revisi manusia.

AI/OCR/API belum dikonfigurasi atau gagal berarti kemampuan tersebut belum tersedia. Simpan dokumen dan lanjutkan pekerjaan yang tidak bergantung padanya. Jangan menampilkan respons sintetis sebagai analisis nyata. Backup, akses, retensi/penghapusan, dan redaksi identitas dirancang sebelum layanan multi-pengguna/produksi.

## 10. Skenario penerimaan yang harus dibuktikan saat implementasi

| Skenario | Perilaku yang benar |
|---|---|
| Baru punya ide | Dapat membuat proyek dan membaca jurnal; tidak dipaksa mengunggah proposal yang belum ada. |
| Sudah punya data/naskah | Inventaris keduanya; audit asal/izin dan input yang relevan sebelum memakai ulang hasil. |
| Satu audit proposal belum selesai | Hasil penggabungan tidak lolos hanya karena empat audit lain memadai. |
| Proposal berubah ketika diaudit | Audit versi lama tetap di riwayat, tetapi tidak menyatakan versi baru lolos. |
| PDF hanya abstrak / ada halaman gagal | Cakupan dibatasi; informasi tidak ditemukan pada teks terbaca tidak dinyatakan tidak ada dalam artikel. |
| Kutipan cocok tetapi konteks berlawanan | Pemeriksaan semantik menolak/membatasi klaim, bukan lolos karena substring cocok. |
| API key hilang atau OCR gagal | Status capability/kegagalan eksplisit; tidak ada temuan palsu. |
| Hasil studi tidak signifikan | Dapat lolos jika proses valid; tidak mengubah data agar signifikan. |
| Dry run menghasilkan tabel | Hanya artefak uji sintetis; tidak masuk hasil penelitian. |
| Instrumen/skor/aturan eksklusi berubah | Turunan terdampak usang, perlu perhitungan dan tinjauan ulang. |
| Pembimbing memberi revisi saat budget mesin habis | Catatan tetap masuk; tugas mesin menunggu budget/keputusan baru, riwayat tidak direset. |
| Belum ada aturan seminar proposal | Status aturan belum diketahui; tidak otomatis memilih jalur tanpa seminar. |
| Proposal disetujui | Membuka milestone terkait, tidak mengesahkan skripsi akhir atau seluruh izin data. |
| Sidang akhir lulus dengan revisi | Revisi dan bukti pengesahan versi akhir diselesaikan sebelum label arsip final disetujui. |
| Pengguna memakai catatan saat menjelaskan | Penalaran dinilai dari keputusan/bukti/asumsi, bukan hafalan atau kemampuan mengulang teks AI. |
| Satu isu kritis terbuka dengan skor total tinggi | Status siap ditinjau tetap tertahan pada lingkup terdampak. |

Skenario di atas adalah syarat penerimaan untuk pengembangan berikutnya, **bukan daftar tes aplikasi yang sudah lulus saat ini**. Implementasikan dan validasi satu alur yang lengkap sebelum menambah modul lain.
