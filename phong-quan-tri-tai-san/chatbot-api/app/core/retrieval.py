"""Hằng số retrieve. P4 nhân cosine với retrieve_boost (FAQ cao hơn 03/04/05)."""

FAQ_SOURCE = "faq"
FAQ_RETRIEVE_BOOST = 1.5
DATE_HINTS = ("hạn", "lịch", "ngày", "khi nào", "deadline", "học kỳ", "deadline")
PROC_KINDS = frozenset({"step", "dossier", "procedure_meta"})
PROC_TYPES = frozenset({"procedure", "mixed"})
