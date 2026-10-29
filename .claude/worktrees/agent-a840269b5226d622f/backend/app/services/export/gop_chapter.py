"""E33 — gộp nhiều chapter vào MỘT file xuất.

## Vì sao

Bốn phần của luồng tự động đã có từ trước (tải nhiều ảnh, tự nhận diện, năm bước nối nhau, chạy cả
chapter một mẻ). Gộp chapter là **thứ duy nhất thật sự thiếu** — kiểm kê 12-09.

## Hai thứ phải làm đúng, và cả hai đều dễ làm sai âm thầm

**1. Tên file trong archive không được trùng.** Mỗi chapter đều có trang 1. Đổ thẳng vào một
archive thì trang 1 của chapter sau **ghi đè** trang 1 của chapter trước — và `zipfile` không báo
lỗi, nó chỉ lặng lẽ tạo hai entry cùng tên mà phần lớn ứng dụng đọc truyện chỉ thấy một. Mất trang
mà không ai biết. Nên tên phải mang **số thứ tự chapter**.

**2. Thứ tự phải theo đúng lựa chọn của người dùng, không theo id hay theo tên.** Gộp chapter 3 rồi
chapter 1 ra file khác hẳn gộp 1 rồi 3. Ứng dụng đọc truyện sắp trang theo **tên file**, nên thứ tự
phải nằm trong tên chứ không chỉ nằm trong thứ tự ghi vào archive.

## Tên trang trong archive do `ChapterExporter.ten_trang` ghép

Module này chỉ sinh **tiền tố chapter**; việc ghép `tiền tố + số trang` nằm ở `ten_trang` của bộ
xuất. Cố ý không tự ghép tên đầy đủ ở đây: bộ xuất đã là chỗ duy nhất quyết định tên trang (nó
tính độ rộng chữ số theo tổng số trang), và có hai chỗ đặt tên là sớm muộn hai chỗ lệch nhau.

## Vì sao đánh số chapter chứ không dùng tên chapter làm thư mục

Tên chapter do người dùng đặt, có thể trùng nhau, có thể rỗng sau khi lọc ký tự lạ. Số thứ tự thì
luôn duy nhất và luôn sắp đúng. Tên chapter vẫn được đưa vào **sau** số, để người mở file còn nhận
ra đó là chapter nào.
"""
from __future__ import annotations

from app.services.export.naming import slugify

#: Bao nhiêu chữ số cho phần chapter. 2 chữ số đủ cho 99 chapter một lần gộp; vượt thì tự nới ra
#: theo số lượng thật, chứ không cắt bớt thành tên trùng.
SO_CHU_SO_CHAPTER = 2


def tien_to_chapter(vi_tri: int, ten_chapter: str, tong_so: int) -> str:
    """`(1, "Chương Một", 3)` -> `01_chuong_mot`.

    `vi_tri` đếm từ 1 theo ĐÚNG thứ tự người dùng chọn.
    """
    rong = max(SO_CHU_SO_CHAPTER, len(str(max(tong_so, 1))))
    return f"{vi_tri:0{rong}d}_{slugify(ten_chapter)}"


def kiem_thu_tu(ids: list, chinh) -> list:
    """Chuẩn hoá danh sách chapter cần gộp: bỏ trùng, GIỮ thứ tự, bảo đảm có chapter chính.

    Bỏ trùng mà giữ thứ tự lần xuất hiện ĐẦU: người dùng chọn trùng là nhầm tay, và nếu để nguyên
    thì trang của chapter đó bị xuất hai lần với hai tiền tố khác nhau.

    Chapter chính (`ExportJob.project_id`) luôn phải có mặt — nó là chỗ nghẽn kiểm quyền, nên một
    danh sách không chứa nó là danh sách chưa được kiểm quyền đầy đủ.
    """
    ra: list = []
    for i in list(ids or []):
        if i not in ra:
            ra.append(i)
    if chinh is not None and chinh not in ra:
        ra.insert(0, chinh)
    return ra
