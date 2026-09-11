# Báo cáo Mini-Spec E26 — Sửa chất lượng dịch (A + B + C)

**Project:** Translation · **Phase:** E · **Ngày:** 2026-09-11
**Nền:** `69b475b` (sau E16 LIVE)
**Trạng thái:** **LIVE** — `translation-api` v61, build từ `1656eb1a` (khớp HEAD), 11/11 chặng.
A+B+C có bằng chứng end-to-end (§7b) · D đã ĐO và thắng rõ (§7) · production **ĐÃ có khoá Gemini**
(`/healthz` trả `llm_configured: true`) nên "Dịch theo ngữ cảnh" bấm được ngay.

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

### 3.3 KHÔNG sửa được ca tiếng Nhật — và cơ chế thật khác điều tôi viết lúc đầu

Bản tiếng Nhật của cùng trang bị **gộp ngược lại**: 4 nhãn thuốc nằm trong **một** vùng, nên
`笑い薬` + `超毛生え薬` ra `Thuốc cười siêu mọc tóc` — một nghĩa không tồn tại. B không giúp được vì
ở đây **không có vùng nhỏ nào** để ưu tiên.

Lúc đầu tôi viết thêm rằng nguyên nhân là *"4 nhãn nằm trong một vùng"* và dừng ở đó. Đo lại
(§7.3) thì **cơ chế cụ thể khác**, và chỗ khác đó quyết định cách chữa:

```
'笑い薬\n超毛生え薬…'  (CÓ xuống dòng)  -> 'thuốc cười\nthuốc mọc tóc siêu tốc\n…'   ĐÚNG
'笑い薬超毛生え薬'      (KHÔNG dấu tách) -> 'Thuốc cười siêu mọc tóc'                 SAI
'笑い薬 超毛生え薬'     (dấu cách)       -> 'Thuốc cười siêu mọc tóc'                 VẪN SAI
```

Tức OCR đọc dính **không có dấu tách nào**, và Google nuốt chuỗi kanji liền thành một từ ghép.
**Gộp dòng (A) không cứu được, thêm dấu cách cũng không** — tôi đã thử cả hai.

Cái cứu được là **D**: `llm_context` cho `Thuốc cười, thuốc mọc tóc siêu tốc.` trên đúng chuỗi
dính đó. Nên ca này không phải "giới hạn không vá được" như tôi viết ban đầu — nó là ca mà A và B
đều bó tay còn D thì vá được.

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

## 7. D — dịch theo ngữ cảnh: ĐÃ ĐO, và nó thắng rõ

Yêu cầu của người dùng (*"phải dịch sát nghĩa, dựa ngữ cảnh để diễn đạt"*) **đã được xây sẵn** ở
`llm_context`. Prompt của nó viết đúng nguyên văn:

> *"Dịch theo mạch văn của cả trang, không dịch rời rạc từng dòng"*
> *"Bám sát nghĩa gốc… Chỉ được đổi CÁCH DIỄN ĐẠT cho tự nhiên bằng tiếng Việt, không đổi Ý"*
> *"Giữ giọng điệu nhân vật"*
> *"Đầu vào là chữ do OCR đọc nên có thể sai chính tả; tự suy luận và sửa khi dịch"*

Thay vì hỏi rồi chờ, tôi **đo** — cùng một trang thật, cùng đường đi production (có A và C), hai
bộ dịch.

### 7.1 Chất lượng — trang EN thật `0d47b661`, 14 vùng, khác nhau 11/11

| Gốc | `google_fast` | `llm_context` |
|---|---|---|
| `Luughing Fotlons …` | *Luughing Fotlons* — **để nguyên rác OCR** | **`Thuốc Cười`** — tự suy ra |
| `"Bright-Side" Potions` | *Độc dược "Bright-Side"* — **bỏ tiếng Anh** | **`Thuốc "Lạc Quan"`** |
| `Mega-Hairgrowth` (#2) | *mọc tóc **cực mạnh*** | `Mọc Tóc Siêu Tốc` |
| `Mega-Hairgrowth` (#3) | *mọc tóc **siêu lớn*** ⇒ **KHÔNG NHẤT QUÁN** | `Mọc Tóc Siêu Tốc` ⇒ **nhất quán** |
| `Make all this disappear…` | *…biến mất khi tôi đi vắng;\n**S**ẽ không tốt nếu…* | *Dọn sạch đống này đi khi tôi vắng mặt; để mấy đứa nhóc nghịch ngợm…* |

Ca `Luughing Fotlons` chính là **Lỗi #1** của lượt kiểm dịch — thứ tôi đã xếp vào "giới hạn của bộ
đọc chữ". Hoá ra prompt đã xử lý nó từ đầu.

Cột nhất quán mới là lợi ích **chỉ ngữ cảnh cả trang mới cho được**: google dịch cùng một cụm
thành hai kiểu khác nhau ở hai vùng, vì nó không biết hai vùng đó cùng một trang.

### 7.2 Tiếng Nhật — giọng nhân vật, thứ không đo được bằng "đúng/sai"

| Gốc | `google_fast` | `llm_context` |
|---|---|---|
| `私はコモナの市場に 行かねばならぬ` | *Tôi phải đi chợ ở Komona.* | ***Ta** phải đến chợ Komona ngay.* |
| `私がいない間に すべて片付けるのだ` | *Dọn dẹp mọi thứ khi tôi đi vắng.* | *Trong lúc **ta** vắng mặt, hãy dọn dẹp hết chỗ này đi.* |
| `その通り。\nそうあるべきじゃ。` | *đúng rồi.\nĐó là cách nó nên được.* | *Đúng vậy. Phải làm thế mới được.* |

`ならぬ` / `のだ` / `じゃ` là văn cổ, giọng bề trên. Google trả về *"Tôi"* trung tính — **không sai
nghĩa nhưng mất giọng**. LLM chọn *"Ta"*, đúng nhân vật phù thuỷ dạy việc. Đó là dòng prompt *"giữ
giọng điệu nhân vật"* chạy thật.

Ca thứ ba cho thấy google dịch từng dòng rời ra một câu tiếng Việt không ai nói.

> Chữ tiếng Nhật ở đây là **chữ ghi lại** trong lượt kiểm trước, không phải trang đang nằm trong
> CSDL này — CSDL local không có project tiếng Nhật nào. Nói rõ để không ai đọc nhầm thành một
> lượt chạy end-to-end.

### 7.3 Và D vá đúng chỗ B chịu thua — xem §3.3

```
'笑い薬超毛生え薬'  google_fast -> 'Thuốc cười siêu mọc tóc'          (tái hiện ĐÚNG lỗi gốc)
'笑い薬超毛生え薬'  llm_context -> 'Thuốc cười, thuốc mọc tóc siêu tốc.'
```

### 7.4 Chi phí — số đo, không phải ước lượng

```
trang EN 14 vùng (gửi đi 11, giữ 3 SFX) : 553 token
4 dòng tiếng Nhật                        : 315 token
google_fast                              : không có token (miễn phí)
```

⇒ một chapter 24 trang ≈ **13 000 token**. `thinking_budget=0` nên không đốt token suy nghĩ (M5 đo
938 → 0 mà chất lượng không đổi).

**Tôi KHÔNG quy ra tiền**: đơn giá `gemini-3.1-flash-lite` là thứ tôi không kiểm chứng được ở đây,
và bịa một con số đô la còn tệ hơn không đưa số nào.

### 7.5 Vì sao bật được mà không sợ — đo, không suy luận

Câu hỏi tôi treo lúc đầu (*"production đã có khoá chưa"*) hoá ra **không còn chặn**, vì trường hợp
xấu nhất đã được đo:

```
get_translator('llm_context', api_keys=[])   -> dựng được, KHÔNG ném
    .translate([...])                        -> QuotaExhausted('… GEMINI_API_KEYS rỗng')
_run_translate  except (QuotaExhausted, TranslationFailed) -> lùi google_fast + fallback_used
```

Hai mệnh đề này **mong manh và kéo ngược chiều nhau**: `build_translator` được gọi **NGOÀI** khối
try (`tasks.py:1094`), nên chỉ cần nó ném lúc dựng là mất hẳn đường lùi; và lỗi phải đúng loại
`QuotaExhausted`. Test cũ chỉ canh đường lùi bằng **translator giả tự ném** — không canh được đường
thật. Nay có `test_d_khoa_rong_van_co_duong_lui_unit.py` (7 test) canh cả hai, **kể cả đọc thẳng
mã nguồn** khối except để ai đổi nó là đỏ.

⇒ **Khoá rỗng thì tệ nhất là đúng hành vi hôm nay, có dán nhãn.** Không có ca nào hỏng thêm.

### 7.6 Việc đã làm cho D, và việc CỐ Ý không làm

**Đã làm** — `/healthz` nay trả `llm_configured` (§API.md). Trước đó muốn biết production bật được
LLM chưa thì phải đăng nhập gọi `/batch-config`; và bảng biến môi trường của nền tảng hosting chỉ
liệt kê **tên** biến, không nói biến **rỗng hay không** — `GEMINI_API_KEYS` có tên ở đó nhưng đó
không phải bằng chứng nó có giá trị. Trường mới nói đúng sự khác nhau đó, chỉ `true`/`false`, có
test soi rò rỉ cả khoá lẫn tiền tố `AIza`.

**CỐ Ý không làm** — không tự đổi `TRANSLATE_DEFAULT_ENGINE` trên production. Không phải vì rủi ro
kỹ thuật (§7.5 cho thấy tệ nhất là hoà), mà vì nó **tiêu quota/tiền của người dùng cho mọi trang
của mọi người**, và đó là quyết định của họ chứ không phải của tôi.

**Và hoá ra cũng không cần đổi**: `BatchPanel.jsx:146` đã có sẵn ô chọn bộ dịch, mục `llm_context`
tự bật khi `llm_configured` đúng. Người dùng chọn được **theo từng mẻ** — ai muốn dịch kỹ thì
chọn, ai không thì thôi, không ai bị ép tốn token. Đó là cách bật đúng hơn hẳn một cờ toàn cục.

## 7b. Live Verification — end-to-end trên trang THẬT (local)

§9 bản đầu ghi *"B và C mới có unit test, chưa có bằng chứng end-to-end"*. Đã chạy, và nó tìm ra
thêm một giới hạn mà unit test không thấy được.

Chạy lại `_run_translate` + `_run_typeset` trên đúng trang `0d47b661` (14 vùng).

### A và C — xác nhận bằng dữ liệu ra

| Vùng | TRƯỚC (lần chạy cũ) | SAU |
|---|---|---|
| `756e89d8` | `Tôi cần phải đi đến / chợ ở Komona.` | `Tôi cần đi chợ ở / Komona.` |
| `4b8c6563` | `... chỉ kể tên thôi / một vài!` | `... chỉ kể tên một / vài!` |
| `cd115254` | `…thực sự của **Hỗn loạn**…` | `…thực sự của **Chaosah**…` |
| `5ea82bf8` | `Bám / vào` | **`Cling`** |
| `34a57f8b` | `Kêu / vang` | **`Clang`** |
| `7ed91cf0` | `tiếng kêu` | **`Clong`** |

### B — và một chỗ tôi suýt kết luận sai

Lần đo đầu tôi đếm số dòng `TypesetResult` và thấy **14/14**, suýt kết luận B không chạy. **Đo
nhầm thứ**: B lọc ở danh sách **vẽ lên ảnh** (`ve`), không đụng dòng dữ liệu — đúng như thiết kế
§3.2 *"không xoá, chỉ không vẽ"*. Dòng `TypesetResult` còn nguyên là ĐÚNG, không phải lỗi.

Đo đúng chỗ thì log nói thẳng:

```
typeset trang 0d47b661…: bỏ qua 1 vùng BAO (chứa trọn >=2 vùng khác): ['b8b24333']
```

Đúng một vùng, đúng vùng bao đã xác định ở §3.1.

### So ảnh thật, bật/tắt cờ trên cùng một trang

Dựng ảnh đối chứng bằng `E26_BO_QUA_VUNG_BAO=false` rồi bật lại:

| | Vùng nhãn thuốc (crop 380,10–700,290) |
|---|---|
| **Tắt cờ** | cả khối `LUUGHING FOTLONS / THUỐC MỌC TÓC CỰC MẠNH…` của vùng bao **đè lên mọi thứ** — không đọc được chữ nào |
| **Bật cờ** | khối rác đó **biến mất**; các nhãn con đọc được |

### GIỚI HẠN MỚI mà chỉ ảnh mới lộ ra

Ảnh "sau" **vẫn còn một cặp chữ chồng nhau**: `ĐỘC DƯỢC KHÓI..` (thuộc `e8e30ad4`) và
`THUỐC KHÓI...` (thuộc `6aaf8a55`) là **cùng một câu gốc vẽ hai lần**.

B không bắt được vì cặp này thua cả hai điều kiện:

```
e8e30ad4 (421,159 250x72) chứa 6aaf8a55 (452,211 215x29) ~68.6%  < ngưỡng 0.9
và chỉ có 1 vùng con                                             < tối thiểu 2
```

Nới ngưỡng hay hạ tối thiểu xuống 1 thì **bỏ oan bong bóng thật** — đúng ca
`test_chua_TRON_mot_vung_thoi_cung_KHONG_du`. Nên đây là chỗ **cố ý chưa vá**, không phải chỗ bỏ
sót: cần một dấu hiệu khác (vd trùng nội dung sau khi dịch), và nó phải có bằng chứng riêng.

⇒ B **giảm hẳn** chồng chữ trên trang này nhưng **không xoá hết**. Đừng đọc nó thành "đã xử lý
xong chồng lấn".

## 8. Tests

```
$ pytest tests/test_e26_*.py -q                        43 passed
$ pytest tests/test_translate_task_integration.py -q   14 passed
$ pytest -q -p no:randomly                           1368 đạt · 6 bỏ qua · 0 ĐỎ
```

## 9. Remaining Limits

- **Chưa chạy lại cả 4 tổ hợp qua pipeline thật** sau khi sửa. A, B, C đã có bằng chứng
  end-to-end trên **một** trang EN thật (§7b); ba tổ hợp còn lại (JA màu, JA trắng đen, EN trắng
  đen) thì chưa.
- **B giảm chồng chữ nhưng KHÔNG xoá hết** (§7b): cặp `e8e30ad4`/`6aaf8a55` vẫn vẽ trùng vì chứa
  nhau 68.6% (< 0.9) và chỉ 1 vùng con (< 2). Cố ý chưa vá — nới ngưỡng là bỏ oan bong bóng thật.
- ~~Chưa deploy~~ → **ĐÃ LIVE** `translation-api` v61, build từ `1656eb1a`. `/healthz` trả
  `llm_configured: true` ⇒ production **có** khoá Gemini, "Dịch theo ngữ cảnh" dùng được ngay.
  §7.5 (khoá rỗng vẫn lùi được) vẫn là bằng chứng phải có: nó canh ca khoá bị gỡ/hết hạn sau này.
- **Chưa tự đổi `TRANSLATE_DEFAULT_ENGINE` trên production** — cố ý, §7.6. Và **tôi không biết giá
  trị hiện tại của nó**: bảng biến môi trường chỉ liệt kê TÊN, không trả giá trị. Không đoán. Ô
  chọn theo từng mẻ là đường chắc chắn, nên D không bị chặn bởi việc này.
- **Chưa kiểm thị giác TRÊN production.** Bằng chứng ảnh của B là ở local; kiểm trên production đòi
  tải một chapter test lên đó.
- C bỏ sót 3/6 SFX (§4.3) và có lớp dương tính giả lý thuyết với thoại ≤5 ký tự.
- B không giúp được ca gộp-ngược của tiếng Nhật — nhưng **D thì có** (§3.3, §7.3).
- Chưa quy chi phí ra tiền (§7.4): có số token đo được, không có đơn giá kiểm chứng được.
- **Chưa đo `llm_context` trên nhiều trang liên tiếp.** Cả hai phép đo đều là một trang / vài dòng.
  Nhất quán thuật ngữ **giữa các trang** của cùng chapter thì `llm_context` không giải quyết được:
  nó gộp ngữ cảnh trong **một trang**, không phải cả chapter. Muốn nhất quán xuyên trang thì đó là
  việc của bảng thuật ngữ (E17), không phải của D.
- Bộ mẫu vẫn là 2 trang, 1 chapter, 1 tác giả — đủ tìm lỗi, chưa đủ đo tỉ lệ.
