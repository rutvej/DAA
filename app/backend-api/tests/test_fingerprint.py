try:
    from common.fingerprint import (
        compute_canonical_fingerprint,
        normalize_error_content,
    )
except ImportError:
    from app.common.fingerprint import (
        compute_canonical_fingerprint,
        normalize_error_content,
    )


def test_normalize_error_content():
    sample_trace = (
        "Traceback (most recent call last):\n"
        '  File "/app/main.py", line 42, in process\n'
        "    obj = MyClass(0x7f8b9c0d1e2f)\n"
        "RuntimeError: Failed at 2026-07-16T15:50:28Z"
    )
    normalized = normalize_error_content(sample_trace)
    assert "0x<HEX>" in normalized
    assert "0x7f8b9c0d1e2f" not in normalized
    assert "<TIMESTAMP>" in normalized
    assert "2026-07-16T15:50:28Z" not in normalized
    assert 'File "/app/main.py", line <LINE>' in normalized


def test_compute_canonical_fingerprint_deduplication():
    trace_a = 'File "/app/foo.py", line 10\nError at 0x111111 on 2026-07-16T10:00:00Z'
    trace_b = 'File "/app/foo.py", line 99\nError at 0x999999 on 2026-07-16T12:34:56Z'

    fp_a = compute_canonical_fingerprint("myapp", "ValueError", trace_a)
    fp_b = compute_canonical_fingerprint("myapp", "ValueError", trace_b)

    assert fp_a == fp_b
    assert len(fp_a) == 16
