from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw

from app_video_review_studio import nap_danh_sach_anh_va_thoai_tu_thu_muc
from core_tts_voice import tong_hop_giong_doc_phan_canh, uoc_tinh_thoi_luong_cau, xuat_phu_de_srt
from core_video_renderer import (
    ve_khung_hinh_pan_zoom_va_phu_de,
    xac_thuc_va_tru_luot_video_cloud,
    xuat_video_review_mp4,
)
from core_vision_character import (
    CharacterCastMemory,
    sinh_kich_ban_review_chuong,
    tach_khung_tranh_thong_minh,
    tao_luoi_storyboard_2x2,
)


def _tao_anh_webtoon_dai_co_ranh() -> bytes:
    """Tạo 1 trang Webtoon dài 600x2400 có 2 rãnh trắng phân cách rõ ràng."""
    im = Image.new("RGB", (600, 2400), (40, 60, 120))
    draw = ImageDraw.Draw(im)
    # Rãnh trắng số 1 tại y=760..820
    draw.rectangle([0, 760, 600, 820], fill=(255, 255, 255))
    # Rãnh trắng số 2 tại y=1580..1640
    draw.rectangle([0, 1580, 600, 1640], fill=(255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def test_1_character_cast_memory_persist_and_speaker_attribution():
    with tempfile.TemporaryDirectory() as tmp:
        bible_path = Path(tmp) / "character_bible.json"
        cast = CharacterCastMemory(bible_path)
        cast.them_hoac_cap_nhat(
            ten="Lâm Phong",
            vai_tro="Nam chính (Main)",
            ngoai_hinh="Tóc đen ngắn, mặc áo khoác đen, cầm đoản kiếm",
            xung_ho="thanh niên",
            tu_khoa_nhan_dien="kiếm khí, hệ thống",
        )
        cast.them_hoac_cap_nhat(
            ten="Triệu Hổ",
            vai_tro="Trùm Phản diện",
            ngoai_hinh="Đầu trọc, sẹo ngang mặt",
            xung_ho="tên trùm",
            tu_khoa_nhan_dien="phế vật, chết đi",
        )
        assert bible_path.is_file()

        # Nạp lại từ ổ đĩa để đảm bảo sang Chapter sau vẫn nhớ đúng nhân vật
        cast2 = CharacterCastMemory(bible_path)
        assert len(cast2.characters) == 2
        nv_phan_dien = cast2.doan_nhan_vat_theo_ngu_canh("Ngươi chỉ là tên phế vật, chết đi!", vi_tri_bong="phai")
        assert nv_phan_dien["ten"] == "Triệu Hổ"
        nv_main = cast2.doan_nhan_vat_theo_ngu_canh("Hệ thống của Lâm Phong đã kích hoạt!", vi_tri_bong="trai")
        assert nv_main["ten"] == "Lâm Phong"


def test_2_smart_webtoon_panel_cutter_and_2x2_storyboard_grid():
    raw_strip = _tao_anh_webtoon_dai_co_ranh()
    panels = tach_khung_tranh_thong_minh(raw_strip)
    assert len(panels) >= 3

    grid_bytes = tao_luoi_storyboard_2x2(panels[:4], kich_thuoc_o=(320, 420))
    with Image.open(io.BytesIO(grid_bytes)) as gim:
        assert gim.size == (640, 840)


def test_3_script_generator_handles_dialogue_and_silent_action_panels():
    raw_strip = _tao_anh_webtoon_dai_co_ranh()
    panels = tach_khung_tranh_thong_minh(raw_strip)
    cast = CharacterCastMemory()
    cast.them_hoac_cap_nhat("Lâm Phong", "Nam chính (Main)", "Tóc đen", "thanh niên")
    cast.them_hoac_cap_nhat("Triệu Hổ", "Phản diện", "Mặt sẹo", "gã đầu trọc")

    ocr_per_panel = [
        ["Hả?! Ngươi dám cản đường Triệu Hổ ta sao?"],
        [],  # Khung tranh hành động không lời (Silent Action Panel)
        ["Lâm Phong ta hôm nay sẽ cho ngươi biết tay!"],
    ]
    kb = sinh_kich_ban_review_chuong(
        panels[:3],
        ocr_per_panel,
        cast_memory=cast,
        phong_cach="hai_huoc",
        ten_truyen="Ta Là Chí Tôn",
        ten_chap="Chapter-001",
    )
    assert kb["so_khung_tranh"] == 3
    assert kb["so_luoi_storyboard_2x2"] == 1
    assert kb["scenes"][0]["nhan_vat"] == "Triệu Hổ"
    assert kb["scenes"][1]["la_canh_hanh_dong"] is True
    assert len(kb["scenes"][1]["loi_thuyet_minh"]) > 25
    assert kb["scenes"][2]["nhan_vat"] == "Lâm Phong"


def test_4_tts_audio_and_mp4_video_export_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        chap_dir = tmp_dir / "BoTruyenTest" / "Chapter-001"
        chap_dir.mkdir(parents=True)

        # Tạo 2 trang ảnh kèm _translation_ledger.json
        for i in (1, 2):
            im = Image.new("RGB", (600, 900), (30 * i, 50, 90))
            im.save(chap_dir / f"00{i}.jpg", format="JPEG")

        ledger = {
            "pages": [
                {
                    "output_name": "001.jpg",
                    "regions": [{"chu_goc": "Hello", "ban_dich": "Ngươi nghĩ có thể đánh bại ta sao?"}],
                },
                {
                    "output_name": "002.jpg",
                    "regions": [],  # Trang hành động không lời
                },
            ]
        }
        (chap_dir / "_translation_ledger.json").write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")

        panels, ocr_list = nap_danh_sach_anh_va_thoai_tu_thu_muc(chap_dir)
        assert len(panels) == 2
        assert ocr_list[0] == ["Ngươi nghĩ có thể đánh bại ta sao?"]

        kb = sinh_kich_ban_review_chuong(panels, ocr_list, phong_cach="kich_tinh", ten_truyen="BoTruyenTest", ten_chap="Chapter-001")
        out_mp4 = chap_dir / "Chapter-001_Review.mp4"
        kq = xuat_video_review_mp4(
            panels,
            kb,
            out_mp4,
            ma_dinh_dang="tiktok_9_16",
            ma_giong="nam_minh_kich_tinh",
            toc_do_doc=1.15,
            che_do_nhanh_offline=True,
        )
        assert kq["ok"] is True
        assert Path(kq["video_path"]).is_file()
        assert Path(kq["video_path"]).stat().st_size > 1000
        assert Path(kq["srt_path"]).is_file()
        assert "00:00:00,000 -->" in Path(kq["srt_path"]).read_text(encoding="utf-8")
        assert Path(kq["storyboard_json_path"]).is_file()


def test_5_cloud_wallet_ticket_deduction_for_video_studio(monkeypatch=None):
    import urllib.request

    calls = []

    def fake_urlopen(req, timeout=15):
        url = req.full_url
        calls.append(url)
        if url.endswith("/api/v1/han-muc"):
            body = json.dumps({"con_lai": 50, "la_quan_tri": False}).encode("utf-8")
        elif url.endswith("/api/v1/developer/consume-local-page"):
            body = json.dumps(
                {
                    "ok": True,
                    "execution_ticket": {"sig": "hmac_valid_sig", "credits": 2},
                }
            ).encode("utf-8")
        else:
            raise AssertionError(f"Unexpected URL: {url}")

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return body

        return _Resp()

    old_urlopen = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        kq_std = xac_thuc_va_tru_luot_video_cloud(
            "https://translation-api.vibe1.tinhgon.xyz",
            "tr_live_test_token_123",
            ma_goi="review_standard",
            ma_dinh_danh_video="chap1",
        )
        assert kq_std["ok"] is True
        assert kq_std["so_luot_da_tru"] == 10
        assert kq_std["con_lai_sau_tru"] == 40
        assert len(kq_std["tickets"]) == 5  # 5 * 2 lượt = 10 lượt
    finally:
        urllib.request.urlopen = old_urlopen


if __name__ == "__main__":
    test_1_character_cast_memory_persist_and_speaker_attribution()
    test_2_smart_webtoon_panel_cutter_and_2x2_storyboard_grid()
    test_3_script_generator_handles_dialogue_and_silent_action_panels()
    test_4_tts_audio_and_mp4_video_export_end_to_end()
    test_5_cloud_wallet_ticket_deduction_for_video_studio()
    print("ALL 5 VIDEO REVIEW STUDIO TESTS PASSED!")
