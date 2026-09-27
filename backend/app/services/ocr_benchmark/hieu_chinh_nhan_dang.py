"""E57b — hiệu chỉnh ngưỡng nhận dạng ngôn ngữ trên DỮ LIỆU CÓ NHÃN.

## Dữ liệu dùng, và nó KHÔNG nói được gì

Hai bộ đã có trong repo (`test_fixtures/external/`), tổng **65 crop có nhãn `language`**:

| Bộ | Số mẫu | Là gì |
|---|---|---|
| `ocr_benchmark` | 45 | 6 crop **manga thật** (Pepper&Carrot, CC-BY-SA-4.0) + 39 crop dựng với phông cách điệu, in hoa, nghiêng, SFX, xoay, và bản **làm nhiễu** |
| `ocr_benchmark_e20b` | 20 | Chữ mảnh / đậm trên **nền rối** |

**Cả 65 mẫu đều `language: en`.** Nên bộ này hiệu chỉnh được **một chiều**, và đó lại là chiều đáng lo
nhất: OCR đọc chữ Latin cách điệu rất dễ sinh ký tự rác, và nếu rác đó là chữ Hán thì trang tiếng Anh
bị lật thành tiếng Trung — sai mà trông tự tin.

Bộ này **không** nói được gì về ngưỡng kana (`SO_KANA_TOI_THIEU`) hay về chiều ja↔zh: repo không có
mẫu tiếng Nhật/Trung có nhãn, và `test_fixtures/external/mangaplus_private/` rỗng.

## Đơn vị đo phải là TRANG, không phải crop

Production chạy `doc_toan_anh()` trên **cả trang** rồi phân loại **một lần** cho toàn bộ chữ đọc
được. Đo theo từng crop sẽ cho một kết luận sai lệch: một bong bóng 5 ký tự luôn rơi vào
`qua_it_chu`, trong khi trên trang thật nó nằm cùng 20 bong bóng khác.

Nên script gom crop theo **bộ nguồn** thành "trang giả lập" rồi phân loại theo nhóm — đó là đơn vị
production thật sự dùng. Vẫn in cả số liệu từng crop, vì nó cho biết ngưỡng `SO_KY_TU_TOI_THIEU` chặn
những gì.

Chạy:

    ../.venv/bin/python -m app.services.ocr_benchmark.hieu_chinh_nhan_dang
"""
from __future__ import annotations

import collections
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

GOC = Path(__file__).resolve().parents[3] / "test_fixtures" / "external"

BO = (
    ("ocr_benchmark", GOC / "ocr_benchmark"),
    ("ocr_benchmark_e20b", GOC / "ocr_benchmark_e20b"),
)


@dataclass
class Mau:
    bo: str
    sample_id: str
    nhom: str
    language: str
    lettering_style: str
    rotation_bucket: str
    duong: Path
    ground_truth: str


def _doc_bo_cjk() -> list[Mau]:
    """Bộ `pepper_carrot_cjk` — **trang truyện THẬT**, đã dịch sang tiếng Nhật/Trung.

    Khác hai bộ kia ở một điểm quyết định: đây là **trang đầy đủ**, đúng thứ production nhận, chứ
    không phải crop từng bong bóng. Nên mỗi tệp tự nó là một "trang" và không cần gom nhóm.
    """
    thu_muc = GOC / "pepper_carrot_cjk"
    mf = thu_muc / "manifest.json"
    if not mf.exists():
        return []
    ds: list[Mau] = []
    for r in json.loads(mf.read_text(encoding="utf-8")):
        duong = thu_muc / r["tep"]
        if not duong.exists():
            continue
        ds.append(
            Mau(
                bo="pepper_carrot_cjk",
                sample_id=r["tep"].replace("_Pepper-and-Carrot_by-David-Revoy", ""),
                # Mỗi TRANG là một nhóm riêng: nó đã là đơn vị production dùng.
                nhom=f"{r['language']}__{r['tep']}",
                language=r["language"],
                lettering_style="comic_that",
                rotation_bucket="none",
                duong=duong,
                ground_truth="",
            )
        )
    return ds


def doc_manifest() -> list[Mau]:
    ds: list[Mau] = _doc_bo_cjk()
    for ten_bo, thu_muc in BO:
        mf = thu_muc / "manifest.jsonl"
        if not mf.exists():
            continue
        for dong in mf.read_text(encoding="utf-8").splitlines():
            if not dong.strip():
                continue
            r = json.loads(dong)
            duong = thu_muc / "crops" / r["crop_path"]
            if not duong.exists():
                duong = thu_muc / r["crop_path"]
            if not duong.exists():
                print(f"  BO QUA (khong thay tep): {r['sample_id']}", file=sys.stderr)
                continue
            ds.append(
                Mau(
                    bo=ten_bo,
                    sample_id=r["sample_id"],
                    nhom=r.get("source_category", "?"),
                    language=r["language"],
                    lettering_style=r.get("lettering_style", "?"),
                    rotation_bucket=r.get("rotation_bucket", "?"),
                    duong=duong,
                    ground_truth=r.get("ground_truth", ""),
                )
            )
    return ds


def main() -> int:
    from app.services.nhan_dang_ngon_ngu import (
        SO_KANA_TOI_THIEU,
        SO_KY_TU_TOI_THIEU,
        TI_LE_HAN_TOI_THIEU,
        TI_LE_LATIN_TOI_THIEU,
        dem_ky_tu,
        phan_loai,
    )
    from app.services.ocr.engines import PaddleOCREngine

    mau = doc_manifest()
    if not mau:
        print("Khong co mau nao — xem docstring module.")
        return 1
    print(f"{len(mau)} mau co nhan. Nhan: {dict(collections.Counter(m.language for m in mau))}")
    print(
        f"Nguong dang dung: ky_tu>={SO_KY_TU_TOI_THIEU} kana>={SO_KANA_TOI_THIEU} "
        f"han>={TI_LE_HAN_TOI_THIEU:.0%} latin>={TI_LE_LATIN_TOI_THIEU:.0%}"
    )
    print()

    engine = PaddleOCREngine(
        lang="ch",
        device=os.environ.get("OCR_DEVICE", "cpu"),
        enable_mkldnn=False,
    )

    # ── Đọc từng crop MỘT LẦN, cache lại: OCR là phần đắt, còn thử ngưỡng thì rẻ ──
    doc_duoc: dict[str, list[str]] = {}
    for i, m in enumerate(mau, 1):
        try:
            doc_duoc[m.sample_id] = engine.doc_toan_anh(str(m.duong))
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}/{len(mau)}] {m.sample_id}: OCR LOI {type(exc).__name__}: {exc}")
            doc_duoc[m.sample_id] = []
        if i % 10 == 0:
            print(f"  … da doc {i}/{len(mau)}")
    print()

    # ── Từng crop ──
    print("=== TUNG CROP (khong phai don vi production dung) ===")
    dem_crop: collections.Counter = collections.Counter()
    for m in mau:
        kq = phan_loai(doc_duoc[m.sample_id])
        ten = kq.ngon_ngu.value if kq.ngon_ngu else "khong-ket-luan"
        dem_crop[ten] += 1
    print("  ket luan:", dict(dem_crop))
    print(f"  (nhan that: tat ca la '{mau[0].language}')")

    sai_han = [
        m for m in mau
        if (k := phan_loai(doc_duoc[m.sample_id])).ngon_ngu is not None
        and k.ngon_ngu.value != m.language
    ]
    print(f"  SAI HAN (ket luan mot ngon ngu KHAC nhan): {len(sai_han)}")
    for m in sai_han:
        kq = phan_loai(doc_duoc[m.sample_id])
        print(
            f"    {m.sample_id:18s} nhan={m.language} -> {kq.ngon_ngu.value} ({kq.ly_do})"
            f" | {kq.bang_chung.nhu_dict()}"
        )
        print(f"      OCR doc ra: {doc_duoc[m.sample_id]!r}")
    print()

    # ── Theo TRANG giả lập (gom theo bộ nguồn) ──
    print("=== THEO TRANG GIA LAP (gom theo source_category — DON VI PRODUCTION DUNG) ===")
    nhom: dict[tuple[str, str], list[Mau]] = collections.defaultdict(list)
    for m in mau:
        nhom[(m.bo, m.nhom)].append(m)
    dung = sai = khong = 0
    for (bo, ten), ds in sorted(nhom.items()):
        chu: list[str] = []
        for m in ds:
            chu.extend(doc_duoc[m.sample_id])
        kq = phan_loai(chu)
        nhan = ds[0].language
        ra = kq.ngon_ngu.value if kq.ngon_ngu else "khong-ket-luan"
        dau = "OK " if ra == nhan else ("?? " if kq.ngon_ngu is None else "SAI")
        if ra == nhan:
            dung += 1
        elif kq.ngon_ngu is None:
            khong += 1
        else:
            sai += 1
        bc = kq.bang_chung
        print(
            f"  {dau} {bo}/{ten:32s} n={len(ds):2d} nhan={nhan} -> {ra:15s}"
            f" latin={bc.latin:4d} han={bc.han:3d} kana={bc.kana:3d} tong={bc.tong_co_nghia:4d}"
            f" ({kq.ly_do})"
        )
    print(f"\n  dung={dung} sai={sai} khong-ket-luan={khong}")
    print()

    # ── Quét ngưỡng: ngưỡng nào là biên thật? ──
    print("=== QUET NGUONG TI_LE_HAN (tren TRANG gia lap) ===")
    print("  Ti le Han do duoc o tung trang gia lap — biet bien that o dau:")
    for (bo, ten), ds in sorted(nhom.items()):
        chu = [t for m in ds for t in doc_duoc[m.sample_id]]
        bc = dem_ky_tu(chu)
        if bc.tong_co_nghia:
            print(
                f"    {bo}/{ten:32s} han/tong = {bc.han}/{bc.tong_co_nghia}"
                f" = {bc.han / bc.tong_co_nghia:.1%}"
            )
    print()
    print("=== DO DAI CHU DOC DUOC (de dat SO_KY_TU_TOI_THIEU) ===")
    dai_crop = sorted(dem_ky_tu(doc_duoc[m.sample_id]).tong_co_nghia for m in mau)
    print(f"  tung crop: min={dai_crop[0]} p25={dai_crop[len(dai_crop)//4]} "
          f"trung_vi={dai_crop[len(dai_crop)//2]} max={dai_crop[-1]}")
    print(f"  so crop duoi nguong {SO_KY_TU_TOI_THIEU}: "
          f"{sum(1 for d in dai_crop if d < SO_KY_TU_TOI_THIEU)}/{len(dai_crop)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
