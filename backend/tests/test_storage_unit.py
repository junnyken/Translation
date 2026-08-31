"""Lớp lưu trữ hiện vật (P3d + P3e).

Bộ test này chạy **cùng một hợp đồng trên CẢ HAI backend** (`local` và `postgres`) qua fixture
`kho` được parametrize. Đó là điểm mấu chốt: nếu chỉ test riêng từng lớp thì "thay backend được"
mãi mãi là một lời hứa. Chạy chung một bộ khẳng định mới là bằng chứng.

Những gì trước P3d KHÔNG có test nào:
  1. chặn path thoát khỏi gốc kho (`_abs()` cũ ghép thẳng `root / rel`, không kiểm gì);
  2. ghi nguyên tử — không để lại tệp ghi dở khi lỗi giữa chừng.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import ArtifactBlob
from app.services.storage import (
    ArtifactTooLarge,
    LocalObjectStorage,
    PostgresObjectStorage,
    UnsafeObjectPath,
    chuan_hoa_path,
    workspace,
)


def _kho_postgres(max_bytes: int = 0) -> PostgresObjectStorage:
    with sync_session() as s:
        s.execute(sa.delete(ArtifactBlob))
        s.commit()
    return PostgresObjectStorage(max_bytes=max_bytes)


@pytest.fixture(params=["local", "postgres"])
def kho(request, tmp_path):
    """CÙNG hợp đồng, hai hiện thực. Test nào dùng fixture này là test nào chạy hai lượt."""
    if request.param == "local":
        return LocalObjectStorage(str(tmp_path / "kho"))
    return _kho_postgres()


@pytest.fixture
def kho_local(tmp_path) -> LocalObjectStorage:
    return LocalObjectStorage(str(tmp_path / "kho"))


class TestChanPathNguyHiem:
    """Trước P3c, cả 3 ca dưới đây đều IM LẶNG đọc/ghi sai chỗ."""

    @pytest.mark.parametrize(
        "xau",
        [
            "/etc/passwd",              # path tuyệt đối NUỐT luôn root: root / "/etc/passwd" == "/etc/passwd"
            "../../etc/passwd",         # thoát bằng ..
            "projects/../../../etc/x",  # thoát bằng .. ở giữa
            "",                         # rỗng -> chính root
            "   ",
        ],
    )
    def test_tu_choi_path_thoat_khoi_goc(self, xau):
        with pytest.raises(UnsafeObjectPath):
            chuan_hoa_path(xau)

    def test_moi_thao_tac_deu_tu_choi_chu_khong_chi_rieng_ham_kiem(self, kho):
        for goi in (
            lambda: kho.save("/etc/passwd", b"x"),
            lambda: kho.read("../ngoai.txt"),
            lambda: kho.open_read("/etc/passwd"),
        ):
            with pytest.raises(UnsafeObjectPath):
                goi()

    def test_kiem_tra_khong_ne_thi_tra_ve_an_toan_chu_khong_no(self, kho):
        """`exists`/`stat`/`delete` là câu hỏi, không phải lệnh — trả 'không có', không ném."""
        assert kho.exists("../ngoai.txt") is False
        assert kho.stat("/etc/passwd") is None
        assert kho.delete("../ngoai.txt") is False
        assert kho.list_prefix("../ngoai") == []

    def test_khong_ghi_duoc_ra_ngoai_goc_that(self, kho, tmp_path):
        moi = tmp_path / "moi-nhu.txt"
        moi.write_text("nguyên vẹn")
        with pytest.raises(UnsafeObjectPath):
            kho.save("../moi-nhu.txt", "đã bị ghi đè".encode())
        assert moi.read_text() == "nguyên vẹn", "tệp ngoài kho bị ghi đè"

    def test_chuan_hoa_bo_thanh_phan_thua(self):
        assert chuan_hoa_path("a/./b.png") == "a/b.png"
        assert chuan_hoa_path("a//b.png") == "a/b.png"


class TestGhiDocXoa:
    def test_ghi_roi_doc_lai_dung_nguyen_van(self, kho):
        rel = kho.save("projects/p1/a.png", b"noi dung")
        assert rel == "projects/p1/a.png"
        assert kho.read(rel) == b"noi dung"
        assert kho.exists(rel)

    def test_open_read_tra_luong_doc_duoc(self, kho):
        kho.save("a.bin", b"0123456789")
        with kho.open_read("a.bin") as fh:
            assert fh.read(4) == b"0123"
            assert fh.read() == b"456789"

    def test_ghi_de_khong_de_lai_tep_ghi_do(self, kho_local, tmp_path):
        kho = kho_local
        kho.save("a.png", b"cu")
        kho.save("a.png", b"moi hon nhieu")
        assert kho.read("a.png") == b"moi hon nhieu"
        thua = [p.name for p in (tmp_path / "kho").rglob("*") if ".ghi-do-" in p.name]
        assert thua == [], f"còn tệp ghi dở: {thua}"

    def test_ghi_loi_giua_chung_thi_ban_cu_con_nguyen(self, kho):
        """Nguồn hỏng ⇒ `save_file` phải ném VÀ giữ nguyên bản cũ, không để tệp cụt."""
        kho.save("a.png", b"ban cu")
        with pytest.raises(OSError):
            kho.save_file("a.png", Path("/khong/he/ton/tai.png"))
        assert kho.read("a.png") == b"ban cu"

    def test_stat_doi_khi_noi_dung_doi(self, kho):
        kho.save("a.png", b"x")
        st1 = kho.stat("a.png")
        kho.save("a.png", b"dai hon")
        st2 = kho.stat("a.png")
        assert st1.size != st2.size
        assert kho.stat("chua-co.png") is None

    def test_xoa_idempotent(self, kho):
        kho.save("a.png", b"x")
        assert kho.delete("a.png") is True
        assert kho.delete("a.png") is False, "xoá lần hai phải là False, không ném"

    def test_thu_muc_khong_bi_tinh_la_hien_vat(self, kho):
        kho.save("d/a.png", b"x")
        assert kho.stat("d") is None
        assert kho.exists("d") is False


class TestLietKeVaDonTheoTienTo:
    def test_liet_ke_de_quy_va_sap_xep(self, kho):
        kho.save("exports/p1/b.cbz", b"x")
        kho.save("exports/p1/png/001.png", b"y")
        assert kho.list_prefix("exports/p1") == [
            "exports/p1/b.cbz",
            "exports/p1/png/001.png",
        ]

    def test_don_theo_tien_to_khong_dung_toi_hang_xom(self, kho):
        kho.save("exports/p1/a.cbz", b"x")
        kho.save("exports/p10/giu.cbz", b"y")   # tiền tố p1 là tiền tố CHUỖI của p10
        da_xoa = kho.delete_prefix("exports/p1")
        assert da_xoa == ["exports/p1/a.cbz"]
        assert kho.list_prefix("exports/p10") == ["exports/p10/giu.cbz"], "xoá lan sang project khác"

    def test_don_xong_khong_de_lai_thu_muc_rong(self, kho_local, tmp_path):
        kho = kho_local
        kho.save("exports/p1/png/001.png", b"x")
        kho.delete_prefix("exports/p1")
        assert not (tmp_path / "kho" / "exports" / "p1" / "png").exists()


class TestVatChatHoa:
    def test_fetch_to_chep_ra_ngoai_kho_va_giu_nguyen_byte(self, kho):
        kho.save("projects/p1/a.png", b"noi dung that")
        with workspace() as ws:
            dich = kho.fetch_to("projects/p1/a.png", ws / "a.png")
            assert dich.read_bytes() == b"noi dung that"
            assert ws in dich.parents, "phải nằm trong thư mục tạm, không phải trong lòng kho"

    def test_workspace_luon_duoc_don_ke_ca_khi_loi(self):
        giu = {}
        with pytest.raises(RuntimeError):
            with workspace() as ws:
                giu["d"] = ws
                (ws / "rac.txt").write_text("x")
                raise RuntimeError("hỏng giữa chừng")
        assert not giu["d"].exists(), "thư mục tạm còn sót sau khi lỗi"

    def test_ghi_nguoc_vao_kho_tu_tep_cuc_bo(self, kho):
        with workspace() as ws:
            tep = ws / "ket-qua.png"
            tep.write_bytes(b"engine vua ghi")
            rel = kho.save_file("previews/p1/typeset.png", tep)
        assert rel == "previews/p1/typeset.png"
        assert kho.read(rel) == b"engine vua ghi"


class TestRiengPostgres:
    """Những gì chỉ backend CSDL mới có."""

    def test_tran_kich_thuoc_chan_o_duong_GHI(self):
        """Chặn lúc ghi, không để phát hiện lúc đọc — lúc đó đã muộn và đã tốn CSDL."""
        kho = _kho_postgres(max_bytes=1024)
        kho.save("vua-du.bin", b"x" * 1024)
        with pytest.raises(ArtifactTooLarge):
            kho.save("qua-to.bin", b"x" * 1025)
        assert kho.exists("qua-du.bin") is False
        assert kho.exists("qua-to.bin") is False, "hiện vật quá trần vẫn lọt vào kho"

    def test_ghi_de_la_upsert_khong_de_lai_hang_trung(self):
        kho = _kho_postgres()
        kho.save("a.png", b"cu")
        kho.save("a.png", b"moi")
        with sync_session() as s:
            n = s.scalar(
                sa.select(sa.func.count()).select_from(ArtifactBlob).where(
                    ArtifactBlob.path == "a.png"
                )
            )
        assert n == 1, "ghi đè đẻ ra hàng thứ hai"
        assert kho.read("a.png") == b"moi"

    def test_stat_khong_keo_ca_hien_vat_len(self):
        """`size_bytes` là cột riêng đúng để `stat()` khỏi phải đọc cột `data`."""
        kho = _kho_postgres()
        kho.save("to.bin", b"y" * 300_000)
        st = kho.stat("to.bin")
        assert st.size == 300_000
        with sync_session() as s:
            luu = s.scalar(sa.select(ArtifactBlob.size_bytes).where(ArtifactBlob.path == "to.bin"))
        assert luu == 300_000, "size_bytes lệch với nội dung thật"

    def test_moc_phien_ban_du_min_de_phan_biet_hai_lan_ghi_lien_tiep(self):
        """Vân tay E14 = (size, mtime). Hai lượt ghi cùng cỡ trong cùng một giây mà mtime không
        đổi thì E14 sẽ dùng lại hình bong bóng của ảnh CŨ. Micro giây loại hẳn ca đó."""
        kho = _kho_postgres()
        kho.save("a.png", b"x" * 100)
        m1 = kho.stat("a.png").mtime
        kho.save("a.png", b"y" * 100)          # CÙNG kích thước, ngay lập tức
        m2 = kho.stat("a.png").mtime
        assert m1 != m2, "hai lần ghi liên tiếp cùng cỡ cho ra cùng mốc phiên bản"

    def test_ten_co_dau_gach_duoi_khong_bi_LIKE_hieu_nham(self):
        """`_` là ký tự đại diện của LIKE, mà tên thật của hệ thống có `_` (`…_clean.png`)."""
        kho = _kho_postgres()
        kho.save("p_1/a_clean.png", b"x")
        kho.save("pX1/b.png", b"y")            # khớp `p_1/%` nếu quên thoát `_`
        assert kho.list_prefix("p_1") == ["p_1/a_clean.png"]
