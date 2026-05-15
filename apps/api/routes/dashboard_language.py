from __future__ import annotations

LANGUAGE_COOKIE = "imoex_lang"
SUPPORTED_LANGUAGES = {"ru", "en"}


def resolve_language(request) -> str:
    candidate = (
        request.query_params.get("lang")
        or request.cookies.get(LANGUAGE_COOKIE)
        or "ru"
    )
    candidate = candidate.lower().strip()
    return candidate if candidate in SUPPORTED_LANGUAGES else "ru"
