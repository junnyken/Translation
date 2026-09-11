# Báo cáo Mini-Spec E26 — Sửa chất lượng dịch (A + B + C)

**Project:** Translation · **Phase:** E · **Ngày:** 2026-09-11
**Nền:** `69b475b` (sau E16 LIVE)
**Trạng thái:** **A + B + C xong + đo trước/sau** · **D (dịch theo ngữ cảnh) chưa làm** — §7

## 1. Summary

Lượt kiểm dịch (EN/JA × màu/trắng đen, so với bản `vi` **do người dịch** của Pepper&Carrot) tìm ra
ba lỗi. E26 sửa cả ba.

Phát hiện quan trọng nhất của phần audit: **ba trong bốn hạ tầng cần dùng đã có sẵn**, chỉ là chưa
được nối vào đúng chỗ.

| Hạ tầng | Trạng thái trước E26 |
|---|---|
| Dịch theo ngữ cảnh cả trang | **ĐÃ CÓ** — `llm_context`, prompt viết đúng yêu cầu |
| Cờ vùng chồng lấn | **ĐÃ CÓ và gắn đúng** — `overlap_suspect=true` trên đúng 4 vùng lỗi |
| Phân loại SFX | **ĐÃ CÓ** — `RegionRelevance.possible_sfx` |
| Gộp dòng trước khi dịch | **KHÔNG CÓ** |

## 2. A — gộp dòng trước khi dịch

### 2.1 Lỗi

Dấu xuống dòng trong `raw_text` là **chỗ chữ ngắt dòng trong bong bóng**, không mang nghĩa. Nhưng
nó được truyền thẳng cho bộ dịch (`tasks.py:1069` → `1086`, không có chỗ nào gộp), và Google
Translate coi mỗi dòng là một câu riêng. **7/14 vùng** của trang đo là nhiều dòng.

### 2.2 Đo trước/sau trên chữ THẬT — 6/7 tốt lên

| Gốc | TRƯỚC | SAU |
|---|---|---|
| `... to name just\na few!` | `... chỉ kể tên thôi\nmột vài!` — vô nghĩa | `... chỉ kể tên một vài!` |
| `I need to go to the\nmarket in Komona.` | `Tôi cần phải đi đến\nchợ ở Komona.` | `Tôi cần đi chợ ở Komona.` |
| `私はコモナの市場に\n行かねばならぬ` | `Tôi đang ở chợ ở Komona\nphải đi` — **SAI NGHĨA** | `Tôi phải đi chợ ở Komona.` |
| `私がいない間に\nすべて片付けるのだ` | `trong khi tôi đi vắng\nDọn dẹp mọi thứ` — **đảo thứ tự** | `Dọn dẹp mọi thứ khi tôi đi vắng.` |
| `"A-true-witch-of-Chaosah..."` | `...của Hỗn loạn...` — dịch cả **tên riêng** | `...Chaosah...` giữ tên |
| `Exactly.\nAs well it should be.` | giữ nguyên | **giữ nguyên** ✓ |

Hai ca tiếng Nhật nặng nhất: ngắt dòng làm **đảo thứ tự mệnh đề**, ra nghĩa khác hẳn.

Ca cuối **không đổi**, và đó là bằng chứng luật ranh giới câu chạy đúng chứ không phải nó gộp bừa.

### 2.3 Hai quyết định

**KHÔNG sửa `raw_text` trong CSDL.** E21 cho người dùng gõ đè nó; đổi ở đây là phá hợp đồng đó và
làm họ thấy chữ khác cái đã gõ. Việc gộp chỉ xảy ra **trên đường gửi đi dịch**. Bước căn chữ vốn tự
ngắt dòng lại theo khung nên không mất gì.

**GIỮ dấu xuống dòng ở ranh giới câu thật** (dòng kết thúc bằng `.` `!` `?` `:` `;` `…` và bản
full-width). Gộp cả những chỗ đó thì hai câu rời dính thành một, và bộ dịch mất đúng thông tin nó
cần để chấm câu.

**Nối bằng DẤU CÁCH**, không nối liền: chữ Latin ngắt dòng cần dấu cách (`just` + `a few`), nếu
không thành từ không tồn tại (`justa`). Với tiếng Nhật thì dấu cách là dư nhưng **vô hại**. Sai một
chiều vô hại, sai chiều kia hỏng nghĩa ⇒ chọn chiều vô hại.

Sửa ở **cả hai** đường dịch: cả trang (`_run_translate`) và dịch lại một vùng
(`_run_region_retranslate`). Hai đường xử lý khác nhau thì bấm "dịch lại vùng" sẽ ra kết quả khác
lượt tự động trên cùng chữ đó.

## 3. B — không chèn chữ lên vùng BAO

### 3.1 Lỗi, và một chỗ tôi tra sai lúc đầu

Trang `en_E12P01` cho 14 vùng, trong đó một vùng `400,41 285x228` **chứa trọn** hai vùng khác và
lặp lại nội dung của chúng ⇒ cùng một câu bị vẽ **hai lần chồng nhau**. Chính vùng bao đọc sai
nhiều nhất (`Luughing Fotlons`) vì nó gộp năm nhãn vào một khối.

Lúc đầu tôi tra cột `text_region.status` và kết luận *"luật chồng lấn không bắt được"*. **Sai** —
`overlap_suspect` là **cột riêng**, và nó đã gắn đúng:

```
overlap_suspect = true trên ĐÚNG 4 vùng có vấn đề của trang đó · 13 vùng trên cả 24 trang
overlap_ratio(#2, #4) = 1.000   (ngưỡng 0.8)
```

Nên lỗi **không phải** "không phát hiện được" mà là **"đã gắn cờ nhưng không ai dùng cờ đó"** — và
docstring của M2 nói rõ đó là chủ đích: *"Chỉ GẮN CỜ, không merge/xóa box nào"*.

### 3.2 Bản sửa — không xoá gì

Vùng chứa trọn **≥2** vùng khác **nhỏ hơn hẳn** thì bỏ qua khi **vẽ**. Dòng dữ liệu, kết quả OCR,
cờ rà soát đều còn nguyên — đúng nguyên tắc E12 *"máy không được kết luận một vùng là rác rồi tự
bỏ"*.

**Điều kiện "≥2" là chốt chặn.** Chỉ dựa vào `overlap_suspect` sẽ bỏ oan một bong bóng lớn hợp lệ
chỉ vì nó chồng nhẹ một vùng khác. Một bong bóng thật không chứa trọn hai bong bóng khác.

**Chỉ tính vùng con NHỎ HƠN hẳn**: nếu không, hai box gần trùng nhau sẽ coi nhau là con của nhau và
cả hai cùng bị bỏ ⇒ **mất chữ**. Có test riêng cho ca này.

### 3.3 KHÔNG sửa được ca tiếng Nhật

Bản tiếng Nhật của cùng trang đó bị **gộp ngược lại**: 4 nhãn thuốc nằm trong **một** vùng, nên
`笑い薬` + `超毛生え薬` dịch nhập thành `Thuốc cười siêu mọc tóc` — một nghĩa không tồn tại. Ở đây
không có vùng nhỏ nào để ưu tiên, nên B không giúp gì. Đó là giới hạn của bộ nhận diện.

## 4. C — giữ nguyên chữ cho SFX

### 4.1 Lỗi

`Clang` → `Kêu vang`, `Cling` → `Bám vào`, `Clong` → `tiếng kêu`. Dịch **đúng từ điển nhưng sai thể
loại**: đó là tiếng kim loại chạm nhau, không phải động từ.

### 4.2 CHỈ dùng cờ của E12, KHÔNG tự suy thêm

Toàn bộ 13 chữ bị E12 gắn `possible_sfx` trên 24 trang thật:

```
CC · Pam · 音全。 · Bam · SXXX · Boom · Grrrr · Grrr! · Poof! · Cling · Clong · Pfff! · Clang
```

**13/13 đều là tiếng động hoặc nhiễu OCR, không một cái nào là thoại.**

Tôi **cố ý không** thêm luật tự suy (chữ ngắn / nghiêng / ngoài bong bóng): một dương tính giả sẽ
để **thoại thật không được dịch**, tức người đọc mất cả câu — tệ hơn hẳn một SFX dịch sai mà họ vẫn
hiểu là tiếng động. Sai một chiều mất cả câu, sai chiều kia chỉ lạ một từ.

### 4.3 Lớp dương tính giả CÓ THẬT, ghi rõ chứ không giấu

`possible_sfx` được gán **thuần theo độ dài** (`so_ky_tu_goc <= 5`), không theo dấu hiệu tiếng động.
Chính comment trong `assessor.py:183` viết *"`NO!` là thoại"* — tức tác giả đã biết. Nên thoại rất
ngắn (`NO!`, `Yes!`) sẽ bị giữ nguyên.

Đo được: **0/13 ca sai** trên dữ liệu thật. Rủi ro là lý thuyết, nhưng nó có thật và
`e26_giu_nguyen_sfx=false` tắt được.

**Và nó bỏ sót 3/6 SFX**: `Shhshh`, `Shklak!`, `CRACK!!\nKLING!!` bị E12 gắn `likely_translatable`
nên vẫn bị dịch như cũ. Cơ chế này cải thiện 3/6 và **không phá ca nào** — đừng đọc nó thành "đã xử
lý xong SFX".

### 4.4 Chỗ dễ vỡ nhất không phải việc nhận SFX

Mà là **ghép kết quả về đúng thứ tự** sau khi loại phần tử khỏi danh sách gửi dịch. Lệch một chỉ số
là gán bản dịch của vùng này cho vùng khác — lỗi im lặng, ảnh không hỏng mà nội dung sai hết. Có 7
test riêng cho việc ghép (SFX ở đầu / giữa / cuối / liên tiếp / tất cả / không có).

## 5. Một test đỏ, và vì sao tôi sửa fixture chứ không nới assertion

`test_dich_lai_duoc_ca_trang_sau_khi_da_canh_chu` đỏ sau khi thêm C. Truy ra: fixture dùng chữ
`"TRAI"` / `"PHAI"` (4 ký tự) ⇒ sau khi `run_typeset_job` chạy bộ chấm E12, cả hai bị gắn
`possible_sfx` ⇒ E26-C giữ nguyên chúng ⇒ không mang tiền tố.

Mục đích thật của test là *"trang đã canh chữ phải dịch lại được"* — độ dài chữ chỉ là chi tiết
tình cờ. Nên tôi đổi fixture sang chữ dài thực tế, **giữ nguyên assertion mạnh** (MỌI vùng phải
dịch lại), thay vì nới assertion thành "một số vùng".

Test này cũng là bằng chứng lớp dương tính giả ở §4.3 là thật: `TRAI`/`PHAI` là hai từ có nghĩa.

## 6. Changed Files

| Tệp | Việc |
|---|---|
| `backend/app/services/translate/gop_dong.py` | **MỚI** — A |
| `backend/app/services/typeset/vung_bao.py` | **MỚI** — B |
| `backend/app/services/translate/sfx.py` | **MỚI** — C |
| `backend/app/workers/tasks.py` | Nối cả ba vào đúng chỗ |
| `backend/app/core/config.py` | `e26_bo_qua_vung_bao`, `e26_giu_nguyen_sfx` |
| `backend/tests/test_e26_gop_dong_unit.py` | **MỚI** — 18 test |
| `backend/tests/test_e26_vung_bao_unit.py` | **MỚI** — 11 test |
| `backend/tests/test_e26_sfx_unit.py` | **MỚI** — 14 test |
| `backend/tests/test_translate_task_integration.py` | Sửa fixture (§5) |

Không migration. Không đổi enum. Không đổi hợp đồng API. Không đổi `raw_text` trong CSDL.

## 7. D — dịch theo ngữ cảnh: CHƯA LÀM, và vì sao

Yêu cầu của người dùng (*"phải dịch sát nghĩa, dựa ngữ cảnh để diễn đạt"*) **đã được xây sẵn** ở
`llm_context`. Prompt của nó viết đúng nguyên văn:

> *"Dịch theo mạch văn của cả trang, không dịch rời rạc từng dòng"*
> *"Bám sát nghĩa gốc… Chỉ được đổi CÁCH DIỄN ĐẠT cho tự nhiên bằng tiếng Việt, không đổi Ý"*
> *"Giữ giọng điệu nhân vật"*
> *"Đầu vào là chữ do OCR đọc nên có thể sai chính tả; tự suy luận và sửa khi dịch"*

Dòng cuối còn xử lý luôn lỗi OCR kiểu `Luughing Fotlons`.

**Chưa bật vì hai điều cần người dùng quyết:**
1. Production đã cấu hình khoá Gemini chưa (`/api/v1/batch-config` đòi đăng nhập, tôi không đọc được).
2. `google_fast` miễn phí, `llm_context` **tốn token mỗi trang**.

## 8. Tests

```
$ pytest tests/test_e26_*.py -q                        43 passed
$ pytest tests/test_translate_task_integration.py -q   14 passed
$ pytest -q -p no:randomly                           1368 đạt · 6 bỏ qua · 0 ĐỎ
```

## 9. Remaining Limits

- **Chưa chạy lại cả 4 tổ hợp qua pipeline thật** sau khi sửa — mới đo A trên chữ thật ở tầng
  service. B và C mới có unit test, chưa có bằng chứng end-to-end trên trang thật.
- **Chưa deploy.**
- C bỏ sót 3/6 SFX (§4.3) và có lớp dương tính giả lý thuyết với thoại ≤5 ký tự.
- B không giúp được ca gộp-ngược của tiếng Nhật (§3.3).
- Bộ mẫu vẫn là 2 trang, 1 chapter, 1 tác giả — đủ tìm lỗi, chưa đủ đo tỉ lệ.
