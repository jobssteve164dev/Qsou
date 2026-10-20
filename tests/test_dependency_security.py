import io
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "crawler"))

from qsou_crawler.adapters.base import SourceAdapter


def test_pdf_extraction_preserves_announcement_text():
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }),
        }),
    })
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 720 Td (Quarterly revenue 42) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    output = io.BytesIO()
    writer.write(output)

    assert SourceAdapter._extract_pdf(output.getvalue()).strip() == "Quarterly revenue 42"


def test_pdf_page_labels_do_not_expand_untrusted_alphabetical_start_values():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.set_page_label(0, 0, style="/A", start=15_000)
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    assert PdfReader(output).page_labels == ["1"]


def test_twisted_imap_does_not_interpret_mailbox_names_as_regular_expressions():
    from twisted.mail.imap4 import wildcardToRegexp

    assert wildcardToRegexp("(a+)+z", "/").match("aaaaaaaaaaaaaaaz") is None
    assert wildcardToRegexp("inbox[1]+(draft)", "/").fullmatch("inbox[1]+(draft)")


def test_twisted_imap_preserves_wildcard_and_mailbox_delimiter_semantics():
    from twisted.mail.imap4 import wildcardToRegexp

    assert wildcardToRegexp("mail/*", "/").fullmatch("mail/team/2026")
    assert wildcardToRegexp("mail/%", "/").fullmatch("mail/team")
    assert wildcardToRegexp("mail/%", "/").fullmatch("mail/team/2026") is None
