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
#: E84 — dải viền SẠCH gần như tuyệt đối (≥ tỉ lệ này điểm gần nền) ⇒ không nét viền bong bóng nào
#: cắt qua khung được (muốn vào khung phải đi qua dải). Khi đó mực ở mép trong chỉ có thể là CHÍNH NÉT
#: CHỮ chạm mép — khung của bộ nhận diện ngoài (Gemini) ôm rất sát chữ. Đo thật 16-10-2026 trang
#: ja_E12P01: 5/6 câu có dải viền 100% trắng nhưng mép trong chỉ 84–92% ⇒ bị loại oan, rơi về LaMa và
#: để lại bóng mờ chữ gốc. Ca này: bỏ chốt mép trong và tô cả khe hở `KHE_HO` (nét chữ chạm mép
#: thường lấn vào khe).
TI_LE_VIEN_SACH = 0.995
#: …nhưng vẫn chặn NÉT VẼ CHẠY DỌC MÉP bên trong khung (không chạm dải viền): nét như vậy phủ kín MỘT
#: cạnh, còn chữ chạm mép chỉ chạm vài điểm. Đo trên mỗi cạnh: tỉ lệ vị trí dọc cạnh mà CẢ `MEP_TRONG`
#: điểm đều là nền. Đo thật (11 khung, ja_E12P01): cạnh tệ nhất của khung chữ chạm mép = 0.56; nét vẽ
#: dọc mép = 0.
TI_LE_MOI_CANH_GAN_NEN_KHI_VIEN_SACH = 0.4
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


#: E86 — tô từng phần: nền đa số trong dải viền phải chiếm ít nhất tỉ lệ này.
TI_LE_NEN_DA_SO = 0.6


def _to_net_trong_nen_da_so(anh, o, ngoai, lay) -> bool:
    """E86 — dải viền KHÔNG phẳng toàn bộ, nhưng đa số là MỘT màu nền phẳng (bong bóng trắng không
    viền nằm trên nền trời: khung chữ sát mép bong bóng nên dải viền lẫn màu trời).

    Đo thật (ja_E12P01, "その通り"): ca này rơi về LaMa và LaMa kéo màu trời vào trong bong bóng
    thành một vệt xanh. Ở đây chỉ tô màu bong bóng lên NÉT CHỮ, giữ nguyên phần nền khác lọt vào
    khung:
    - thành phần liên thông "không phải màu bong bóng" trong khung;
    - thành phần chạm MÉP khung mà ngay bên ngoài chỗ chạm KHÔNG phải màu bong bóng ⇒ là nền khác
      (trời) tràn vào ⇒ giữ nguyên;
    - còn lại là nét chữ (nằm trọn trong lòng bong bóng) ⇒ tô.
    Không chắc (không đủ nền đa số, nét chữ chiếm quá nửa khung) ⇒ trả False, để LaMa như cũ.
    """
    import cv2

    x1, y1, x2, y2 = o
    ox1, oy1, ox2, oy2 = ngoai
    vien = anh[oy1:oy2, ox1:ox2][lay]
    if vien.shape[0] < SO_MAU_TOI_THIEU:
        return False
    tho = np.floor(np.median(vien.astype(np.float64), axis=0)).astype(np.int16)
    gan_vien = (np.abs(vien.astype(np.int16) - tho) <= SAI_SO_GAN_NEN).all(axis=1)
    if gan_vien.mean() < TI_LE_NEN_DA_SO:
        return False
    mau = mau_nen_phang(vien[gan_vien])
    if mau is None:
        return False

    vung = anh[oy1:oy2, ox1:ox2].astype(np.int16)
    gan = (np.abs(vung - mau.astype(np.int16)) <= SAI_SO_GAN_NEN).all(axis=2)
    ty1, tx1 = y1 - oy1, x1 - ox1
    trong = ~gan[ty1:ty1 + (y2 - y1), tx1:tx1 + (x2 - x1)]
    if trong.mean() > 0.5 or not trong.any():
        return False
    so, nhan = cv2.connectedComponents(trong.astype(np.uint8), connectivity=8)
    # Điểm ngay BÊN NGOÀI mép khung (trong vùng `ngoai`) có phải màu bong bóng không.
    def _ngoai_la_nen(yy, xx):
        gy, gx = yy + ty1, xx + tx1
        lan = []
        if yy == 0 and gy > 0:
            lan.append(gan[gy - 1, gx])
        if yy == trong.shape[0] - 1 and gy + 1 < gan.shape[0]:
            lan.append(gan[gy + 1, gx])
        if xx == 0 and gx > 0:
            lan.append(gan[gy, gx - 1])
        if xx == trong.shape[1] - 1 and gx + 1 < gan.shape[1]:
            lan.append(gan[gy, gx + 1])
        return all(lan) if lan else True

    to = np.zeros_like(trong)
    h, w = trong.shape
    for k in range(1, so):
        tp = nhan == k
        ys, xs = np.nonzero(tp)
        bien = (ys == 0) | (ys == h - 1) | (xs == 0) | (xs == w - 1)
        if bien.any() and not all(_ngoai_la_nen(yy, xx) for yy, xx in zip(ys[bien], xs[bien])):
            continue  # nền khác tràn vào khung — giữ nguyên
        to |= tp
    if not to.any():
        return False
    # Nới 1px để ăn cả viền khử răng cưa của nét chữ, nhưng không lấn sang khung chữ khác.
    # Tô MỌI điểm trong khung trừ phần nền khác (và 1px quanh nó để giữ mép bong bóng): tô riêng nét
    # chữ thì viền khử răng cưa — xám nhạt, vẫn "gần màu nền" — còn lại thành bóng mờ (đo thật).
    nen_khac = trong & ~to
    giu = cv2.dilate(nen_khac.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    anh[y1:y2, x1:x2][~giu] = mau
    return True


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
        mau_vien = anh[oy1:oy2, ox1:ox2][lay]
        mau = _mau_vien_phang(mau_vien)
        if mau is None:
            if _to_net_trong_nen_da_so(anh, (x1, y1, x2, y2), (ox1, oy1, ox2, oy2), lay):
                da_to.append(i)
            else:
                con_lai.append(i)
            continue
        vien_sach = bool(
            (np.abs(mau_vien.astype(np.int16) - mau.astype(np.int16)) <= SAI_SO_GAN_NEN)
            .all(axis=1).mean() >= TI_LE_VIEN_SACH
        )

        trong = anh[y1:y2, x1:x2].astype(np.int16)
        gan_nen = (np.abs(trong - mau.astype(np.int16)) <= SAI_SO_GAN_NEN).all(axis=2)
        if gan_nen.mean() < TI_LE_NEN_TRONG_TOI_THIEU:
            con_lai.append(i)
            continue
        mep = np.ones(gan_nen.shape, dtype=bool)
        mep[MEP_TRONG:-MEP_TRONG, MEP_TRONG:-MEP_TRONG] = False
        if vien_sach:
            m = MEP_TRONG
            canh = (gan_nen[:m].all(axis=0), gan_nen[-m:].all(axis=0),
                    gan_nen[:, :m].all(axis=1), gan_nen[:, -m:].all(axis=1))
            if min(c.mean() for c in canh) < TI_LE_MOI_CANH_GAN_NEN_KHI_VIEN_SACH:
                con_lai.append(i)
                continue
        elif gan_nen[mep].mean() < TI_LE_MEP_TRONG_GAN_NEN:
            con_lai.append(i)
            continue

        if vien_sach:
            # Tô cả khe hở — nhưng KHÔNG lấn sang khung chữ khác (khe của khung này có thể là chữ
            # của khung kia khi hai khung sát nhau).
            tx1, ty1 = max(0, x1 - KHE_HO), max(0, y1 - KHE_HO)
            tx2, ty2 = min(rong, x2 + KHE_HO), min(cao, y2 + KHE_HO)
            vung = np.ones((ty2 - ty1, tx2 - tx1), dtype=bool)
            vung &= ~phu[ty1:ty2, tx1:tx2]
            vung[y1 - ty1:y2 - ty1, x1 - tx1:x2 - tx1] = True
            anh[ty1:ty2, tx1:tx2][vung] = mau
        else:
            anh[y1:y2, x1:x2] = mau
        da_to.append(i)

    return KetQuaToPhang(da_to=tuple(da_to), con_lai=tuple(con_lai))
