"""Versioned request identity; pure stdlib, no DB/provider or deployment defaults.

A key binds the submitted choices, not future server defaults. Replays return the
original page even if deployment/model defaults change later.
"""
import hashlib
import json


def upload_fingerprint(data, *, source_lang, target_lang, engine, che_do, font_style,
                       tu_dien_rieng, tao_chapter_rieng):
    payload = {"version": 1, "image_sha256": hashlib.sha256(data).hexdigest(),
               "source_lang": source_lang, "target_lang": target_lang, "engine": engine,
               "che_do": che_do, "font_style": font_style or "", "tu_dien_rieng": tu_dien_rieng or "",
               "tao_chapter_rieng": bool(tao_chapter_rieng)}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def upload_lock_id(owner_id, request_key):
    # Signed bigint accepted by PostgreSQL. Namespace avoids other advisory locks.
    digest = hashlib.sha256(f"translation-upload-v1:{owner_id}:{request_key}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)
