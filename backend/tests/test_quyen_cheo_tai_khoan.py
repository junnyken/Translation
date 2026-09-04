"""Dò chéo tài khoản trên TOÀN BỘ bảng route (Auth slice B).

## Vì sao phải có test này thay vì đọc code

Slice B gắn kiểm quyền ở 61/65 endpoint. Đọc từng cái rồi tự tin là không sót là đúng cái
kiểu tin tưởng đã làm hỏng chuyện nhiều lần trong dự án này. Test này **tự sinh** phép thử từ
`app.openapi()`, nên endpoint thêm về sau cũng bị dò mà không ai phải nhớ cập nhật gì.

## Điều quan trọng nhất: phép dò rỗng nghĩa

Một cái bẫy hiển nhiên: nếu id gửi lên không tồn tại thì B nhận 404, test xanh, mà chẳng chứng
minh được gì. Nên mỗi đường dẫn được gọi **hai lần** — một lần bằng A (chủ thật) và một lần
bằng B — rồi phân loại:

- A 2xx, B không 2xx  ⇒ **chứng minh được** có kiểm quyền.
- B 2xx               ⇒ **LỖ HỔNG**, test đỏ.
- A cũng không 2xx    ⇒ **rỗng nghĩa**, không kết luận gì; test in ra danh sách này để người
  đọc biết đúng phần nào đã được chứng minh, chứ không cho nó lẫn vào phần xanh.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.main import app
from app.models import (
    BatchItem,
    BatchRun,
    CharacterVoiceProfile,
    ConsistencyReviewTask,
    ExportJob,
    GlossaryEntry,
    Job,
    OCRResult,
    Page,
    Project,
    RegionQualityAssessment,
    RegionSafeArea,
    RegionTextOrientation,
    TermSuggestionRun,
    TextRegion,
    TranslationResult,
    TypesetResult,
)
from app.models.enums import (
    BatchPipeline,
    ConfidenceState,
    TranslationState,
    ConsistencyTaskType,
    ExportFormat,
    GlossaryStatus,
    JobType,
    OrientationStatus,
    RegionRelevance,
    SafeAreaStatus,
    SafeAreaSource,
    SafeAreaGeometryType,
    OrientationSource,
    SourceLang,
    TargetLang,
    TermType,
    TextOrientation,
    IntendedUse,
    JobStatus,
)

pytestmark = pytest.mark.anyio


async def _dung_du_lieu(session, chu_so_huu_id: uuid.UUID) -> dict[str, str]:
    """Dựng một chapter đầy đủ thuộc về `chu_so_huu_id`, trả bảng tra id theo tên tham số."""
    project = Project(
        name="chapter cua A",
        source_lang=SourceLang.ja,
        target_lang=TargetLang.vi,
        intended_use=IntendedUse.personal,
        chu_so_huu_id=chu_so_huu_id,
    )
    session.add(project)
    await session.flush()

    page = Page(project_id=project.id, image_path="a/1.png", order=1)
    session.add(page)
    await session.flush()

    region = TextRegion(page_id=page.id, bbox_x=10, bbox_y=10, bbox_w=100, bbox_h=50)
    session.add(region)
    await session.flush()

    job = Job(type=JobType.detect, page_id=page.id)
    export_job = ExportJob(project_id=project.id, format=ExportFormat.cbz)
    batch = BatchRun(project_id=project.id, requested_pipeline=BatchPipeline.full_pipeline)
    glossary = GlossaryEntry(
        project_id=project.id, source_lang=SourceLang.ja, target_lang=TargetLang.vi,
        source_term="ナルト", source_term_key="ナルト", target_term="Naruto",
        term_type=TermType.character_name, definition="ten nhan vat",
        status=GlossaryStatus.approved,
    )
    voice = CharacterVoiceProfile(
        project_id=project.id, character_name="Naruto", character_name_key="naruto"
    )
    run = TermSuggestionRun(project_id=project.id, series_name="Naruto")
    session.add_all([job, export_job, batch, glossary, voice, run])
    await session.flush()

    session.add_all([
        BatchItem(batch_run_id=batch.id, page_id=page.id, page_order=1),
        ConsistencyReviewTask(
            project_id=project.id, region_id=region.id,
            task_type=ConsistencyTaskType.glossary_missing, snapshot_hash="x" * 16,
        ),
        OCRResult(region_id=region.id),
        TranslationResult(region_id=region.id),
        TypesetResult(region_id=region.id),
        RegionSafeArea(
            region_id=region.id, algorithm_version="v1", source=SafeAreaSource.shape_derived,
            status=SafeAreaStatus.ready, roi_x=0, roi_y=0, roi_w=10, roi_h=10,
            geometry_type=SafeAreaGeometryType.rect, geometry_json=[],
        ),
        RegionTextOrientation(
            region_id=region.id, algorithm_version="v1",
            orientation=TextOrientation.horizontal_ltr, source=OrientationSource.image_heuristic,
            status=OrientationStatus.ready,
        ),
        RegionQualityAssessment(
            region_id=region.id, assessment_version="v1",
            relevance=RegionRelevance.likely_translatable,
            detector_confidence_state=ConfidenceState.available,
            ocr_confidence_state=ConfidenceState.available,
            translation_state=TranslationState.present,
        ),
    ])
    await session.commit()

    # Hiện vật THẬT trên kho: không có chúng thì A cũng nhận 404 và phép dò không kết luận
    # được gì về chính ba đường phục vụ file — đúng chỗ đáng lo nhất về rò rỉ dữ liệu.
    from app.services.storage import get_storage
    from app.services.typeset.paths import preview_relative_path

    kho = get_storage()
    anh = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    duong_clean = f"{project.id}/{page.id}/clean.png"
    kho.save(duong_clean, anh)
    page.clean_image_path = duong_clean
    kho.save(preview_relative_path(page.id), anh)

    duong_xuat = f"{project.id}/export/{export_job.id}.cbz"
    kho.save(duong_xuat, b"PK\x03\x04" + b"0" * 64)
    export_job.status = JobStatus.done
    export_job.output_path = duong_xuat
    await session.commit()

    task = (await session.execute(
        text("SELECT id FROM consistency_review_task LIMIT 1")
    )).scalar()
    return {
        "project_id": str(project.id),
        "page_id": str(page.id),
        "region_id": str(region.id),
        "job_id": str(job.id),
        "export_job_id": str(export_job.id),
        "batch_run_id": str(batch.id),
        "entry_id": str(glossary.id),
        "profile_id": str(voice.id),
        "run_id": str(run.id),
        "task_id": str(task),
    }


def _duong_dan_that(mau: str, ids: dict[str, str]) -> str | None:
    """Thay `{ten}` bằng id thật. Thiếu một tham số ⇒ None (bỏ qua, và báo ra)."""
    ket = mau
    while "{" in ket:
        dau = ket.index("{"); cuoi = ket.index("}", dau)
        ten = ket[dau + 1:cuoi]
        # `/export-jobs/{job_id}` và `/jobs/{job_id}` dùng chung tên nhưng khác bảng.
        khoa = "export_job_id" if (ten == "job_id" and "export-job" in mau) else ten
        if khoa not in ids:
            return None
        ket = ket[:dau] + ids[khoa] + ket[cuoi + 1:]
    return ket


#: Endpoint KHÔNG gắn với tài nguyên của ai — dò chéo ở đây vô nghĩa.
#: Danh sách này phải ngắn và mỗi mục phải giải thích được, nếu không nó thành chỗ giấu lỗ hổng.
MIEN_TRU = {
    "/api/v1/projects": "tạo chapter mới / liệt kê chapter CỦA MÌNH — không nhận id của ai",
    "/api/v1/batch-config": "hằng số cấu hình, không có dữ liệu người dùng",
    "/api/v1/health": "trạng thái hệ thống",
    "/api/v1/auth/login": "chưa đăng nhập thì mới gọi",
    "/api/v1/auth/logout": "chỉ thu hồi phiên của chính người gọi",
    "/api/v1/auth/me": "trả về chính người gọi",
    "/api/v1/auth/register": "tự gác bằng khoá chung",
    "/api/v1/auth/co-tai-khoan-chua": "chỉ trả true/false",
    # Quản trị người dùng KHÔNG gắn với chapter nào nên dò chéo chủ sở hữu ở đây vô nghĩa.
    # Nhưng chúng có cổng riêng (chỉ quản trị) và được kiểm ở `test_quan_tri_nguoi_dung.py` —
    # miễn trừ ở đây KHÔNG có nghĩa là không kiểm.
    "/api/v1/auth/users": "danh bạ tài khoản, không thuộc chapter nào; kiểm ở test_quan_tri_nguoi_dung",
    "/api/v1/auth/users/{nguoi_id}": "khoá/xoá tài khoản; kiểm ở test_quan_tri_nguoi_dung",
}


def _gia_tri_mau(schema: dict, goc: dict, ids: dict[str, str], sau: int = 0):
    """Sinh một giá trị hợp khuôn từ schema OpenAPI. Không cần đúng nghiệp vụ, chỉ cần **qua
    được tầng kiểm khuôn của FastAPI** — vì trước khi qua được đó thì kiểm quyền chưa chạy."""
    if sau > 6 or not isinstance(schema, dict):
        return None
    if "$ref" in schema:
        ten = schema["$ref"].rsplit("/", 1)[-1]
        return _gia_tri_mau(goc["components"]["schemas"].get(ten, {}), goc, ids, sau + 1)
    for khoa in ("anyOf", "oneOf", "allOf"):
        if khoa in schema:
            for nhanh in schema[khoa]:
                if nhanh.get("type") != "null":
                    return _gia_tri_mau(nhanh, goc, ids, sau + 1)
    if "const" in schema:
        # `Literal["rules"]` của Pydantic ra `const` chứ không phải `enum`. Không hiểu nó thì
        # gửi `null` và bị 422 trước khi chạm tới kiểm quyền.
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    kieu = schema.get("type")
    if kieu == "object":
        thuoc_tinh = schema.get("properties", {})
        bat_buoc = schema.get("required", [])
        # Không có trường nào bắt buộc ⇒ thân rỗng ⇒ handler từ chối "không có gì để sửa" và
        # phép dò lại rỗng nghĩa. Điền hết trường tuỳ chọn để chạm được tới thân hàm.
        chon = bat_buoc or list(thuoc_tinh)
        return {
            ten: _gia_tri_mau(con, goc, ids, sau + 1)
            for ten, con in thuoc_tinh.items()
            if ten in chon
        }
    if kieu == "array":
        return []
    if kieu == "integer":
        return 1
    if kieu == "number":
        return 1.0
    if kieu == "boolean":
        return True
    if kieu == "string":
        if schema.get("format") == "uuid":
            return ids["region_id"]
        if schema.get("format") == "date-time":
            return datetime.now(timezone.utc).isoformat()
        # Chuỗi phải DUY NHẤT: dùng chung một giá trị thì lần POST tạo bản ghi rồi lần PATCH
        # sau đó đụng ràng buộc duy nhất, và phép dò hỏng vì lý do chẳng liên quan tới quyền.
        return f"x{uuid.uuid4().hex[:8]}"
    return None


def _than_request(method: str, mau: str, ids: dict[str, str]):
    """Thân request tối thiểu hợp khuôn cho một endpoint, hoặc `{}` nếu nó không nhận thân."""
    goc = app.openapi()
    thong_tin = goc["paths"][mau][method.lower()]
    than = thong_tin.get("requestBody", {}).get("content", {}).get("application/json", {})
    if not than:
        return {}
    return _gia_tri_mau(than.get("schema", {}), goc, ids) or {}


def _duong_dan_can_do() -> list[tuple[str, str]]:
    ket = []
    for duong, cac_method in app.openapi()["paths"].items():
        if duong in MIEN_TRU or not duong.startswith("/api/v1"):
            continue
        for method in cac_method:
            if method.upper() in ("GET", "POST", "PATCH", "PUT", "DELETE"):
                ket.append((method.upper(), duong))
    return ket


async def test_khong_endpoint_nao_lo_du_lieu_sang_tai_khoan_khac(
    session, client, client_b, nguoi_a
):
    """B không được nhận 2xx ở bất kỳ đường dẫn nào trỏ vào dữ liệu của A."""
    ids = await _dung_du_lieu(session, uuid.UUID(nguoi_a[0]))

    lo_hong: list[str] = []
    chung_minh: list[str] = []
    rong_nghia: list[str] = []
    khong_dung_duoc: list[str] = []

    for method, mau in _duong_dan_can_do():
        duong = _duong_dan_that(mau, ids)
        if duong is None:
            khong_dung_duoc.append(f"{method} {mau}")
            continue
        if mau.endswith("/pages") and method == "POST":
            # Endpoint duy nhất nhận multipart. Gửi JSON vào đây thì cả A lẫn B đều 422 và
            # phép dò rỗng nghĩa — mà đây lại là đường GHI dữ liệu vào chapter người khác.
            tep = {"file": ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")}
            tra_a = await client.post(duong, files=tep)
            tra_b = await client_b.post(duong, files=tep)
        else:
            than = _than_request(method, mau, ids)
            tra_a = await client.request(method, duong, json=than)
            tra_b = await client_b.request(method, duong, json=than)
        # Đặt lại chủ sở hữu sau MỖI lượt. Không có dòng này, chỉ cần một endpoint đổi
        # quyền sở hữu (`/release` nhả chapter, `/claim` nhận chapter) là mọi lượt kiểm phía
        # sau mất hết ý nghĩa — và tệ hơn, chúng sẽ hiện ra như một loạt "lỗ hổng" giả.
        #
        # Đo được thật: thêm `/release` xong, phép dò tụt từ 63 chứng minh được xuống 4, kèm
        # 18 "lỗ hổng" mà thực ra là B truy cập một chapter đã bị chính phép dò nhả ra.
        await session.execute(
            text("UPDATE project SET chu_so_huu_id = :u WHERE id = :p"),
            {"u": uuid.UUID(nguoi_a[0]), "p": uuid.UUID(ids["project_id"])},
        )
        await session.commit()

        nhan = f"{method} {mau} (A {tra_a.status_code} / B {tra_b.status_code})"
        if 200 <= tra_b.status_code < 300:
            lo_hong.append(f"{method} {mau} → B nhận {tra_b.status_code}")
        elif 200 <= tra_a.status_code < 300:
            chung_minh.append(nhan)
        elif tra_b.status_code == 404 and tra_a.status_code != 404:
            # A vào tới thân hàm rồi hỏng vì lý do nghiệp vụ (409/422), B bị chặn từ 404.
            # Hai kết quả KHÁC nhau chính là bằng chứng cổng quyền đã chặn B.
            chung_minh.append(nhan + " [A vào tới thân hàm, B bị chặn]")
        else:
            rong_nghia.append(nhan)

    print(
        f"\n[dò chéo] chứng minh được: {len(chung_minh)}"
        f" | rỗng nghĩa (A cũng không 2xx): {len(rong_nghia)}"
        f" | không dựng được đường dẫn: {len(khong_dung_duoc)}"
    )
    for d in rong_nghia:
        print(f"  rỗng nghĩa: {d}")
    for d in khong_dung_duoc:
        print(f"  không dựng được: {d}")

    assert not lo_hong, "Endpoint để lọt dữ liệu sang tài khoản khác:\n" + "\n".join(lo_hong)
    # Không cho phép phép dò rỗng nghĩa. Một endpoint mà A cũng không vào được thì test này
    # xanh mà chẳng chứng minh gì — đúng kiểu "xanh giả" nguy hiểm hơn cả đỏ.
    #
    # Thêm endpoint mới mà phép dò không chạm tới được ⇒ test đỏ, và người thêm phải chọn:
    # dựng thêm dữ liệu cho nó, hoặc ghi vào MIEN_TRU KÈM LÝ DO.
    assert not rong_nghia, (
        "Phép dò không kết luận được gì ở các endpoint sau (A cũng không vào được nên không "
        "so sánh được với B):\n" + "\n".join(rong_nghia)
    )
    assert not khong_dung_duoc, (
        "Không dựng được đường dẫn thật cho:\n" + "\n".join(khong_dung_duoc)
    )


async def test_moi_endpoint_deu_doi_dang_nhap(session, client_chua_dang_nhap, client, nguoi_a):
    """Không đăng nhập ⇒ 401 ở mọi đường dẫn, trừ danh sách miễn trừ có giải thích."""
    ids = await _dung_du_lieu(session, uuid.UUID(nguoi_a[0]))
    lot: list[str] = []
    for method, mau in _duong_dan_can_do():
        duong = _duong_dan_that(mau, ids)
        if duong is None:
            continue
        tra = await client_chua_dang_nhap.request(method, duong, json={})
        if tra.status_code != 401:
            lot.append(f"{method} {mau} → {tra.status_code}")
    assert not lot, "Endpoint không đòi đăng nhập:\n" + "\n".join(lot)


async def test_chapter_chua_co_chu_thi_ai_dang_nhap_cung_thay(session, client, client_b):
    """Chapter tạo TRƯỚC slice B (`chu_so_huu_id IS NULL`) không được biến mất khỏi tầm nhìn."""
    project = Project(
        name="chapter cu khong co chu",
        source_lang=SourceLang.ja, target_lang=TargetLang.vi,
        intended_use=IntendedUse.personal, chu_so_huu_id=None,
    )
    session.add(project)
    await session.commit()

    for c in (client, client_b):
        tra = await c.get(f"/api/v1/projects/{project.id}")
        assert tra.status_code == 200, tra.text
        ds = await c.get("/api/v1/projects")
        assert str(project.id) in [p["id"] for p in ds.json()]


async def test_nhan_chapter_vo_chu_roi_thi_nguoi_khac_mat_quyen(session, client, client_b):
    """Nhận chapter vô chủ về mình ⇒ người khác không còn thấy nữa."""
    project = Project(
        name="chapter vo chu", source_lang=SourceLang.ja, target_lang=TargetLang.vi,
        intended_use=IntendedUse.personal, chu_so_huu_id=None,
    )
    session.add(project)
    await session.commit()

    nhan = await client.post(f"/api/v1/projects/{project.id}/claim")
    assert nhan.status_code == 200, nhan.text

    assert (await client.get(f"/api/v1/projects/{project.id}")).status_code == 200
    assert (await client_b.get(f"/api/v1/projects/{project.id}")).status_code == 404
    # Và không ai cướp lại được.
    assert (await client_b.post(f"/api/v1/projects/{project.id}/claim")).status_code == 404


async def test_chapter_tao_moi_luon_co_chu(session, client, client_b):
    """Từ slice B trở đi không còn đường nào sinh ra chapter vô chủ."""
    tra = await client.post("/api/v1/projects", json={
        "name": "moi", "source_lang": "ja", "target_lang": "vi", "intended_use": "personal",
    })
    assert tra.status_code == 201, tra.text
    assert tra.json()["chu_so_huu_id"] is not None
    assert (await client_b.get(f"/api/v1/projects/{tra.json()['id']}")).status_code == 404
