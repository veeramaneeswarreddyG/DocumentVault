"""Utility script to generate a sample valid PDF file for persistence testing.
"""
import hashlib
import sys
from pathlib import Path

SAMPLE_PDF_TEMPLATE = (
    b"%PDF-1.4\n"
    b"1 0 obj\n"
    b"<< /Type /Catalog /Pages 2 0 R >>\n"
    b"endobj\n"
    b"2 0 obj\n"
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
    b"endobj\n"
    b"3 0 obj\n"
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\n"
    b"endobj\n"
    b"4 0 obj\n"
    b"<< /Length 56 >>\n"
    b"stream\n"
    b"BT /F1 18 Tf 70 700 Td (Document Vault Persistent Test Document) Tj ET\n"
    b"endstream\n"
    b"endobj\n"
    b"xref\n"
    b"0 5\n"
    b"0000000000 65535 f \n"
    b"0000000010 00000 n \n"
    b"0000000060 00000 n \n"
    b"0000000117 00000 n \n"
    b"0000000202 00000 n \n"
    b"trailer\n"
    b"<< /Size 5 /Root 1 0 R >>\n"
    b"startxref\n"
    b"308\n"
    b"%%EOF\n"
)

def create_sample_pdf(output_path: str = "sample_document.pdf"):
    out_file = Path(output_path)
    out_file.write_bytes(SAMPLE_PDF_TEMPLATE)
    sha256 = hashlib.sha256(SAMPLE_PDF_TEMPLATE).hexdigest()
    print(f"Created valid PDF at: {out_file.resolve()}")
    print(f"File Size: {len(SAMPLE_PDF_TEMPLATE)} bytes")
    print(f"SHA-256 Checksum: {sha256}")
    return sha256

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sample_document.pdf"
    create_sample_pdf(target)
