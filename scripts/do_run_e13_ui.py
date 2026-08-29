#!/usr/bin/env python3
"""Run C + Run D của E13 — đo trên giao diện thật bằng Chromium.

Run C — hồ sơ giọng nhân vật: tạo qua UI, xem nó có hiện ra làm ngữ cảnh lúc rà soát không,
        và **quan trọng nhất**: chỉ xem thôi thì bản dịch trong CSDL phải y nguyên.
Run D — hộp thoại xuất: số việc nhất quán có nằm riêng khối, không lẫn với tràn khung / chất
        lượng / bản quyền, và vẫn xuất được.

    ../.venv/bin/python scripts/do_run_e13_ui.py <project_id>
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

from playwright.sync_api import sync_playwright

GOC = "http://localhost:5174"
KQ: dict = {}


def sql(cau: str) -> str:
    r = subprocess.run(
        ["docker", "compose", "-f", "deploy/docker-compose.yml", "exec", "-T", "db",
         "psql", "-U", "translation", "-d", "translation", "-tAc", cau],
        capture_output=True, text=True, check=True,
    )
    return r.stdout.strip()


def don_dep(pid: str) -> None:
    """Dựng lại điều kiện đầu để lần chạy nào cũng ra cùng kết quả.

    Xoá đúng thứ **chính lần chạy trước của script này** tạo ra (thuật ngữ `Happy`, hồ sơ giọng
    `Pepper`) và xoá dấu đã-xác-nhận-bản-quyền của chapter, vì hộp thoại xuất cố ý chỉ hiện một
    lần cho mỗi chapter — không xoá thì Run D không có gì để quan sát. Không đụng tới thuật ngữ
    và việc của Run A/B.
    """
    sql("delete from consistency_review_task where glossary_entry_id in "
        "(select id from glossary_entry where source_term = 'Happy')")
    sql("delete from glossary_entry where source_term = 'Happy'")
    sql("delete from character_voice_profile where character_name = 'Pepper'")
    sql(f"delete from export_compliance_log where project_id = '{pid}'")


def anh_ban_dich(pid: str) -> str:
    return sql(
        "select string_agg(t.id || '=' || md5(coalesce(t.translated_text,'')) || ':' "
        "|| t.edited_by_user, ',' order by t.id) "
        "from translation_result t join text_region r on r.id = t.region_id "
        f"join page p on p.id = r.page_id where p.project_id = '{pid}'"
    )


def chu(page) -> str:
    """Chữ đang hiện trên màn hình, hạ về chữ thường.

    `inner_text()` trả về chữ **sau khi CSS biến đổi**: các tiêu đề `h3` được `text-transform`
    viết hoa hết. So thẳng chuỗi gốc sẽ báo "không tìm thấy" trong khi mắt người vẫn đọc được —
    đó là lỗi của phép đo, không phải của sản phẩm.
    """
    return page.inner_text("body").casefold()


def main(pid: str) -> None:
    don_dep(pid)
    truoc = anh_ban_dich(pid)

    with sync_playwright() as pw:
        tb = pw.chromium.launch()
        page = tb.new_page(viewport={"width": 1280, "height": 950})
        loi_console: list[str] = []
        page.on("console", lambda m: m.type == "error" and loi_console.append(m.text))
        page.goto(f"{GOC}/#project={pid}", wait_until="networkidle")
        page.wait_for_timeout(1200)

        # ---------- Run C ----------
        page.get_by_role("button", name="Thêm nhân vật").click()
        page.get_by_label("Tên nhân vật").fill("Pepper")
        page.get_by_label("Giọng điệu", exact=True).select_option(label="Thân mật")
        page.get_by_label("Cách xưng hô tiếng Việt").fill("xưng 'tớ', gọi Carrot là 'cậu'")
        page.get_by_label("Ghi chú giọng điệu", exact=True).fill("Hấp tấp, hay reo lên; không dùng giọng trang trọng.")
        page.get_by_role("button", name="Thêm", exact=True).click()
        page.wait_for_timeout(1500)
        # Hồ sơ mới phải ở *nháp*: chưa bật thì không được coi là đang có hiệu lực.
        KQ["C1_tao_ho_so"] = "pepper" in chu(page)
        KQ["C1b_moi_tao_la_nhap"] = "nháp" in chu(page)
        page.get_by_role("button", name="Dùng", exact=True).click()
        page.wait_for_timeout(1200)
        KQ["C1c_bat_duoc"] = "đang dùng" in chu(page)

        # Không có thanh "độ tin cậy" ở bất kỳ đâu trên màn hình.
        KQ["C2_khong_do_tin_cay"] = "độ tin cậy" not in chu(page)

        # Tạo một thuật ngữ mới trỏ vào một chỗ dịch sai thật rồi duyệt + quét.
        page.get_by_role("button", name="Thêm thuật ngữ").click()
        page.get_by_label("Thuật ngữ gốc").fill("Happy")
        page.get_by_label("Cách dịch đã chốt").fill("Vui chưa")
        page.get_by_label("Giải nghĩa").fill(
            "Carrot trêu Pepper — là câu hỏi 'vui chưa?', không phải cảm thán 'vui mừng'.")
        page.get_by_role("button", name="Thêm", exact=True).click()
        page.wait_for_timeout(1200)
        page.get_by_role("button", name="Duyệt").last.click()
        page.wait_for_timeout(1200)
        page.get_by_role("button", name="Rà soát nhất quán").click()
        page.wait_for_timeout(2500)
        page.get_by_role("button", name=re.compile(r"Xem \d+ chỗ cần sửa")).click()
        page.wait_for_timeout(800)
        page.locator("#tieu-de-hang-doi").scroll_into_view_if_needed()
        page.wait_for_timeout(400)

        t = chu(page)
        KQ["C3_hang_doi_hien_viec"] = "rà soát nhất quán" in t and "vui chưa" in t
        KQ["C4_hien_ho_so_giong"] = ("giọng nhân vật bạn đã đặt" in t and "xưng 'tớ'" in t
                                     and "pepper · thân mật" in t)
        KQ["C5_noi_ro_khong_tu_sua"] = "không tự sửa lời thoại theo" in t
        KQ["C6_o_sua_giu_ban_dich_hien_tai"] = (
            page.get_by_label("Bản dịch cho vùng này").input_value().strip() == "Vui mừng?!"
        )
        page.screenshot(path="/tmp/e13_runC.png", full_page=True)

        # ---------- Run D ----------
        so_job_truoc = sql("select count(*) from export_job")
        nut_xuat = page.get_by_role("button", name="Xuất chapter", exact=True)
        nut_xuat.scroll_into_view_if_needed()
        nut_xuat.click()
        page.wait_for_timeout(900)
        hop = page.get_by_role("dialog")
        th = hop.inner_text().casefold()
        KQ["D1_co_khoi_nhat_quan"] = "nhất quán thuật ngữ" in th
        KQ["D2_tach_khoi_chat_luong"] = "chất lượng bản đang xuất" in th
        KQ["D3_tach_khoi_ban_quyen"] = "trách nhiệm về bản quyền" in th
        KQ["D4_dem_dung"] = "1 chỗ chưa rà soát" in th
        nut = hop.get_by_role("button", name="Xuất dù còn")
        KQ["D5_van_cho_xuat"] = nut.count() == 1
        KQ["D5_nhan_nut"] = nut.inner_text() if nut.count() else None
        KQ["D6_khoa_khi_chua_tick"] = nut.is_disabled() if nut.count() else None
        hop.get_by_role("checkbox").check()
        KQ["D7_mo_khi_da_tick"] = not nut.is_disabled() if nut.count() else None
        hop.screenshot(path="/tmp/e13_runD.png")
        page.get_by_role("button", name="Để sau").click()
        page.wait_for_timeout(800)
        # Bấm "Để sau" thì tuyệt đối không được có file nào chạy ra sau lưng người dùng.
        KQ["D8_de_sau_khong_xuat"] = sql("select count(*) from export_job") == so_job_truoc

        KQ["loi_console"] = loi_console
        tb.close()

    sau = anh_ban_dich(pid)
    KQ["C7_ban_dich_khong_doi"] = truoc == sau
    KQ["anh_truoc"] = truoc
    KQ["anh_sau"] = sau
    print(json.dumps(KQ, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
