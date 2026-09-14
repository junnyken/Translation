"""Dò chéo tài khoản cho id nằm trong THÂN REQUEST — lớp lỗ mà phép dò cũ KHÔNG với tới.

## Vì sao cần một phép dò RIÊNG

`test_quyen_cheo_tai_khoan.py` tự sinh phép thử từ `app.openapi()` và che rất tốt id trên **URL**:
nó đặt id của A lên đường dẫn rồi gọi bằng B, B phải không nhận 2xx.

Nhưng lỗ IDOR của id trong **thân request** có hình dạng KHÁC:

```
phép dò cũ :  B  ->  /projects/{id-của-A}/export      { }                   -> chặn ở URL
lỗ thật    :  B  ->  /projects/{id-của-B}/export      {"gop": [id-của-A]}   -> URL HỢP LỆ
```

URL hoàn toàn hợp lệ với B, nên phép kiểm ở URL đi qua sạch. Id lạ nằm trong body, và nếu handler
không tự kiểm từng id thì B tải được dữ liệu của A.

**Tôi đã thử vá phép dò cũ (điền id thật vào mảng uuid) và nó VẪN xanh khi bỏ phép kiểm quyền** —
vì nó luôn đặt id của A lên URL, tức B bị chặn trước khi body được nhìn tới. Cấu trúc của phép dò
đó không diễn đạt được lớp lỗ này, nên phải có phép dò riêng.

## Chống rỗng nghĩa

Mỗi endpoint bị gọi **hai lần** bằng B:

- body chứa id của **A** ⇒ phải **không** 2xx (nếu 2xx: LỖ HỔNG),
- body chứa id của **chính B** ⇒ phải **2xx** (nếu không: phép dò rỗng nghĩa — nó bị chặn vì lý
  do khác, không phải vì kiểm quyền, nên phép thử trên chẳng chứng minh gì).

Không có nhánh thứ hai thì một endpoint hỏng vì lý do bất kỳ cũng làm test này xanh.
"""
from __future__ import annotations

import uuid

import pytest

from app.main import app

pytestmark = pytest.mark.anyio

#: Tên trường mang id CHAPTER trong thân request. Dò theo tên vì OpenAPI không nói field này trỏ
#: tới bảng nào — đó là giới hạn của schema, không phải lựa chọn của tôi.
_TU_KHOA_PROJECT = ("project_id", "project_ids", "chapter_id", "chapter_ids")


def _truong_id_chapter(schema: dict, goc: dict, sau: int = 0) -> list[tuple[str, bool]]:
    """Trả `[(tên trường, có phải mảng)]` cho mọi trường mang id chapter trong schema."""
    if sau > 6 or not isinstance(schema, dict):
        return []
    if "$ref" in schema:
        ten = schema["$ref"].rsplit("/", 1)[-1]
        return _truong_id_chapter(goc["components"]["schemas"].get(ten, {}), goc, sau + 1)
    ra: list[tuple[str, bool]] = []
    for ten, con in (schema.get("properties") or {}).items():
        if not any(k in ten for k in _TU_KHOA_PROJECT):
            continue
        nhanh = con
        for khoa in ("anyOf", "oneOf", "allOf"):
            if khoa in con:
                nhanh = next(
                    (n for n in con[khoa] if n.get("type") != "null"), con[khoa][0]
                )
                break
        ra.append((ten, nhanh.get("type") == "array"))
    return ra


def _endpoint_nhan_id_chapter() -> list[tuple[str, str, str, bool]]:
    """`[(method, mẫu đường dẫn, tên trường, có phải mảng)]` — tự sinh từ OpenAPI."""
    goc = app.openapi()
    ra = []
    for duong, methods in goc["paths"].items():
        if not duong.startswith("/api/v1") or "{project_id}" not in duong:
            continue
        for method, tt in methods.items():
            if method.upper() not in ("POST", "PATCH", "PUT"):
                continue
            than = (tt.get("requestBody") or {}).get("content", {}).get("application/json", {})
            for ten, la_mang in _truong_id_chapter(than.get("schema", {}), goc):
                ra.append((method.upper(), duong, ten, la_mang))
    return ra


async def _tao_chapter(cl, ten: str) -> str:
    r = await cl.post("/api/v1/projects", json={
        "name": ten, "source_lang": "ja", "intended_use": "study"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _than_toi_thieu(method: str, mau: str, ten_truong: str, la_mang: bool, gia_tri: str) -> dict:
    """Thân request tối thiểu: chỉ trường bắt buộc + trường id đang dò."""
    goc = app.openapi()
    tt = goc["paths"][mau][method.lower()]
    than = (tt.get("requestBody") or {}).get("content", {}).get("application/json", {})
    schema = than.get("schema", {})
    if "$ref" in schema:
        schema = goc["components"]["schemas"].get(schema["$ref"].rsplit("/", 1)[-1], {})
    ra: dict = {}
    for ten, con in (schema.get("properties") or {}).items():
        if ten in (schema.get("required") or []):
            nhanh = con
            for khoa in ("anyOf", "oneOf", "allOf"):
                if khoa in con:
                    nhanh = next((n for n in con[khoa] if n.get("type") != "null"), con[khoa][0])
                    break
            # Enum của Pydantic ra `$ref` tới `components.schemas`, KHÔNG phải `enum` nội tuyến.
            # Không giải `$ref` thì `format` nhận chuỗi rác ⇒ 422 ⇒ phép dò rỗng nghĩa. Chính
            # phép chống-rỗng-nghĩa bên dưới đã bắt được ca này.
            if "$ref" in nhanh:
                nhanh = goc["components"]["schemas"].get(nhanh["$ref"].rsplit("/", 1)[-1], {})
            if "enum" in nhanh:
                ra[ten] = nhanh["enum"][0]
            elif nhanh.get("type") == "string":
                ra[ten] = f"x{uuid.uuid4().hex[:8]}"
            elif nhanh.get("type") == "integer":
                ra[ten] = 1
            elif nhanh.get("type") == "boolean":
                ra[ten] = True
    ra[ten_truong] = [gia_tri] if la_mang else gia_tri
    return ra


async def test_co_endpoint_nao_de_do_khong():
    """Chống rỗng nghĩa ở tầng cao nhất: không tìm ra endpoint nào thì test này vô nghĩa."""
    assert _endpoint_nhan_id_chapter(), (
        "không tìm thấy endpoint nào nhận id chapter trong thân request — "
        "phép dò dưới đây sẽ xanh mà chẳng kiểm gì"
    )


async def test_khong_endpoint_nao_nhan_id_chapter_LA_trong_than(client, client_b):
    """B dùng chapter CỦA MÌNH trên URL, nhét id của A vào thân ⇒ phải bị chặn."""
    cua_a = await _tao_chapter(client, "Chapter của A")
    cua_b = await _tao_chapter(client_b, "Chapter của B")

    lo_hong: list[str] = []
    chung_minh: list[str] = []
    rong_nghia: list[str] = []

    for method, mau, ten_truong, la_mang in _endpoint_nhan_id_chapter():
        duong = mau.replace("{project_id}", cua_b)
        nhan = f"{method} {mau} [{ten_truong}]"

        tra_la = await client_b.request(
            method, duong, json=_than_toi_thieu(method, mau, ten_truong, la_mang, cua_a)
        )
        tra_minh = await client_b.request(
            method, duong, json=_than_toi_thieu(method, mau, ten_truong, la_mang, cua_b)
        )

        if 200 <= tra_la.status_code < 300:
            lo_hong.append(f"{nhan}: id của A trong thân ⇒ HTTP {tra_la.status_code}")
        elif 200 <= tra_minh.status_code < 300:
            # Id lạ bị chặn VÀ id của chính mình đi qua ⇒ chứng minh được là kiểm quyền.
            chung_minh.append(nhan)
        else:
            rong_nghia.append(
                f"{nhan}: cả hai đều không 2xx (lạ={tra_la.status_code} "
                f"mình={tra_minh.status_code}) — không kết luận gì"
            )

    assert not lo_hong, "LỖ HỔNG id trong thân request:\n" + "\n".join(lo_hong)
    assert chung_minh, (
        "không chứng minh được endpoint nào có kiểm quyền id-trong-thân — "
        f"rỗng nghĩa: {rong_nghia}"
    )
