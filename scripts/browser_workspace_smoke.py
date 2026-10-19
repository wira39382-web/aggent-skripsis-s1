"""Visible dashboard/proposal smoke test; synthetic inputs and mocked provider only."""
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
from app import ProjectStore, make_handler
from scripts.make_test_pdf import make_pdf
from test_proposals import PROPOSAL_PAGES, audit_fixture


def main():
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': '', 'OPENAI_API_KEY': ''}):
        store = ProjectStore(Path(tmp) / 'projects.sqlite3')
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(store))
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 1050}, timezone_id='Asia/Jakarta')
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.route('**/api/health', lambda route: route.fulfill(json={'status': 'ok', 'version': '0.2.0'}))
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    expect(page.locator('#message')).to_contain_text('Versi halaman dan server berbeda')
                    page.unroute('**/api/health')
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    expect(page.locator('#app-version')).to_contain_text('v0.3.0')
                    title = 'PROYEK UJI SINTETIS: pengaruh persepsi kegunaan dan kepercayaan terhadap niat penggunaan layanan pembayaran digital pada mahasiswa'
                    page.get_by_label('Judul atau topik sementara').fill(title)
                    page.get_by_role('button', name='+ Buat proyek').click()
                    expect(page.locator('#next-title')).to_have_text('Belum ada proposal')
                    page.locator('#nav-proposal').click()
                    page.get_by_label('Pilih PDF').set_input_files({'name': 'proposal-uji-sintetis.pdf', 'mimeType': 'application/pdf', 'buffer': make_pdf(PROPOSAL_PAGES)})
                    page.get_by_role('button', name='Unggah & baca PDF').click()
                    expect(page.get_by_role('heading', name='proposal-uji-sintetis.pdf', exact=True)).to_be_visible()
                    expect(page.locator('#proposal-ai-audit')).to_be_disabled()
                    page.get_by_role('button', name='Periksa struktur tanpa AI').click()
                    expect(page.locator('#proposal-progress')).to_contain_text('Pemeriksaan struktur tersimpan')
                    expect(page.locator('.outline-row')).to_have_count(3)
                    page.locator('#manual-finding > summary').click()
                    page.locator('#finding-criterion').select_option('keselarasan')
                    page.get_by_label('Temuan dan akibatnya').fill('Catatan uji sintetis: pertanyaan perlu diperjelas.')
                    page.get_by_label('Tindak lanjut yang dapat diperiksa').fill('Rinci pertanyaan serta hubungan dengan tujuan.')
                    page.get_by_label('Nama pencatat', exact=True).fill('<script>peninjau uji</script>')
                    page.get_by_label('Kutipan persis dari proposal').fill(PROPOSAL_PAGES[0][3])
                    page.get_by_role('button', name='Simpan temuan manual').click()
                    expect(page.locator('#nav-issue-count')).to_have_text('1')
                    page.locator('#nav-revisions').click()
                    expect(page.locator('.issue-card')).to_have_count(1)
                    form = page.locator('.issue-card form')
                    form.locator('select').select_option('in_progress')
                    form.get_by_label('Nama pencatat', exact=True).fill('Peninjau lokal uji')
                    form.get_by_label('Catatan tindakan atau alasan perubahan').fill('Sedang merinci pertanyaan pada fixture.')
                    form.get_by_role('button', name='Simpan tindak lanjut').click()
                    expect(page.locator('.issue-meta')).to_contain_text('Sedang dikerjakan')
                    page.reload()
                    page.locator('#nav-revisions').click()
                    expect(page.locator('.issue-meta')).to_contain_text('Sedang dikerjakan')
                    form = page.locator('.issue-card form')
                    form.locator('select').select_option('addressed')
                    form.get_by_label('Nama pencatat', exact=True).fill('Peninjau lokal uji')
                    form.get_by_label('Catatan tindakan atau alasan perubahan').fill('Perubahan fixture dicatat, belum diverifikasi.')
                    form.get_by_role('button', name='Simpan tindak lanjut').click()
                    expect(page.locator('#nav-issue-count')).to_have_text('0')
                    page.locator('#nav-proposal').click()
                    page.get_by_label('Pilih PDF').set_input_files({'name': 'proposal-uji-revisi.pdf', 'mimeType': 'application/pdf', 'buffer': make_pdf(PROPOSAL_PAGES)})
                    page.get_by_role('button', name='Unggah & baca PDF').click()
                    expect(page.get_by_role('heading', name='proposal-uji-revisi.pdf', exact=True)).to_be_visible()
                    page.locator('#nav-revisions').click()
                    expect(page.locator('.issue-card')).to_have_count(0)
                    page.get_by_label('Tampilkan riwayat versi lama').check()
                    expect(page.locator('.issue-card')).to_have_count(1)
                    expect(page.locator('.issue-card form')).to_have_count(0)
                    expect(page.locator('.event-list')).to_contain_text('<script>peninjau uji</script>')
                    expect(page.locator('script:not([src])')).to_have_count(0)
                    def provider(key, model, system, inputs, *args):
                        return audit_fixture(inputs['untrusted_documents'][0]['document_id']), 'MOCK-AUDITOR-NOT-REAL', {}
                    with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'MOCK-KEY-ONLY'}), patch('proposal.request_structured', side_effect=provider):
                        page.reload()
                        page.locator('#start-proposal').click()
                        page.get_by_label('Saya mengizinkan teks proposal').check()
                        page.get_by_role('button', name='Audit substantif dengan AI').click()
                        expect(page.locator('#proposal-checks')).to_contain_text('MOCK-AUDITOR-NOT-REAL')
                        expect(page.locator('.check-card')).to_have_count(10)
                        expect(page.locator('#nav-issue-count')).to_have_text('1')
                        page.locator('#nav-dashboard').click()
                        expect(page.locator('#next-title')).to_have_text('Ada revisi yang perlu ditindaklanjuti')
                        for width in (1440, 390):
                            page.set_viewport_size({'width': width, 'height': 1050})
                            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                        page.set_viewport_size({'width': 1440, 'height': 1050})
                        page.screenshot(path='/tmp/skripsi-dashboard-v030.png', full_page=True)
                        page.locator('#start-proposal').click()
                        expect(page.locator('#structure-audit')).to_be_enabled()
                        expect(page.locator('#proposal-checks')).to_contain_text('MOCK-AUDITOR-NOT-REAL')
                        page.locator('#proposal-panel').scroll_into_view_if_needed()
                        page.screenshot(path='/tmp/skripsi-proposal-v030.png')
                    assert not errors, errors
                    print('PASS dashboard/proposal Chromium: offline structure, evidence-bound manual finding, issue events/reload, version history, mock AI audit, long titles and mobile layout.')
                finally:
                    browser.close()
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == '__main__':
    main()
