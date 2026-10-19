"""Render the documentation graphs from one definition (requires Graphviz, not app runtime)."""
import json
from pathlib import Path
import re
import subprocess
import textwrap
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / 'docs' / 'revisi6'


def diagram(name, title, nodes, edges):
    return {'name': name, 'title': title,
            'nodes': {key: {'kind': kind, 'label': label} for key, kind, label in nodes},
            'edges': edges, 'entry': nodes[0][0], 'count': len(nodes)}


DIAGRAMS = [
    diagram('01-kendali', '01 · Kendali proyek berbasis bukti dan dependensi', [
        ('START', 'work', 'Inventaris ide, proposal, dokumen, data, hasil dan keputusan'),
        ('RULES', 'work', 'Petakan aturan, kewenangan, capability dan tujuan saat ini'),
        ('QUEUE', 'work', 'Susun tugas menurut dependensi; gunakan ulang versi yang masih sah'),
        ('NEXT', 'gate', 'Ada tugas siap dan diperlukan?'),
        ('TASK', 'work', 'Pilih satu tugas: literatur, proposal, data, analisis atau naskah'),
        ('WORK', 'work', 'Kerjakan pada snapshot input; catat sumber, proses dan biaya'),
        ('CHECK', 'gate', 'Hasil audit lokal?'),
        ('SAVE', 'work', 'Simpan versi dan bukti; tandai turunan terdampak usang'),
        ('READY', 'gate', 'Tujuan paket saat ini siap ditinjau?'),
        ('PACK', 'work', 'Ekspor dan keputusan per fase — diagram 04'),
        ('DONE', 'end', 'Paket dan status aktual tersimpan; bukan persetujuan otomatis'),
        ('ISSUE', 'work', 'Catat isu stabil, akar masalah dan kriteria selesai'),
        ('BUDGET', 'gate', 'Upaya otomatis masih beralasan dan dalam budget?'),
        ('TARGET', 'work', 'Pilih satu target terdampak; jangan reset riwayat isu'),
        ('DIAG', 'work', 'Diagnosis teknis; kegagalan alat bukan temuan penelitian'),
        ('HOLD', 'hold', 'Jeda tugas terkait; lanjutkan tugas independen yang siap'),
        ('ESC', 'hold', 'Minta keputusan atau budget baru; simpan state'),
    ], [
        ('START', 'RULES', ''), ('RULES', 'QUEUE', ''), ('QUEUE', 'NEXT', ''),
        ('NEXT', 'TASK', 'Ada'), ('NEXT', 'READY', 'Tidak ada tugas tersisa'),
        ('NEXT', 'HOLD', 'Tugas tersisa tetapi prasyarat terblokir'),
        ('TASK', 'WORK', ''), ('WORK', 'CHECK', ''),
        ('CHECK', 'SAVE', 'Memadai / tidak relevan beralasan'),
        ('CHECK', 'ISSUE', 'Perlu revisi'), ('CHECK', 'DIAG', 'Alat gagal'),
        ('CHECK', 'HOLD', 'Belum dapat dinilai'), ('DIAG', 'ISSUE', ''),
        ('SAVE', 'READY', ''), ('READY', 'PACK', 'Ya: gerbang scope terpenuhi'),
        ('READY', 'QUEUE', 'Belum: tugas baru yang dapat dikerjakan teridentifikasi'),
        ('READY', 'HOLD', 'Belum: syarat/bukti yang diperlukan belum jelas'), ('PACK', 'DONE', ''),
        ('ISSUE', 'BUDGET', ''), ('BUDGET', 'TARGET', 'Ya, ada diagnosis/perubahan berarti'),
        ('BUDGET', 'ESC', 'Tidak / perlu keputusan manusia'), ('TARGET', 'QUEUE', ''),
        ('HOLD', 'QUEUE', 'Tugas independen siap atau prasyarat berubah'),
        ('ESC', 'QUEUE', 'Keputusan dan budget baru tercatat'),
    ]),
    diagram('02-proposal', '02 · Proposal: audit serentak, perbaikan terarah', [
        ('INPUT', 'work', 'Masukan yang tersedia dan versi: ide, literatur atau proposal'),
        ('ENOUGH', 'gate', 'Bahan minimum untuk tugas ini dapat dinilai?'),
        ('INTENT', 'work', 'Ringkas maksud, cakupan, ketidakpastian dan keputusan lama'),
        ('CONFIRM', 'gate', 'Pengguna mengonfirmasi maksud substantif?'),
        ('FORK', 'join', 'Audit pada snapshot yang sama; AND split'),
        ('A1', 'work', 'Aturan, struktur dan sumber ketentuan'),
        ('A2', 'work', 'Masalah, gap dan keselarasan tujuan'),
        ('A3', 'work', 'Literatur, konteks dan dukungan klaim'),
        ('A4', 'work', 'Desain, sampel, pengukuran dan analisis'),
        ('A5', 'work', 'Etik, izin, privasi dan kelayakan'),
        ('JOIN', 'gate', 'Semua audit relevan selesai pada versi yang sama?'),
        ('FIND', 'work', 'Gabungkan status, bukti, isu penghambat dan dependensi'),
        ('CORE', 'gate', 'Perlu keputusan arah inti?'),
        ('OPTIONS', 'work', 'Tawarkan opsi, konsekuensi dan aktor yang perlu memutuskan'),
        ('DECISION', 'gate', 'Keputusan substantif tersedia dan tercatat?'),
        ('FIX', 'work', 'Perbaiki hanya target terdampak; Bab I–III mengikuti dependensi'),
        ('FEASIBLE', 'work', 'Periksa bukti dan uji relevan; dry run tidak menjadi hasil nyata'),
        ('LOCAL', 'gate', 'Gerbang target memadai?'),
        ('CROSS', 'work', 'Periksa matriks lintas bab dan sanggahan berbukti'),
        ('FINAL', 'gate', 'Semua gerbang wajib mutakhir; tanpa isu penghambat?'),
        ('EXPLAIN', 'work', 'Jelaskan alasan, bukti, alternatif dan batas dengan sumber'),
        ('UNDERSTAND', 'gate', 'Keputusan utama dipahami?'),
        ('HELP', 'work', 'Bimbing area belum dipahami; latihan dalam budget'),
        ('READY', 'end', 'Proposal siap ditinjau — lanjut diagram 04'),
        ('RETRY', 'end', 'Isu kembali ke kendali budget dan target — diagram 01'),
        ('WAIT', 'hold', 'Minta bahan/keputusan yang kurang; tahan hanya tugas terkait'),
    ], [
        ('INPUT', 'ENOUGH', ''), ('ENOUGH', 'INTENT', 'Ya'), ('ENOUGH', 'WAIT', 'Belum'),
        ('INTENT', 'CONFIRM', ''), ('CONFIRM', 'FORK', 'Sesuai'),
        ('CONFIRM', 'WAIT', 'Belum sesuai / belum dijawab'),
        ('FORK', 'A1', ''), ('FORK', 'A2', ''), ('FORK', 'A3', ''),
        ('FORK', 'A4', ''), ('FORK', 'A5', ''),
        ('A1', 'JOIN', ''), ('A2', 'JOIN', ''), ('A3', 'JOIN', ''),
        ('A4', 'JOIN', ''), ('A5', 'JOIN', ''),
        ('JOIN', 'FIND', 'Ya: status lengkap, bukan otomatis lolos'),
        ('JOIN', 'WAIT', 'Belum / versi berubah'),
        ('FIND', 'CORE', ''), ('CORE', 'OPTIONS', 'Ya'), ('CORE', 'FIX', 'Tidak'),
        ('OPTIONS', 'DECISION', ''), ('DECISION', 'INPUT', 'Ada: perbarui arah dan versi'),
        ('DECISION', 'WAIT', 'Belum'), ('FIX', 'FEASIBLE', 'Lewati keluaran yang tetap sah'),
        ('FEASIBLE', 'LOCAL', ''), ('LOCAL', 'CROSS', 'Memadai'),
        ('LOCAL', 'RETRY', 'Perlu revisi'), ('LOCAL', 'WAIT', 'Belum dapat dinilai'),
        ('CROSS', 'FINAL', ''), ('FINAL', 'EXPLAIN', 'Ya'), ('FINAL', 'RETRY', 'Tidak'),
        ('EXPLAIN', 'UNDERSTAND', ''), ('UNDERSTAND', 'READY', 'Ya: bukan tes hafalan'),
        ('UNDERSTAND', 'HELP', 'Sebagian: budget tersedia'), ('UNDERSTAND', 'RETRY', 'Budget habis / isu substantif'),
        ('HELP', 'EXPLAIN', 'Setelah penjelasan bermakna'), ('WAIT', 'INPUT', 'Masukan/prasyarat berubah'),
    ]),
    diagram('03-pelaksanaan', '03 · Pelaksanaan: izin, rencana, data dan hasil yang sah', [
        ('START', 'work', 'Inventaris data, instrumen, hasil eksternal dan keterpaparan hasil'),
        ('EXIST', 'gate', 'Data untuk tujuan ini sudah tersedia?'),
        ('ORIGIN', 'work', 'Audit asal, akses, persetujuan dan mutu data lama'),
        ('GO', 'gate', 'Data layak digunakan untuk tujuan ini?'),
        ('INSTR', 'work', 'Susun instrumen dan protokol sesuai rancangan'),
        ('PNEED', 'gate', 'Uji coba diperlukan?'),
        ('PPERM', 'gate', 'Persetujuan uji coba yang diwajibkan tersedia?'),
        ('PILOT', 'work', 'Uji coba nyata dan evaluasi instrumen sesuai protokol'),
        ('GI', 'gate', 'Instrumen layak; alasan dan bukti cukup?'),
        ('PLAN', 'work', 'Versikan rencana; catat asumsi dan keterpaparan hasil; jangan mundurkan tanggal'),
        ('NEED', 'gate', 'Perlu pengumpulan data baru/tambahan?'),
        ('PERMIT', 'gate', 'Syarat kegiatan dan aturan penghentian terpenuhi?'),
        ('COLLECT', 'work', 'Kumpulkan data nyata; simpan asal dan bukti prosedur'),
        ('CLEAN', 'work', 'Raw tetap; audit buku kode, missing dan transformasi menjadi versi baru'),
        ('GC', 'gate', 'Data siap untuk analisis yang dipilih?'),
        ('MODE', 'gate', 'Sumber perhitungan yang digunakan?'),
        ('ENGINE', 'gate', 'Modul metode didukung dan lulus benchmark relevan?'),
        ('RUN', 'work', 'Eksekusi; rekam versi, estimator, parameter dan diagnostik'),
        ('IMPORT', 'work', 'Impor hasil eksternal; audit perangkat, pengaturan dan provenance'),
        ('GA', 'gate', 'Perhitungan dan interpretasi memadai untuk klaim?'),
        ('WRITE', 'end', 'Hasil sah; tulis naskah berbukti lalu paket akhir — diagram 04'),
        ('HANDOFF', 'hold', 'Handoff metode; jangan mengganti rancangan demi alat'),
        ('WAIT', 'hold', 'Tahan kegiatan terkait; minta bukti/izin/keputusan yang tepat'),
        ('RETRY', 'end', 'Isu ke diagram 01; amandemen tercatat dan turunan usang'),
    ], [
        ('START', 'EXIST', ''), ('EXIST', 'ORIGIN', 'Ya'), ('EXIST', 'INSTR', 'Belum'),
        ('ORIGIN', 'GO', ''), ('GO', 'PLAN', 'Ya'), ('GO', 'WAIT', 'Belum / tidak layak'),
        ('INSTR', 'PNEED', ''), ('PNEED', 'PPERM', 'Ya'),
        ('PNEED', 'GI', 'Tidak relevan dengan alasan'), ('PNEED', 'WAIT', 'Belum diketahui'),
        ('PPERM', 'PILOT', 'Ya / tidak diwajibkan dengan dasar'), ('PPERM', 'WAIT', 'Belum'),
        ('PILOT', 'GI', ''), ('GI', 'PLAN', 'Ya'), ('GI', 'RETRY', 'Perlu revisi'),
        ('GI', 'WAIT', 'Bukti kurang'), ('PLAN', 'NEED', ''),
        ('NEED', 'PERMIT', 'Ya: alasan ilmiah tercatat'), ('NEED', 'CLEAN', 'Tidak'),
        ('PERMIT', 'COLLECT', 'Ya'), ('PERMIT', 'WAIT', 'Belum'), ('COLLECT', 'CLEAN', ''),
        ('CLEAN', 'GC', ''), ('GC', 'MODE', 'Ya'), ('GC', 'RETRY', 'Perlu revisi'),
        ('GC', 'WAIT', 'Belum dapat dinilai'), ('MODE', 'ENGINE', 'Dihitung oleh modul aplikasi'),
        ('MODE', 'IMPORT', 'Keluaran eksternal yang tersedia'),
        ('ENGINE', 'RUN', 'Ya'), ('ENGINE', 'HANDOFF', 'Tidak / alat belum tersedia'),
        ('HANDOFF', 'WAIT', ''), ('RUN', 'GA', ''), ('IMPORT', 'GA', ''),
        ('GA', 'WRITE', 'Memadai: hasil tidak signifikan boleh sah'),
        ('GA', 'RETRY', 'Kesalahan / penanganan perlu revisi'), ('GA', 'WAIT', 'Bukti/capability kurang'),
        ('WAIT', 'START', 'Prasyarat berubah; gunakan ulang keluaran sah'),
    ]),
    diagram('04-tinjauan', '04 · Tinjauan dan keputusan: proposal berbeda dari pengesahan akhir', [
        ('TYPE', 'gate', 'Jenis paket yang dituju?'),
        ('PG', 'gate', 'Proposal: gerbang internal dan versi sudah memadai?'),
        ('PE', 'work', 'Ekspor proposal dengan manifest versi'),
        ('PV', 'gate', 'Tampilan dan kelengkapan proposal benar?'),
        ('PR', 'gate', 'Tinjauan proposal tersedia dan mengizinkan langkah berikut?'),
        ('PS', 'gate', 'Seminar proposal diwajibkan menurut aturan terverifikasi?'),
        ('PSE', 'work', 'Seminar proposal; catat keputusan aktual dan versinya'),
        ('PD', 'gate', 'Keputusan proposal untuk versi ini?'),
        ('PA', 'end', 'Milestone proposal disetujui; cek izin kegiatan secara terpisah'),
        ('PW', 'hold', 'Menunggu aturan/keputusan proposal; latihan boleh berjalan'),
        ('PRESUME', 'gate', 'Checkpoint proposal yang tertunda menurut isu?'),
        ('FG', 'gate', 'Akhir: gerbang internal dan versi sudah memadai?'),
        ('FE', 'work', 'Ekspor naskah dan paket reproduksi sesuai akses'),
        ('FV', 'gate', 'Tampilan dan kelengkapan paket akhir benar?'),
        ('FR', 'gate', 'Tinjauan akhir tersedia dan syarat sidang terpenuhi?'),
        ('EXAM', 'work', 'Sidang akhir; catat bukti keputusan penguji'),
        ('FD', 'gate', 'Keputusan sidang akhir?'),
        ('FIX', 'work', 'Selesaikan revisi akhir; pertahankan versi dan isu'),
        ('VER', 'gate', 'Revisi diterima pihak berwenang untuk versi ini?'),
        ('FINAL', 'gate', 'Seluruh syarat final dan bukti pengesahan versi cocok?'),
        ('ARCHIVE', 'end', 'Arsip versi final disetujui beserta bukti dan paket reproduksi'),
        ('FW', 'hold', 'Menunggu bukti/keputusan akhir; jangan mengarang pengesahan'),
        ('FRESUME', 'gate', 'Checkpoint akhir yang tertunda menurut isu?'),
        ('RETRY', 'end', 'Catat isu; kembali ke satu target lewat diagram 01'),
        ('DRAFT', 'end', 'Boleh ekspor draf berlabel belum lolos jika akses sah'),
    ], [
        ('TYPE', 'PG', 'Proposal'), ('TYPE', 'FG', 'Skripsi akhir'),
        ('PG', 'PE', 'Ya'), ('PG', 'DRAFT', 'Belum'),
        ('PE', 'PV', ''), ('PV', 'PR', 'Ya'), ('PV', 'RETRY', 'Tidak'),
        ('PR', 'PS', 'Ya'), ('PR', 'RETRY', 'Perlu revisi'), ('PR', 'PW', 'Belum diketahui/tersedia'),
        ('PS', 'PSE', 'Ya'), ('PS', 'PD', 'Tidak: ada dasar aturan'), ('PS', 'PW', 'Aturan belum jelas'),
        ('PSE', 'PD', ''), ('PD', 'PA', 'Disetujui sesuai bukti'),
        ('PD', 'RETRY', 'Revisi / belum disetujui'), ('PD', 'PW', 'Keputusan belum tersedia'),
        ('PW', 'PRESUME', 'Aturan/keputusan baru tercatat'),
        ('PRESUME', 'PR', 'Tinjauan pembimbing'), ('PRESUME', 'PS', 'Aturan seminar'),
        ('PRESUME', 'PD', 'Keputusan proposal yang sudah diproses'),
        ('FG', 'FE', 'Ya'), ('FG', 'DRAFT', 'Belum'),
        ('FE', 'FV', ''), ('FV', 'FR', 'Ya'), ('FV', 'RETRY', 'Tidak'),
        ('FR', 'EXAM', 'Ya, sesuai aturan'), ('FR', 'RETRY', 'Perlu revisi'), ('FR', 'FW', 'Belum'),
        ('EXAM', 'FD', ''), ('FD', 'FINAL', 'Lulus tanpa revisi yang diwajibkan'),
        ('FD', 'FIX', 'Lulus dengan revisi'), ('FD', 'RETRY', 'Belum lulus / perbaikan substantif'),
        ('FD', 'FW', 'Bukti keputusan belum ada'), ('FIX', 'VER', ''),
        ('VER', 'FINAL', 'Ya'), ('VER', 'RETRY', 'Belum memadai'), ('VER', 'FW', 'Belum dinilai'),
        ('FINAL', 'ARCHIVE', 'Ya'), ('FINAL', 'FW', 'Syarat/bukti belum lengkap'),
        ('FW', 'FRESUME', 'Bukti baru; jangan ulang kegiatan yang sudah sah'),
        ('FRESUME', 'FR', 'Syarat sebelum sidang'), ('FRESUME', 'FD', 'Keputusan sidang yang sudah terjadi'),
        ('FRESUME', 'VER', 'Verifikasi revisi akhir'), ('FRESUME', 'FINAL', 'Kelengkapan pengesahan'),
    ]),
]


def validate(graph):
    nodes, edges = graph['nodes'], graph['edges']
    assert len(nodes) == graph['count'], 'Duplicate node IDs'
    outgoing = {key: [] for key in nodes}
    for source, target, label in edges:
        assert source in nodes and target in nodes, (source, target)
        outgoing[source].append((target, label))
    reached, queue = set(), [graph['entry']]
    while queue:
        key = queue.pop()
        if key in reached:
            continue
        reached.add(key)
        queue.extend(target for target, _ in outgoing[key])
    assert reached == set(nodes), 'Unreachable nodes: ' + str(set(nodes) - reached)
    for key, node in nodes.items():
        assert re.fullmatch('[A-Z][A-Z0-9_]*', key)
        if node['kind'] == 'end':
            assert not outgoing[key], key
        else:
            assert outgoing[key], 'Dead end without explicit status: ' + key
        if node['kind'] == 'gate':
            assert len(outgoing[key]) >= 2, key
            labels = [label for _, label in outgoing[key]]
            assert all(labels) and len(labels) == len(set(labels)), key
    # Every node has a structural route to an explicit terminal, not just a cycle.
    can_finish = {key for key, node in nodes.items() if node['kind'] == 'end'}
    while True:
        expanded = can_finish | {source for source, target, _ in edges if target in can_finish}
        if expanded == can_finish:
            break
        can_finish = expanded
    assert can_finish == set(nodes), 'Nodes trapped in a closed loop'


def quoted(text):
    return json.dumps(text, ensure_ascii=False)


def render(graph):
    validate(graph)
    stem = ROOT / graph['name']
    dot = ['digraph workflow {',
           'graph [rankdir=TB, bgcolor="#fcfcf8", pad=0.4, nodesep=0.3, ranksep=0.52, splines=polyline, fontname="DejaVu Sans", fontsize=19, labelloc=t, label=' + quoted(graph['title']) + '];',
           'node [shape=box, style="rounded,filled", fillcolor="#edf4ed", color="#6c8977", fontcolor="#193b33", fontname="DejaVu Sans", fontsize=11, margin="0.16,0.12"];',
           'edge [color="#89968e", fontname="DejaVu Sans", fontsize=9, fontcolor="#47574e", arrowsize=0.65];']
    mmd = ['%% Revisi 6 — dihasilkan dari scripts/render_workflow_v6.py',
           '%% Kontrak wajib: docs/revisi6/spesifikasi.md; panah silang memakai checkpoint dan versi.',
           'flowchart TD']
    for key, node in graph['nodes'].items():
        label = '\n'.join(textwrap.wrap(node['label'], width=30, break_long_words=False))
        style = ''
        if node['kind'] == 'gate':
            style = ', shape=diamond, fillcolor="#fcf0d8", color="#b29355"'
            shape = ('{', '}')
        elif node['kind'] == 'hold':
            style = ', fillcolor="#fae9e4", color="#b67c6c"'
            shape = ('[', ']')
        elif node['kind'] == 'end':
            style = ', shape=box, fillcolor="#e4edf9", color="#728caa", peripheries=2'
            shape = ('([', '])')
        elif node['kind'] == 'join':
            style = ', fillcolor="#e9e3f4", color="#9381ac"'
            shape = ('[', ']')
        else:
            shape = ('[', ']')
        dot.append(f'  {key} [label={quoted(label)}{style}];')
        safe_label = node['label'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        mmd.append(f'    {key}{shape[0]}{quoted(safe_label)}{shape[1]}')
        mmd.append(f'    class {key} ' + ('terminal' if node['kind'] == 'end' else node['kind']))
    for source, target, label in graph['edges']:
        dot.append(f'  {source} -> {target}' + (f' [label={quoted(label)}]' if label else '') + ';')
        mmd.append(f'    {source} -->' + (f'|"{label}"|' if label else '') + f' {target}')
    dot.append('}')
    mmd.extend([
        '    classDef work fill:#edf4ed,stroke:#6c8977,color:#193b33',
        '    classDef gate fill:#fcf0d8,stroke:#b29355,color:#193b33',
        '    classDef hold fill:#fae9e4,stroke:#b67c6c,color:#193b33',
        '    classDef terminal fill:#e4edf9,stroke:#728caa,color:#193b33',
        '    classDef join fill:#e9e3f4,stroke:#9381ac,color:#193b33',
    ])
    stem.with_suffix('.dot').write_text('\n'.join(dot) + '\n')
    stem.with_suffix('.mmd').write_text('\n'.join(mmd) + '\n')
    subprocess.run(['dot', '-Tsvg', str(stem.with_suffix('.dot')), '-o', str(stem.with_suffix('.svg'))], check=True)
    svg = ET.parse(stem.with_suffix('.svg')).getroot()
    ns = {'s': 'http://www.w3.org/2000/svg'}
    actual = {g.find('s:title', ns).text for g in svg.findall('.//s:g', ns) if g.get('class') == 'node'}
    assert actual == set(graph['nodes']), 'Rendered nodes differ from source'
    print(f'{graph["name"]}: {len(graph["nodes"])} nodes, {len(graph["edges"])} edges; SVG verified')


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    for graph in DIAGRAMS:
        render(graph)
