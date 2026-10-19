"""Bounded PDF extraction in a separate process. No OCR or embedded code execution."""
import json
import subprocess
import sys
from pathlib import Path

MAX_PAGES = 100
MAX_TEXT = 1_000_000


def extract_pdf(path):
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode:
            raise ValueError('PDF tidak dapat dibaca atau melewati batas sumber daya.')
        data = json.loads(result.stdout)
        if 'error' in data:
            raise ValueError(data['error'])
        return data
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        raise ValueError('Pembacaan PDF gagal atau melewati batas 30 detik.') from error


def worker(path):
    # Linux resource limits complement wall-clock, byte, page, and text limits.
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    except ImportError:  # Windows still has the parent process timeout.
        pass
    from pypdf import PdfReader
    try:
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted:
            raise ValueError('PDF terenkripsi tidak didukung. Unggah salinan tanpa kata sandi.')
        if not 1 <= len(reader.pages) <= MAX_PAGES:
            raise ValueError(f'PDF harus berisi 1–{MAX_PAGES} halaman.')
        pages, total = [], 0
        for number, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ''
                total += len(text)
                if total > MAX_TEXT:
                    raise OverflowError
                status = 'read' if text.strip() else 'needs_ocr'
                message = None if text.strip() else 'Tidak ada teks terbaca; mungkin hasil pindai. OCR belum tersedia.'
            except OverflowError:
                raise ValueError('Teks PDF melewati batas 1 juta karakter.')
            except Exception:
                text, status, message = '', 'failed', 'Ekstraksi halaman gagal; periksa PDF asli.'
            pages.append({'pdf_page': number, 'printed_page': None, 'text': text,
                          'status': status, 'message': message})
        readable = sum(p['status'] == 'read' for p in pages)
        status = 'ready' if readable == len(pages) else ('partial' if readable else 'unreadable')
        return {'status': status, 'pages': pages}
    except ValueError:
        raise
    except Exception as error:
        raise ValueError('PDF rusak atau formatnya tidak didukung.') from error


if __name__ == '__main__':
    try:
        output = worker(sys.argv[1])
    except Exception as error:
        output = {'error': str(error)}
    print(json.dumps(output, ensure_ascii=False))
