# Báo cáo Mini-Spec P3c — Dò năng lực lưu trữ VibeHost

**Ngày:** 2026-08-31 · **Trạng thái:** ✅ **HOÀN TẤT** — câu hỏi đã có lời đáp dứt khoát
**Phụ thuộc:** P3a `BLOCKED` · P3b `BLOCKED` · hosted web v13 / API v22
**Phạm vi:** chỉ đọc. Không sửa mã, không đổi cấu hình, không deploy, không tạo/xoá gì.

## Câu hỏi P3b đặt ra

> Gói Vibe Host Pro có cấp được volume bền (persistent disk) gắn vào đường tuỳ ý — cụ thể là
> `/app/storage` của `translation-api` — không?

## Trả lời: **KHÔNG.**

Và điểm quan trọng hơn: **đây không phải chuyện thiếu quyền của khoá tôi đang dùng.** P3b chỉ
chứng minh được *"tôi không có công cụ lẫn quyền"*. P3c chứng minh **nền tảng không có khái niệm
đó trong mô hình tài nguyên** — bằng 4 trục bằng chứng độc lập.

---

## §1 — Đính chính: P3b dò nhầm tài khoản

Trước khi vào bằng chứng, phải nói rõ một chuyện.

Workspace có **4 cổng MCP Vibe Host**, và chúng là **3 tài khoản khác nhau**:

| Cổng MCP | Tài khoản | Dịch vụ | Lưu trữ | Có Translation? |
|---|---|---|---|---|
| `vibehost` | `trieunt2@matbao.com` | 3 | 9,03 GB | ❌ chỉ voxdub |
| `vays2` | `trieunt2@matbao.com` *(trùng)* | 3 | 9,03 GB | ❌ chỉ voxdub |
| `vays` | `trieunt@matbao.com` | 5 | 1,96 GB | ❌ không có |
| **`vibehost1`** | **`trieunt1@matbao.com`** | **4** | **1,26 GB** | ✅ **api v22 + web v13** |
| `vibehost-new` | — | — | — | ⚠️ lỗi xác thực 401, không kết nối được |

Translation nằm ở **`vibehost1`**. Con số P3b ghi lại (*"4 dịch vụ · 1,77 GB"*) khớp tài khoản
này về số dịch vụ, nên P3b **có** dò đúng chỗ — nhưng báo cáo không ghi lại là cổng nào, và với
4 cổng trỏ 3 tài khoản thì đó là một cái bẫy chờ sẵn cho lần sau. Nay đã ghi.

`translation-api` = `cmtcexscl005o0i5fusbnfwwc` · `translation-web` = `cmtcg12h500kq0i5f9q3fxt3t`

---

## §2 — Bốn trục bằng chứng

### Trục 1 — Không khoá nào trong cả 4 tài khoản có phạm vi lưu trữ

Cả 4 cổng trả về **đúng cùng một bộ**:

```
scopes: ["read", "deploy", "runtime:write", "env:write"]
```

Không có `storage:*`, `volume:*`, `disk:*`. P3b nói *"khoá tôi không có quyền"*; đo 4 tài khoản
độc lập cho thấy **không khoá nào có**, nên đây không phải hạn chế riêng của một khoá.

### Trục 2 — `appdata = 0 byte` trên **cả 4** tài khoản

```
trieunt@  : appdata 0    (5 dịch vụ)
trieunt1@ : appdata 0    (4 dịch vụ)  <- Translation ở đây
trieunt2@ : appdata 0    (3 dịch vụ)
```

Tổng **12 dịch vụ đang chạy thật, không dịch vụ nào từng cấp phát 1 byte `appdata`.**

P3b coi việc `storageBreakdownBytes` **có** mục `appdata` là manh mối tích cực ("nền tảng có khái
niệm này"). Đo rộng ra thì manh mối đó **yếu đi rõ rệt**: hạng mục tồn tại trong **sổ kế toán**
lưu trữ, nhưng không dịch vụ nào trong cả đội hình chạm tới nó. Có ô để ghi, không có đường để đổ
dữ liệu vào.

### Trục 3 — Mô hình tài nguyên **không có chiều "đĩa"**

`get_resources` trên `translation-api` trả về **đúng** các trường sau:

```json
{ "currentCpu": 1.6, "currentRamMB": 4096,
  "minCpu": 0.1, "minRamMB": 64,
  "maxCpu": 2.6, "maxRamMB": 5376,
  "freeCpu": 2.6, "freeRamMB": 5376 }
```

Chỉ **CPU và RAM**. Không có `disk`, `volume`, `storageMB` — kể cả ở dạng min/max/free. Và
`set_resources` chỉ nhận `cpu` + `ram`.

⇒ **Không có nút nào để vặn**, chứ không phải có nút mà tôi bị khoá tay.

### Trục 4 — Không công cụ ghi nào nhận khai báo volume, **kể cả lúc tạo mới**

`create_project` — thời điểm duy nhất có thể khai báo hạ tầng cho một website — nhận đúng:

```
name, subdomain, cpu, ram, repoUrl | html, gitBranch, subdir
```

Không có trường volume/mount/disk. **Sinh ra đã không có volume thì sau này không gắn thêm được.**

Quét toàn bộ **20 công cụ** của cổng: không có `create_volume`, `attach_volume`, `list_volumes`,
và cũng **không có `create_stack`**.

Lối thoát cuối cùng đáng cân nhắc là **cụm docker-compose** — vì compose tự khai báo volume trong
tệp, không cần công cụ MCP nào. Nhưng:

- `list_stacks` trả `[]` trên **cả** `vibehost1` **lẫn** `vibehost` → không tài khoản nào có cụm;
- chỉ có `deploy_stack` / `get_stack` / `power_stack` (thao tác lên cụm **đã tồn tại**), **không
  có đường tạo cụm mới** qua API;
- `translation-api` là `sourceType: "git-url"` — website đơn, không phải cụm.

⇒ Đường compose **không với tới được** từ bề mặt này.

---

## §3 — Phát hiện mới: nền tảng **có** lưu trữ bền, chỉ là không phải hệ tệp

Đây là thứ P3b không nêu, và nó đổi hẳn hình dạng của việc kế tiếp.

`get_project` trên `translation-api` trả về:

```json
"databases": [
  { "name": "translation-api-db", "type": "postgresql", "status": "online", "origin": "primary" },
  { "name": "redis-instance",     "type": "redis",      "status": "online", "origin": "verified" }
]
```

Và `whoami` tách bạch trong sổ lưu trữ: `databases: 50,213,144` · `backups: 176,882` — **riêng
khỏi** `containers` và `images`.

**CSDL sống sót qua mỗi lần triển khai lại.** Điều này đã được chính lỗi orphan chứng minh:
bản ghi còn nguyên, chỉ có tệp biến mất (P3a). Nói cách khác — nền tảng **có** đúng một nguyên
thể bền, và ta **đang dùng nó rồi**, chỉ là dùng cho hàng dữ liệu chứ không cho hiện vật.

⇒ Nguyên thể lưu trữ bền của VibeHost là **cơ sở dữ liệu**, không phải đĩa.

---

## §4 — Điều tôi **không** chứng minh được

Nói thẳng giới hạn, vì nó quyết định có nên gửi ticket hay không.

Tôi chứng minh volume bền **vắng mặt khỏi bề mặt API dành cho agent**, khỏi **mô hình tài nguyên**,
và khỏi **sổ kế toán lưu trữ của 12 dịch vụ**. Ba thứ đó cộng lại là bằng chứng mạnh.

Nhưng MCP là bề mặt **agent** — tôi **không** chứng minh được rằng bảng điều khiển web hoặc bộ
phận hỗ trợ không có tính năng đĩa bền nào không lộ ra ở API. P3b đã nhìn giao diện và ghi *"chỉ
có Tạo database và Sao lưu"*; tôi không lặp lại được phép quan sát đó qua công cụ hiện có.

⇒ Phần dư này đáng **một câu hỏi cho support**, không đáng một mini-spec.

Câu hỏi phụ của P3b — *"Sao lưu" sao lưu những gì* — nay đã có câu trả lời gián tiếp: `backups`
là **hạng mục tách riêng** khỏi `appdata`, và `appdata = 0`, nên **không thể** đang sao lưu dữ
liệu ứng dụng — chẳng có gì để sao lưu cả.

---

## §5 — Việc kế tiếp: khung quyết định đã đổi

P3b đóng khung là *"CÓ thì rẻ (vài phút), KHÔNG thì đắt"*. Câu trả lời là **KHÔNG**, nên còn lại
hai lựa chọn — **và cả hai gánh chung một phần việc nặng.**

| | **A — Postgres làm kho hiện vật** | **B — Kho đối tượng ngoài (S3/Supabase)** |
|---|---|---|
| Nhà cung cấp mới | không | **có** |
| Bí mật mới | không | **có** (lưu ý `GEMINI_API_KEYS` hiện vẫn **không** đánh dấu secret) |
| Đã được sao lưu | **có** | không (tự lo) |
| Chi phí/độ trễ | trong hạn mức gói | **chưa đo** |
| Chốt chặn | **hạn mức lưu trữ của gói không tra được** (xem dưới) | khoá + chi phí |
| Đúng công cụ cho ~1 GB ảnh | không hẳn | **có** |

**Phần việc nặng thì giống hệt nhau ở cả A và B**, và đây mới là thứ quyết định công sức:

> **`abs_path()` phải thôi làm hợp đồng đọc/ghi.**

Vì hiện tại (đo ở P3b §5.1): 3 chỗ **ghi** đưa đường tuyệt đối cho engine tự ghi
(`tasks.py:1178`, `1180`, `1881`), 3 chỗ **đọc** trả `FileResponse` theo đường tuyệt đối
(`routes.py:362`, `507`, `931`), và `SafeAreaService` (`tasks.py:494`, `1268`) nhận thẳng root
không qua lớp trừu tượng. Không kho nào ngoài hệ tệp cục bộ phục vụ được kiểu gọi đó.

⇒ **Chọn A hay B không phải thứ chặn việc.** Refactor `abs_path` mới là. Nên đừng để câu hỏi
"Postgres hay S3" trì hoãn mini-spec kế tiếp — phần lớn công việc làm xong rồi mới cần chốt.

### Một số liệu tôi **không** tra được

`whoami` trả `storageUsedGB` nhưng **không có trường hạn mức**, và `canUpgrade: false`. Nên tôi
**không xác nhận được** gói còn đủ chỗ cho ~1 GB hiện vật (ước tính P3b, đo trên 41 trang thật).
Phương án A phụ thuộc con số này. **Phải hỏi cùng lúc với câu hỏi support ở §4.**

---

## §6 — Giới hạn còn lại (không đổi so với P3b)

- **Hiện vật trên host vẫn KHÔNG bền** — chưa sửa, và P3c không sửa gì cả.
- Rủi ro `GEMINI_API_KEYS` chưa chuyển sang Secret — **đã xác nhận lại hôm nay** qua `list_env`:
  biến vẫn `isSecret: false` trong danh sách biến của `translation-api`.
- Chưa có auth / RBAC / TLS riêng. `ROLE=all`. E15 chữ dọc vẫn BLOCKED.
- **Chưa chạy Pilot/UAT.** Cổng Pilot vẫn **NO-GO** — P3c không mở cổng này, nó chỉ trả lời
  câu hỏi khiến cổng đóng.

## §7 — Git / Deploy State

```
Mã              : KHÔNG đổi một dòng nào
Cấu hình VibeHost: KHÔNG đổi — không tạo volume, không đổi biến, không đổi tài nguyên
Deploy          : KHÔNG
Rollback        : KHÔNG
Commit          : chỉ tài liệu này
Push            : xem cảnh báo dưới
```

⚠️ **3 commit trước đó vẫn nằm local, chưa push** lên `github.com/junnyken/Translation`:
`4adff88` (p3b) · `c330242` (p3a) · `c27fa79` (deploy). Commit của P3c là commit thứ tư.
