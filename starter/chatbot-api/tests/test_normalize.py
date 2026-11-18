from app.ingestion.normalize import extract_iso_dates, resolve_ds

AUDIENCE = {
    "Tất cả người học",
    "Thí sinh / người dự tuyển",
    "Sinh viên (mọi hệ)",
    "Sinh viên đại học chính quy",
    "Sinh viên văn bằng 2 / liên thông",
    "Sinh viên vừa làm vừa học",
    "Sinh viên liên kết quốc tế",
    "Sau đại học (cao học + nghiên cứu sinh)",
    "Học viên cao học",
    "Nghiên cứu sinh",
    "Cựu sinh viên",
    "Phụ huynh",
    "Doanh nghiệp / đối tác",
    "Giảng viên / cán bộ",
}


def test_composite_student_maps_to_all_systems() -> None:
    got, how = resolve_ds("Sinh viên đại học (chính quy, vừa làm vừa học, từ xa)", AUDIENCE)
    assert got == "Sinh viên (mọi hệ)"
    assert how == "mapped"


def test_exact_audience_stays_exact() -> None:
    got, how = resolve_ds("Sinh viên đại học chính quy", AUDIENCE)
    assert got == "Sinh viên đại học chính quy"
    assert how == "exact"


def test_dhcq_alias() -> None:
    got, how = resolve_ds("SV ĐHCQ", AUDIENCE)
    assert got == "Sinh viên đại học chính quy"
    assert how == "mapped"


def test_extract_skips_academic_year() -> None:
    assert extract_iso_dates("Lễ tốt nghiệp năm học 2026-2027") == []
    assert extract_iso_dates("Công bố kết quả ngày 15/06/2026.") == ["2026-06-15"]
    assert extract_iso_dates("từ 01/09/2026 đến 15/09/2026") == ["2026-09-01", "2026-09-15"]
