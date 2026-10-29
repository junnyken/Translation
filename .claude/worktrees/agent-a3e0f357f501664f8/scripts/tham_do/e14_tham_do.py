#!/usr/bin/env python3
"""THĂM DÒ E14 — KHÔNG PHẢI MÃ SẢN XUẤT.

Mục đích duy nhất: lấy bằng chứng thật để trả lời câu hỏi của mục 5 "Audit Before Build" —
heuristic vùng sáng có chọn đúng lòng bong bóng trên trang truyện thật không, và tỉ lệ chọn
sai là bao nhiêu. Không import từ app.*, không ghi DB, không đụng ảnh gốc.

Chạy trong container worker (nơi có cv2):
    docker compose -f deploy/docker-compose.yml exec -T worker python /app/../scripts/...
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

RA = Path("/data/storage/_e14_tham_do")


def kiem_cuc_tinh_distance_transform() -> dict:
    """distanceTransform đo khoảng cách tới pixel ZERO gần nhất — phải ĐO chứ không đoán."""
    m = np.zeros((21, 21), np.uint8)
    m[5:16, 5:16] = 255                      # ô vuông 11x11 ở giữa
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    tam = float(dt[10, 10])
    mep = float(dt[5, 10])
    ngoai = float(dt[0, 0])
    # Nghịch đảo để chứng minh cực tính thật sự phụ thuộc giá trị 0, không phải "vùng trắng".
    dt_dao = cv2.distanceTransform(255 - m, cv2.DIST_L2, 5)
    return {
        "tam_o_vuong": tam, "sat_mep": mep, "ngoai_o_vuong": ngoai,
        "tam_khi_dao_mask": float(dt_dao[10, 10]),
        "ket_luan": ("nen trang (255) = vung do; 0 = bien. Tam xa bien nhat."
                     if tam > mep > ngoai else "CUC TINH KHAC DU DOAN — phai xem lai"),
    }


def cat_roi(bbox, w, h, ti_le=4.0, toi_da=1400):
    x, y, bw, bh = bbox
    ex = min(bw * ti_le, toi_da)
    ey = min(bh * ti_le, toi_da)
    x0 = max(int(x - ex), 0); y0 = max(int(y - ey), 0)
    x1 = min(int(x + bw + ex), w); y1 = min(int(y + bh + ey), h)
    return x0, y0, x1 - x0, y1 - y0


def thu_mot_vung(anh, bbox, ten, nguong_sang=200, nguong_bao_hoa=60):
    """Tìm lòng bong bóng quanh MỘT bbox. Trả quyết định + lý do, không ghi DB."""
    h, w = anh.shape[:2]
    rx, ry, rw, rh = cat_roi(bbox, w, h)
    roi = anh[ry:ry + rh, rx:rx + rw]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sang = ((hsv[:, :, 2] >= nguong_sang) & (hsv[:, :, 1] <= nguong_bao_hoa)).astype(np.uint8) * 255

    # Nhân hình thái bám theo BBOX CHỮ, không theo ROI: ROI đổi thì nhân không được đổi
    # theo, nếu không mỗi lần nới ROI là một thuật toán khác.
    k = int(max(3, round(min(bbox[2], bbox[3]) * 0.06)) // 2 * 2 + 1)
    dong = cv2.morphologyEx(sang, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    dong = cv2.morphologyEx(dong, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))

    # Lấy đường viền NGOÀI của từng ứng viên rồi tô đặc TỪNG cái một. Lấp lỗ trên cả ROI là
    # sai: vùng tối bị nền sáng bao quanh cũng bị coi là "lỗ" và bị nuốt vào.
    vien, _ = cv2.findContours(dong, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cx = float(bbox[0] + bbox[2] / 2 - rx)
    cy = float(bbox[1] + bbox[3] / 2 - ry)
    dt_bbox = bbox[2] * bbox[3]

    kq = {"ten": ten, "roi": [rx, ry, rw, rh], "so_ung_vien": len(vien),
          "kernel_dong": k, "ly_do": []}

    chua_tam = [c for c in vien if cv2.pointPolygonTest(c, (cx, cy), False) >= 0]
    kq["so_ung_vien_chua_tam"] = len(chua_tam)
    if not chua_tam:
        kq["ly_do"].append("khong_ung_vien_nao_chua_tam_bbox")
        kq["ket_qua"] = "fallback"
        cv2.imwrite(str(RA / f"{ten}_1_roi.png"), roi)
        cv2.imwrite(str(RA / f"{ten}_2_nguong.png"), dong)
        return kq
    if len(chua_tam) > 1:
        kq["ly_do"].append("nhieu_ung_vien_long_nhau")

    c = min(chua_tam, key=cv2.contourArea)     # ứng viên KHÍT nhất quanh tâm, không phải to nhất
    mask = np.zeros((rh, rw), np.uint8)
    cv2.drawContours(mask, [c], -1, 255, cv2.FILLED)

    dien_tich = int((mask > 0).sum())
    kq["dien_tich"] = dien_tich
    kq["ty_le_so_voi_bbox"] = round(dien_tich / dt_bbox, 3)
    kq["ty_le_so_voi_roi"] = round(dien_tich / (rw * rh), 3)

    vien_cham = int((mask[0, :] > 0).sum() + (mask[-1, :] > 0).sum()
                    + (mask[:, 0] > 0).sum() + (mask[:, -1] > 0).sum())
    kq["ty_le_cham_bien"] = round(vien_cham / (2 * (rw + rh)), 4)

    le = max(3, int(round(min(bbox[2], bbox[3]) * 0.06)))
    kq["le_an_vao"] = le
    mask_an = cv2.erode(mask, np.ones((le * 2 + 1, le * 2 + 1), np.uint8))
    kq["con_lai_sau_an"] = int((mask_an > 0).sum())

    if dien_tich < 0.8 * dt_bbox:
        kq["ly_do"].append("ung_vien_qua_nho_so_voi_bbox")
    if kq["ty_le_so_voi_roi"] > 0.75:
        kq["ly_do"].append("ung_vien_chiem_gan_het_roi")
    if kq["ty_le_cham_bien"] > 0.02:
        kq["ly_do"].append("cham_bien_roi")
    if kq["con_lai_sau_an"] == 0:
        kq["ly_do"].append("an_vao_lam_mat_het")

    cv2.imwrite(str(RA / f"{ten}_1_roi.png"), roi)
    cv2.imwrite(str(RA / f"{ten}_2_nguong.png"), dong)

    if kq["ly_do"]:
        kq["ket_qua"] = "fallback"
        return kq

    dt = cv2.distanceTransform((mask_an > 0).astype(np.uint8), cv2.DIST_L2, 5)
    _, r_max, _, diem = cv2.minMaxLoc(dt)
    kq["ban_kinh_lon_nhat"] = round(float(r_max), 1)
    kq["diem_trong_long"] = [int(diem[0] + rx), int(diem[1] + ry)]
    cnt2, _ = cv2.findContours((mask_an > 0).astype(np.uint8),
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c2 = max(cnt2, key=cv2.contourArea)
    xap_xi = cv2.approxPolyDP(c2, 0.005 * cv2.arcLength(c2, True), True)
    kq["so_dinh_da_giac"] = len(xap_xi)
    kq["ket_qua"] = "shape_derived"

    ve = roi.copy()
    cv2.drawContours(ve, [xap_xi], -1, (0, 0, 255), 2)
    cv2.circle(ve, diem, 4, (255, 0, 0), -1)
    cv2.rectangle(ve, (int(bbox[0] - rx), int(bbox[1] - ry)),
                  (int(bbox[0] + bbox[2] - rx), int(bbox[1] + bbox[3] - ry)), (0, 200, 0), 1)
    cv2.imwrite(str(RA / f"{ten}_4_ketqua.png"), ve)
    cv2.imwrite(str(RA / f"{ten}_3_an.png"), mask_an)
    return kq


def main() -> None:
    RA.mkdir(parents=True, exist_ok=True)
    cauhinh = json.loads(Path(sys.argv[1]).read_text())
    out = {"cuc_tinh_distance_transform": kiem_cuc_tinh_distance_transform(), "vung": []}
    for v in cauhinh:
        anh = cv2.imread(v["anh"])
        if anh is None:
            out["vung"].append({"ten": v["ten"], "loi": "khong doc duoc anh"}); continue
        out["vung"].append(thu_mot_vung(anh, v["bbox"], v["ten"]))
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
