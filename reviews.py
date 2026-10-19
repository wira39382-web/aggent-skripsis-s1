"""Human reading notes, tied to an exact analysis and extraction. No academic approval."""
from analysis import FIELDS, extraction_version, validate_result


class ReviewConflict(ValueError):
    pass


def source_matches(record, document):
    result = record['result']
    return (document.get('source_integrity') == 'matched'
            and result.get('source_sha256') == document['sha256']
            and result.get('extraction_sha256') == extraction_version(document))


def review_state(record, document, current_id):
    if record['status'] != 'needs_review':
        return 'failed'
    if record['id'] != current_id:
        return 'superseded'
    if not source_matches(record, document):
        return 'stale'
    return record['reviews'][0]['status'] if record['reviews'] else 'needs_review'


def assess_review(document, record, payload):
    if not source_matches(record, document):
        raise ReviewConflict('Versi PDF/ekstraksi berbeda atau belum tercatat. Analisis ulang diperlukan.')
    if (payload.get('source_sha256') != document['sha256']
            or payload.get('extraction_sha256') != extraction_version(document)):
        raise ReviewConflict('Sumber berubah sejak formulir dibuka. Muat ulang dokumen.')
    fields = validate_result(record['result']['fields'], document['extraction']['pages'])
    reviewer, note = payload.get('reviewer'), payload.get('note')
    if not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 100:
        raise ValueError('Nama peninjau wajib diisi, maksimal 100 karakter.')
    if not isinstance(note, str) or not 1 <= len(note.strip()) <= 2000:
        raise ValueError('Catatan alasan tinjauan wajib diisi, maksimal 2.000 karakter.')
    decisions = payload.get('decisions')
    if not isinstance(decisions, dict) or set(decisions) != set(FIELDS):
        raise ValueError('Kelima bagian harus memiliki keputusan tinjauan.')
    for name in FIELDS:
        accepted = 'supported' if fields[name]['status'] == 'found' else 'not_found_in_readable_text'
        if decisions[name] not in (accepted, 'needs_revision', 'unknown'):
            raise ValueError('Keputusan tidak sesuai status bukti bagian ' + name + '.')
    if 'needs_revision' in decisions.values():
        status = 'needs_revision'
    elif 'unknown' in decisions.values():
        status = 'unknown'
    elif any(page['status'] != 'read' for page in document['extraction']['pages']):
        status = 'reviewed_partial'
    else:
        status = 'reviewed'
    return status, {'reviewer': reviewer.strip(), 'note': note.strip(), 'decisions': decisions,
                    'source_sha256': document['sha256'],
                    'extraction_sha256': extraction_version(document)}
