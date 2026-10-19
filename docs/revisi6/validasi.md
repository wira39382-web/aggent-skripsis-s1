# Validasi dokumentasi revisi 6

Pemeriksaan dilakukan pada sumber diagram yang dihasilkan dari `scripts/render_workflow_v6.py`. Ini validasi dokumentasi/graf, bukan pengujian runtime agent penelitian.

| Diagram | Simpul | Hubungan | Graphviz SVG | Mermaid 11.12.0 |
|---|---:|---:|---|---|
| 01 Kendali | 17 | 24 | Dirender, ID simpul cocok | Parse dan render berhasil |
| 02 Proposal | 26 | 38 | Dirender, ID simpul cocok | Parse dan render berhasil |
| 03 Pelaksanaan | 24 | 37 | Dirender, ID simpul cocok | Parse dan render berhasil |
| 04 Tinjauan | 25 | 45 | Dirender, ID simpul cocok | Parse dan render berhasil |
| **Total** | **92** | **144** | | |

Pemeriksaan generator: ID unik; seluruh ujung hubungan ada; semua simpul terjangkau dari titik masuk; setiap keputusan memiliki cabang berlabel; setiap simpul nonterminal memiliki kelanjutan; setiap simpul mempunyai jalur struktural ke status terminal. Kemungkinan tertahan menunggu masukan manusia tetap disengaja dan dijelaskan di spesifikasi, bukan dibuktikan hilang oleh pemeriksaan graf.

Regenerasi dua kali menghasilkan berkas DOT/Mermaid/SVG dengan hash yang sama pada lingkungan yang digunakan (Graphviz 2.42.4). Kesamaan byte lintas versi Graphviz/font tidak dijanjikan. SVG kendali dan tinjauan juga diperiksa secara visual melalui Chromium. Tautan lokal Markdown dapat diresolusikan. SVG sumber revisi 5 identik byte demi byte dengan lampiran pengguna.

Penelusuran manual memeriksa penggabungan audit pada snapshot yang sama, pemisahan keputusan proposal/akhir, serta resume keputusan sidang/revisi/pengesahan tanpa mengulang kegiatan yang sudah sah. Enam belas skenario penerimaan pada spesifikasi membatasi perilaku yang harus diuji saat modul diimplementasikan; belum dinyatakan lulus sebagai perilaku aplikasi.

Validasi dokumentasi di halaman ini tidak membuktikan perilaku server, ekstraksi PDF, penyimpanan, atau integrasi AI. Penerapan kode setelah audit diagram dicatat terpisah pada [implementasi jurnal](implementasi-jurnal.md). Tidak dilakukan analisis jurnal atau statistik nyata untuk validasi dokumentasi ini. Tidak ada klaim bahwa mutu akademik telah tersertifikasi atau bahwa seluruh modul rancangan sudah tersedia.
