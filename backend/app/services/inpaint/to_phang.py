"""Tô phẳng vùng chữ nằm trên nền một màu — bỏ qua LaMa cho những vùng đó.

## Nguồn

Ý tưởng và công thức kiểm "nền phẳng" lấy từ Koharu
(`crates/koharu-pipeline/src/stages/inpainting.rs`, `uniform_region_color` / `fill_uniform_regions`,
MIT OR Apache-2.0, © Mayo Takanashi and Koharu contributors), bản gốc lại dựa trên
BallonsTranslator. Viết lại bằng numpy, không chép mã.

## Khác Koharu ở đâu, vì sao

Koharu có **đa giác bong bóng** (model nhận diện trả mặt nạ bong bóng) nên lấy mẫu nền trong lòng
bong bóng. Ở đây bước xoá chữ chỉ có **khung chữ nhật đã nới** — vậy lấy mẫu một **dải viền ngay
bên ngoài khung**. Chữ nằm trong bong bóng trắng ⇒ dải viền cũng nằm trong bong bóng ⇒ phẳng. Khung
chạm viền bong bóng hoặc nằm trên nền vẽ ⇒ dải viền dính mực/hoạ tiết ⇒ không phẳng ⇒ giữ LaMa.

Thêm một chốt Koharu không cần: **phần lớn bên trong khung cũng phải mang màu nền đó**. Koharu chỉ
tô đúng điểm ảnh thuộc mặt nạ chữ; ở đây cả khung bị tô, nên phải chắc trong khung chủ yếu là nền
chứ không phải tranh.

Mọi trường hợp không chắc đều rơi về LaMa — hàm này chỉ được phép *bớt* việc cho model, không
được đổi cách xoá ở chỗ nó không chắc.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.services.interfaces import BBox

#: Koharu `UNIFORM_BACKGROUND_MIN_PIXELS` — ít mẫu hơn thì không đủ căn cứ để gọi là phẳng.
SO_MAU_TOI_THIEU = 16
#: Koharu: ngưỡng độ lệch chuẩn quanh trung vị. 7 khi ba kênh lệch nhau (ảnh màu), 10 khi đều nhau
#: (ảnh xám — nhiễu JPEG trên giấy trắng thường cao hơn một chút mà vẫn là "trắng").
NGUONG_LECH_MAU = 7.0
NGUONG_LECH_XAM = 10.0
#: Khoảng hở giữa khung và dải viền: bỏ qua quầng nhiễu JPEG sát nét chữ.
KHE_HO = 2
#: Bề dày dải viền: tỉ lệ cạnh ngắn của khung, tối thiểu `VIEN_TOI_THIEU` px.
TI_LE_VIEN = 0.06
VIEN_TOI_THIEU = 4
#: Một điểm trong khung được coi là "nền" nếu mọi kênh lệch trung vị không quá chừng này.
SAI_SO_GAN_NEN = 24
#: E69 đo trên trang thật: dải viền của chữ trong bong bóng trắng thường có 95–99% điểm là nền,
#: phần còn lại là NÉT VIỀN BONG BÓNG lọt vào dải (Koharu không gặp vì nó có đa giác bong bóng và
#: bỏ 3px sát viền). Lấy độ lệch trên CẢ dải thì vài điểm mực đó đẩy độ lệch lên 18–24 và vùng bị
#: loại oan. Nên: dải phải có ≥ `TI_LE_VIEN_GAN_NEN` điểm gần nền, và độ phẳng chỉ đo trên các điểm
#: gần nền đó.
TI_LE_VIEN_GAN_NEN = 0.95
#: Chốt bù cho việc nới lỏng ở trên: MÉP TRONG khung (dày `MEP_TRONG` px) cũng phải gần như toàn
#: nền. Nét viền bong bóng mà cắt vào khung thì mép khung lộ mực ⇒ không tô (tô là xoá mất nét).
MEP_TRONG = 2
TI_LE_MEP_TRONG_GAN_NEN = 0.95
#: Tối thiểu tỉ lệ điểm "nền" bên trong khung. Nét chữ manga thường chiếm 10–35% khung đã nới;
#: dưới 50% nghĩa là trong khung có thứ khác ngoài chữ (tranh, hoạ tiết) ⇒ để LaMa vẽ lại.
TI_LE_NEN_TRONG_TOI_THIEU = 0.5


@dataclass(frozen=True)
class KetQuaToPhang:
    #: Chỉ số (theo danh sách đầu vào) các khung đã tô phẳng.
    da_to: tuple[int, ...]
    #: Chỉ số các khung còn lại — phải chạy LaMa.
    con_lai: tuple[int, ...]


def o_nguyen(bbox: BBox, rong: int, cao: int) -> tuple[int, int, int, int]:
    """Làm tròn ra ngoài và kẹp trong ảnh — ĐÚNG cách `mask.build_mask` dựng mặt nạ."""
    x1 = max(0, int(np.floor(bbox.x)))
    y1 = max(0, int(np.floor(bbox.y)))
    x2 = min(rong, int(np.ceil(bbox.x + bbox.w)))
    y2 = min(cao, int(np.ceil(bbox.y + bbox.h)))
    return x1, y1, x2, y2


def mau_nen_phang(mau: np.ndarray) -> np.ndarray | None:
    """Trả màu trung vị (3 kênh uint8) nếu các mẫu đủ phẳng theo công thức Koharu, ngược lại None.

    `mau`: mảng N×3 uint8.
    """
    if mau.shape[0] < SO_MAU_TOI_THIEU:
        return None
    mau_f = mau.astype(np.float64)
    # Koharu lấy trung vị số nguyên kiểu u8 (trung bình hai phần tử giữa, làm tròn xuống).
    trung_vi = np.floor(np.median(mau_f, axis=0))
    lech = np.sqrt(((mau_f - trung_vi) ** 2).mean(axis=0))
    do_trai = np.sqrt(((lech - lech.mean()) ** 2).mean())
    nguong = NGUONG_LECH_MAU if do_trai > 1.0 else NGUONG_LECH_XAM
    if lech.max() >= nguong:
        return None
    return trung_vi.astype(np.uint8)


def _mau_vien_phang(mau: np.ndarray) -> np.ndarray | None:
    """Như `mau_nen_phang` nhưng chịu được ít điểm ngoại lai (nét viền bong bóng lọt vào dải).

    Trung vị thô ⇒ giữ các điểm gần nó ⇒ cần ≥ `TI_LE_VIEN_GAN_NEN` ⇒ đo phẳng trên phần đã giữ.
    """
    if mau.shape[0] < SO_MAU_TOI_THIEU:
        return None
    tho = np.floor(np.median(mau.astype(np.float64), axis=0))
    gan = (np.abs(mau.astype(np.int16) - tho.astype(np.int16)) <= SAI_SO_GAN_NEN).all(axis=1)
    if gan.mean() < TI_LE_VIEN_GAN_NEN:
        return None
    return mau_nen_phang(mau[gan])


def to_phang(anh: np.ndarray, khung_da_noi: list[BBox]) -> KetQuaToPhang:
    """Tô phẳng TẠI CHỖ các khung nằm trên nền một màu.

    `anh`: HWC uint8, bị sửa trực tiếp. `khung_da_noi`: các khung ĐÃ nới (cùng khung dựng mặt nạ).
    Không khung nào bị tô nếu dải viền của nó không đủ phẳng hoặc trong khung có quá nhiều thứ
    không phải nền.
    """
    cao, rong = anh.shape[:2]
    o = [o_nguyen(b, rong, cao) for b in khung_da_noi]

    # Mặt nạ mọi khung: dải viền của khung này không được lấy mẫu từ chữ của khung bên cạnh.
    phu = np.zeros((cao, rong), dtype=bool)
    for x1, y1, x2, y2 in o:
        phu[y1:y2, x1:x2] = True

    da_to: list[int] = []
    con_lai: list[int] = []
    for i, (x1, y1, x2, y2) in enumerate(o):
        if x2 <= x1 or y2 <= y1:
            con_lai.append(i)
            continue
        vien = max(VIEN_TOI_THIEU, int(round(TI_LE_VIEN * min(x2 - x1, y2 - y1))))
        ngoai = KHE_HO + vien
        ox1, oy1 = max(0, x1 - ngoai), max(0, y1 - ngoai)
        ox2, oy2 = min(rong, x2 + ngoai), min(cao, y2 + ngoai)
        lay = np.ones((oy2 - oy1, ox2 - ox1), dtype=bool)
        # Khoét phần khung + khe hở, chỉ còn dải viền.
        lay[
            max(0, y1 - KHE_HO - oy1): min(oy2, y2 + KHE_HO) - oy1,
            max(0, x1 - KHE_HO - ox1): min(ox2, x2 + KHE_HO) - ox1,
        ] = False
        lay &= ~phu[oy1:oy2, ox1:ox2]
        mau = _mau_vien_phang(anh[oy1:oy2, ox1:ox2][lay])
        if mau is None:
            con_lai.append(i)
            continue

        trong = anh[y1:y2, x1:x2].astype(np.int16)
        gan_nen = (np.abs(trong - mau.astype(np.int16)) <= SAI_SO_GAN_NEN).all(axis=2)
        if gan_nen.mean() < TI_LE_NEN_TRONG_TOI_THIEU:
            con_lai.append(i)
            continue
        mep = np.ones(gan_nen.shape, dtype=bool)
        mep[MEP_TRONG:-MEP_TRONG, MEP_TRONG:-MEP_TRONG] = False
        if gan_nen[mep].mean() < TI_LE_MEP_TRONG_GAN_NEN:
            con_lai.append(i)
            continue

        anh[y1:y2, x1:x2] = mau
        da_to.append(i)

    return KetQuaToPhang(da_to=tuple(da_to), con_lai=tuple(con_lai))
