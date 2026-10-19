"""Generate an explicitly synthetic, two-page acceptance PDF without extra dependencies."""
import argparse
from pathlib import Path

TEST_PAGES = [
    ['SYNTHETIC TEST DOCUMENT - NOT A REAL JOURNAL',
     'Purpose: Examine the relationship between study time and test scores.',
     'Method: Cross-sectional quantitative survey.',
     'Sample: 120 undergraduate volunteers from one university.'],
    ['SYNTHETIC TEST DOCUMENT - PAGE 2',
     'Findings: Study time was positively associated with test scores.',
     'This fixture intentionally contains no statement of limitations.'],
]


def make_pdf(pages):
    objects = [b'', b'', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    kids = []
    for lines in pages:
        page_id = len(objects) + 1
        stream_id = page_id + 1
        kids.append(f'{page_id} 0 R')
        escaped = [line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') for line in lines]
        stream = ('BT /F1 11 Tf 50 770 Td 18 TL\n' + '\nT*\n'.join(f'({line}) Tj' for line in escaped) + '\nET').encode('ascii')
        objects += [f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>'.encode(),
                    f'<< /Length {len(stream)} >>\nstream\n'.encode() + stream + b'\nendstream']
    objects[0] = b'<< /Type /Catalog /Pages 2 0 R >>'
    objects[1] = f'<< /Type /Pages /Count {len(pages)} /Kids [{" ".join(kids)}] >>'.encode()
    output = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output += f'{number} 0 obj\n'.encode() + obj + b'\nendobj\n'
    xref = len(output)
    output += f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
    for offset in offsets[1:]:
        output += f'{offset:010d} 00000 n \n'.encode()
    output += f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return bytes(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(make_pdf(TEST_PAGES))
    print(f'PDF uji sintetis dibuat: {args.output}')
