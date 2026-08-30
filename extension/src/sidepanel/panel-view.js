/** Dựng DOM cho Side Panel. Tách khỏi `panel.js` để test được mà không cần API của Chrome.
 *
 * Luật của tệp này:
 *  - Dữ liệu từ máy chủ **luôn** vào DOM bằng `textContent`, không bao giờ bằng `innerHTML`.
 *  - Nút nào chưa có bằng chứng dùng được thì `disabled` kèm lý do, không ẩn đi cho gọn mắt.
 *  - Trạng thái đi kèm CHỮ + BIỂU TƯỢNG; màu chỉ là phần phụ hoạ.
 */

import { nhanChapter, nhanThoiGian, tomTatChapter } from '../lib/status-presentation.js'

const BIEU_TUONG = { ok: '✓', tin: '•', canh: '!', loi: '✕', trung: '–' }

function e(the, thuoc_tinh = {}, con = []) {
  const n = document.createElement(the)
  for (const [k, v] of Object.entries(thuoc_tinh)) {
    if (v === undefined || v === null || v === false) continue
    if (k === 'chu') n.textContent = v
    else if (k === 'lop') n.className = v
    else if (k === 'khi_bam') n.addEventListener('click', v)
    else n.setAttribute(k, v === true ? '' : String(v))
  }
  for (const c of [].concat(con)) if (c) n.append(c)
  return n
}

function huyHieu(nhan, sac) {
  return e('span', { lop: 'huy-hieu', 'data-sac': sac }, [
    e('span', { lop: 'bt', 'aria-hidden': 'true', chu: BIEU_TUONG[sac] ?? '–' }),
    e('span', { chu: nhan }),
  ])
}

function nut(nhan, { vai, nho, tat, ly_do_tat, khi_bam, nhan_doc, gui_form } = {}) {
  return e('button', {
    lop: `nut${nho ? ' nut-nho' : ''}`,
    // Nút nằm trong <form> phải là `submit`, nếu không cú bấm không kích hoạt gì cả.
    type: gui_form ? 'submit' : 'button',
    'data-vai': vai,
    disabled: tat || undefined,
    title: tat ? ly_do_tat : undefined,
    'aria-label': nhan_doc,
    chu: nhan,
    khi_bam,
  })
}

/** Khối riêng tư — spec E1 §D1 bắt buộc có mặt ở màn đầu tiên. */
function khoiRiengTu() {
  return e('p', {
    lop: 'rieng-tu',
    chu: 'Tiện ích này không đọc nội dung trang web bạn đang xem và không tự tải ảnh từ internet.',
  })
}

/** Màn 1 — chưa có địa chỉ local. */
export function manDau({ dia_chi = '', ly_do = '', dang_ban = false, khi_luu, khi_mo_huong_dan }) {
  const o = e('input', {
    type: 'text', id: 'o-dia-chi', placeholder: 'http://127.0.0.1:5174',
    value: dia_chi, disabled: dang_ban || undefined, spellcheck: 'false',
    autocomplete: 'off', 'aria-describedby': 'goi-y-dia-chi',
  })
  const form = e('form', { lop: 'the' }, [
    e('label', { for: 'o-dia-chi', chu: 'Địa chỉ Translation local' }),
    o,
    e('p', {
      id: 'goi-y-dia-chi', lop: 'goi-y',
      chu: 'Chỉ nhận máy của chính bạn: localhost hoặc 127.0.0.1, kèm số cổng.',
    }),
    ly_do ? e('p', { lop: 'khoi', 'data-sac': 'loi', role: 'alert', chu: ly_do }) : null,
    e('div', { lop: 'xep' }, [
      nut(dang_ban ? 'Đang kiểm tra…' : 'Lưu & kiểm tra kết nối',
        { vai: 'chinh', tat: dang_ban, gui_form: true }),
      nut('Hướng dẫn khởi động Translation', { khi_bam: khi_mo_huong_dan }),
    ]),
  ])
  form.addEventListener('submit', (ev) => { ev.preventDefault(); khi_luu(o.value) })
  return e('div', {}, [khoiRiengTu(), form])
}

function lyDoKhongNoiDuoc() {
  return e('div', { lop: 'khoi', 'data-sac': 'loi', role: 'alert' }, [
    e('b', { chu: 'Không kết nối được Translation local.' }),
    e('ul', {}, [
      e('li', { chu: 'Ứng dụng Translation chưa chạy trên máy.' }),
      e('li', { chu: 'Sai địa chỉ hoặc sai cổng.' }),
      e('li', { chu: 'Máy chủ chạy nhưng chưa cho tiện ích đọc dữ liệu (CORS) — xem README §3.' }),
    ]),
  ])
}

/** Một chapter đã ghim. `du_lieu` là bản vừa lấy từ máy chủ, hoặc null nếu chỉ còn bản chụp cũ. */
function mucChapter(ghim, du_lieu, { khi_mo_chapter, khi_mo_ra_soat, khi_xuat, khi_bo_ghim, bay_gio }) {
  const chapter = du_lieu ?? null
  const tom_tat = chapter ? tomTatChapter(chapter) : null
  const ten = chapter?.title || ghim.title || 'Chapter chưa có tên'
  const tt = chapter?.status ?? ghim.status
  const nhan_tt = tt ? nhanChapter(tt) : null

  const tuoi = ghim.cachedAt ? nhanThoiGian(ghim.cachedAt, bay_gio) : ''
  const phu = chapter
    ? `${tom_tat.soTrang} trang · ${tom_tat.soTrangXuatDuoc} trang xuất được`
    : `Số liệu cũ${tuoi ? `, cập nhật lần cuối ${tuoi}` : ''} — chưa làm mới được.`

  const ly_do_tat = chapter
    ? 'Chưa có trang nào ở trạng thái cho phép việc này.'
    : 'Cần đọc được dữ liệu từ máy chủ mới biết việc này có làm được không.'

  return e('li', { lop: 'muc' }, [
    e('p', { lop: 'muc-ten', chu: ten }),
    nhan_tt ? huyHieu(nhan_tt.nhan, nhan_tt.sac) : null,
    e('p', { lop: 'muc-phu', chu: phu }),
    e('div', { lop: 'hang' }, [
      nut('Xem tiến độ', { nho: true, khi_bam: () => khi_mo_chapter(ghim.projectId),
        nhan_doc: `Xem tiến độ chapter ${ten}` }),
      nut('Mở rà soát', {
        nho: true,
        tat: !tom_tat?.coTheRaSoat,
        ly_do_tat,
        khi_bam: () => khi_mo_ra_soat(tom_tat.trangRaSoat),
        nhan_doc: `Mở rà soát chapter ${ten}`,
      }),
      nut('Xuất', {
        nho: true,
        tat: !tom_tat?.coTheXuat,
        ly_do_tat,
        khi_bam: () => khi_xuat(ghim.projectId),
        nhan_doc: `Mở màn xuất chapter ${ten}`,
      }),
      nut('Bỏ ghim', { nho: true, khi_bam: () => khi_bo_ghim(ghim.projectId),
        nhan_doc: `Bỏ ghim chapter ${ten}` }),
    ]),
  ])
}

/**
 * Màn 2 — đã có địa chỉ. Dùng cho cả trạng thái nối được lẫn không nối được: khác nhau ở
 * khối lý do và ở việc nút chapter có bằng chứng để bật hay không.
 */
export function manChinh(trang_thai, viec) {
  const {
    dia_chi, noi_duoc, dang_lam_moi, loi_ghim, ghim = [], du_lieu = {},
    bay_gio = Date.now(), da_kiem_luc,
  } = trang_thai

  // BA trạng thái, không phải hai. `null` = CHƯA kiểm xong. Vẽ "chưa kết nối" lúc chưa hỏi
  // máy chủ là khẳng định một thất bại chưa hề đo được — đúng loại nói quá mà M1–M10 cấm.
  const chua_biet = noi_duoc === null || noi_duoc === undefined

  const dau_the = e('div', { lop: 'the' }, [
    chua_biet
      ? huyHieu('Đang kiểm tra kết nối…', 'trung')
      : noi_duoc
        ? huyHieu('Đã kết nối local', 'ok')
        : huyHieu('Chưa kết nối Translation local', 'loi'),
    e('p', { lop: 'dia-chi-hien', chu: dia_chi, style: 'margin:8px 0 0' }),
    da_kiem_luc
      ? e('p', { lop: 'goi-y', chu: `Kiểm lần cuối: ${nhanThoiGian(da_kiem_luc, bay_gio)}` })
      : null,
  ])

  const cta = e('div', { lop: 'the xep' }, [
    nut('Tạo chapter mới', { vai: 'chinh', khi_bam: viec.khi_tao_chapter }),
    nut('Mở Translation', { khi_bam: viec.khi_mo_trang_chu }),
  ])

  const o_ma = e('input', {
    type: 'text', id: 'o-ma', placeholder: 'Dán mã chapter (UUID)',
    spellcheck: 'false', autocomplete: 'off', 'aria-describedby': 'goi-y-ma',
  })
  const form_ghim = e('form', { lop: 'xep' }, [
    e('label', { for: 'o-ma', chu: 'Ghim chapter bằng mã' }),
    o_ma,
    e('p', {
      id: 'goi-y-ma', lop: 'goi-y',
      chu: 'Máy chủ không có API liệt kê chapter, nên tiện ích không tự dò ra được. '
        + 'Chép mã từ địa chỉ web app (phần sau #project=).',
    }),
    loi_ghim ? e('p', { lop: 'khoi', 'data-sac': 'loi', role: 'alert', chu: loi_ghim }) : null,
    nut('Ghim chapter', { gui_form: true }),
  ])
  form_ghim.addEventListener('submit', (ev) => {
    ev.preventDefault()
    viec.khi_ghim(o_ma.value, () => { o_ma.value = '' })
  })

  const dau_ds = e('div', {
    style: 'display:flex;align-items:center;justify-content:space-between;gap:8px',
  }, [
    e('h2', { chu: 'Chapter đã ghim', style: 'margin:0' }),
    nut(dang_lam_moi ? '…' : '↻', {
      nho: true, tat: dang_lam_moi, khi_bam: viec.khi_lam_moi,
      nhan_doc: 'Làm mới trạng thái chapter',
    }),
  ])

  const than_ds = ghim.length
    ? e('ul', { lop: 'ds' }, ghim.map((g) => mucChapter(g, du_lieu[g.projectId] ?? null, {
      ...viec, bay_gio,
    })))
    : e('p', {
      lop: 'goi-y',
      chu: 'Chưa ghim chapter nào. Danh sách chapter đầy đủ cần được mở từ ứng dụng Translation.',
    })

  // Xác nhận xoá dựng ngay trong panel: `confirm()` của trình duyệt không đáng tin trong
  // các mặt tiền của tiện ích, và một hộp thoại hệ thống thì không test được.
  const chan = trang_thai.hoi_xoa
    ? e('div', { lop: 'khoi', 'data-sac': 'canh', role: 'alertdialog',
      'aria-label': 'Xác nhận xoá dữ liệu tiện ích' }, [
      e('b', { chu: 'Xoá cài đặt và dữ liệu của tiện ích?' }),
      e('p', {
        style: 'margin:6px 0 8px',
        chu: 'Chỉ xoá địa chỉ đã lưu và danh sách chapter đã ghim TRONG TRÌNH DUYỆT. '
          + 'Chapter, ảnh và bản dịch trong ứng dụng Translation KHÔNG bị xoá.',
      }),
      e('div', { lop: 'hang' }, [
        nut('Xoá', { nho: true, khi_bam: viec.khi_xac_nhan_xoa }),
        nut('Huỷ', { nho: true, khi_bam: viec.khi_huy_xoa }),
      ]),
    ])
    : e('div', { lop: 'chan' }, [
      e('button', { lop: 'nut-chu', type: 'button', chu: 'Cài đặt kết nối',
        khi_bam: viec.khi_mo_cai_dat }),
      e('button', { lop: 'nut-chu', type: 'button', chu: 'Xoá dữ liệu extension',
        khi_bam: viec.khi_hoi_xoa }),
    ])

  return e('div', {}, [
    // Khối lý do chỉ hiện khi đã HỎI và thật sự hỏng.
    noi_duoc === false ? lyDoKhongNoiDuoc() : null,
    dau_the,
    cta,
    e('section', { lop: 'the' }, [dau_ds, than_ds]),
    e('section', { lop: 'the' }, [form_ghim]),
    chan,
  ])
}
