"""Optional Chromium smoke test. Uses synthetic PDF and mocked AI, never a real API key."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))

from playwright.sync_api import expect, sync_playwright
from app import make_handler, ProjectStore
from scripts.make_test_pdf import make_pdf, TEST_PAGES
from test_documents import valid_result


def main():
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'mock-test-only'}), patch(
        'analysis.request_model', return_value=(valid_result(), 'MOCK-TEST-NOT-REAL-AI', {})
    ):
        store = ProjectStore(Path(tmp) / 'projects.sqlite3')
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(store))
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                try:
                    page = browser.new_page(viewport={'width': 1360, 'height': 1000})
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    title = '<img src=x onerror=alert(1)>'
                    page.get_by_label('Judul atau topik sementara').fill(title)
                    page.get_by_role('button', name='+ Buat proyek').click()
                    page.get_by_label('Tambahkan PDF jurnal').set_input_files({
                        'name': 'synthetic.pdf', 'mimeType': 'application/pdf', 'buffer': make_pdf(TEST_PAGES)})
                    page.get_by_role('button', name='Unggah & baca PDF').click()
                    page.get_by_role('heading', name='synthetic.pdf', exact=True).wait_for()
                    page.get_by_label('Saya mengizinkan teks jurnal').check()
                    page.get_by_role('button', name='Analisis jurnal', exact=True).click()
                    expect(page.locator('#analysis-results')).to_contain_text('MOCK-TEST-NOT-REAL-AI')
                    expect(page.locator('.analysis-card')).to_have_count(5)
                    expect(page.locator('.analysis-card').last).to_contain_text('Tidak ditemukan')
                    page.get_by_role('button', name='Lihat bukti · halaman PDF 2').click()
                    expect(page.locator('#page')).to_have_value('2')
                    expect(page.locator('mark')).to_contain_text('positively associated')
                    expect(page.locator('img')).to_have_count(0)
                    page.get_by_label('Nama peninjau (catatan lokal)').fill('<script>reviewer</script>')
                    for key in ['tujuan', 'metode', 'sampel', 'temuan']:
                        page.locator('#review-'+key).select_option('supported')
                    page.locator('#review-keterbatasan').select_option('not_found_in_readable_text')
                    page.locator('#review-temuan').select_option('needs_revision')
                    page.get_by_label('Alasan dan batas tinjauan').fill('Fixture uji: interpretasi temuan perlu diperiksa.')
                    page.get_by_role('button', name='Simpan catatan tinjauan').click()
                    expect(page.locator('.review-panel .notice')).to_have_text('Perlu revisi')
                    page.locator('#review-temuan').select_option('supported')
                    page.get_by_label('Alasan dan batas tinjauan').fill('Fixture uji: seluruh klaim cocok dengan konteks sumber sintetis.')
                    page.get_by_role('button', name='Simpan catatan tinjauan').click()
                    expect(page.locator('.review-panel .notice')).to_have_text('Tinjauan tercatat pada teks terbaca')
                    page.reload()
                    page.get_by_role('button', name=title, exact=True).click()
                    page.get_by_role('button', name='synthetic.pdf', exact=False).click()
                    expect(page.locator('#analysis-results')).to_contain_text('MOCK-TEST-NOT-REAL-AI')
                    expect(page.locator('.review-panel .notice')).to_have_text('Tinjauan tercatat pada teks terbaca')
                    expect(page.locator('#history')).to_contain_text('<script>reviewer</script>')
                    expect(page.locator('script:not([src])')).to_have_count(0)
                    page.get_by_label('Saya mengizinkan teks jurnal').check()
                    page.get_by_role('button', name='Analisis jurnal', exact=True).click()
                    expect(page.locator('.review-panel .notice')).to_have_text('Belum ditinjau')
                    expect(page.locator('#reviewer')).to_have_value('')
                    document = store.documents(store.list()[0]['id'])[0]
                    original = store.pdf_path(document['id'])
                    original.write_bytes(original.read_bytes().replace(b'Purpose:', b'Changed:', 1))
                    page.reload()
                    page.get_by_role('button', name=title, exact=True).click()
                    page.get_by_role('button', name='synthetic.pdf', exact=False).click()
                    expect(page.locator('.review-panel .notice')).to_have_text('Versi sumber belum cocok; analisis ulang')
                    expect(page.locator('#human-review-form')).to_have_count(0)
                    expect(page.locator('#original')).to_be_hidden()
                    page.get_by_label('Saya mengizinkan teks jurnal').check()
                    expect(page.get_by_role('button', name='Analisis jurnal', exact=True)).to_be_disabled()
                    for width in (1360, 390):
                        page.set_viewport_size({'width': width, 'height': 900})
                        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                    assert not errors, errors
                    print('PASS Chromium: PDF workflow, review/revision, persistent history, source integrity and stale guards, safe rendering and responsive layout.')
                    print('AI provider was mocked; no real research analysis was performed.')
                finally:
                    browser.close()
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == '__main__':
    main()
