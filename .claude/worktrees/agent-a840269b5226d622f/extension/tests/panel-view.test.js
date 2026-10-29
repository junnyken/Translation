import { beforeEach, describe, expect, it, vi } from 'vitest'
import { manChinh, manDau } from '../src/sidepanel/panel-view.js'

const MA = '67094721-c9e4-4231-896d-83b555205a42'
const MA2 = 'd6c604ed-75f0-4fcf-b2f8-1afe25ae8cb5'
const TRANG_A = '5031a72b-40cc-4818-8734-db9ec0b831e4'
const T0 = Date.parse('2026-08-30T12:00:00.000Z')

function gan(nut) {
  document.body.replaceChildren(nut)
  return document.body
}

const timNut = (chu) => [...document.querySelectorAll('button')]
  .find((b) => b.textContent.trim() === chu)

function viecGia() {
  return {
    khi_tao_chapter: vi.fn(), khi_mo_trang_chu: vi.fn(), khi_mo_chapter: vi.fn(),
    khi_mo_ra_soat: vi.fn(), khi_xuat: vi.fn(), khi_bo_ghim: vi.fn(), khi_ghim: vi.fn(),
    khi_lam_moi: vi.fn(), khi_mo_cai_dat: vi.fn(), khi_hoi_xoa: vi.fn(),
    khi_huy_xoa: vi.fn(), khi_xac_nhan_xoa: vi.fn(),
  }
}

beforeEach(() => document.body.replaceChildren())

describe('màn đầu — chưa có địa chỉ', () => {
  it('có ô nhập, nút lưu, hướng dẫn và câu nói rõ phạm vi', () => {
    gan(manDau({ khi_luu: vi.fn(), khi_mo_huong_dan: vi.fn() }))
    expect(document.querySelector('#o-dia-chi')).not.toBeNull()
    expect(timNut('Lưu & kiểm tra kết nối')).toBeTruthy()
    expect(timNut('Hướng dẫn khởi động Translation')).toBeTruthy()
    expect(document.body.textContent)
      .toContain('không đọc nội dung trang web bạn đang xem')
    expect(document.body.textContent).toContain('không tự tải ảnh từ internet')
  })

  it('gợi ý dùng cổng ĐO ĐƯỢC, không phải cổng đoán', () => {
    gan(manDau({ khi_luu: vi.fn(), khi_mo_huong_dan: vi.fn() }))
    expect(document.querySelector('#o-dia-chi').placeholder).toBe('http://127.0.0.1:5174')
  })

  it('ô nhập có nhãn nối đúng bằng for/id', () => {
    gan(manDau({ khi_luu: vi.fn(), khi_mo_huong_dan: vi.fn() }))
    const nhan = document.querySelector('label[for="o-dia-chi"]')
    expect(nhan).not.toBeNull()
    expect(nhan.textContent).toContain('Địa chỉ Translation local')
  })

  it('nút chính PHẢI là submit — bấm bằng chuột cũng chạy, không chỉ Enter', () => {
    // Lỗi này lọt qua toàn bộ test đơn vị và chỉ lộ ra ở lượt bấm thật trên Chromium:
    // `type="button"` trong <form> khiến nút "Lưu & kiểm tra kết nối" hoàn toàn vô tác dụng.
    const khi_luu = vi.fn()
    gan(manDau({ khi_luu, khi_mo_huong_dan: vi.fn() }))
    const b = timNut('Lưu & kiểm tra kết nối')
    expect(b.type).toBe('submit')
    document.querySelector('#o-dia-chi').value = 'http://127.0.0.1:5174'
    b.click()
    expect(khi_luu).toHaveBeenCalledWith('http://127.0.0.1:5174')
  })

  it('gửi form thì gọi khi_luu với đúng giá trị đã gõ', () => {
    const khi_luu = vi.fn()
    gan(manDau({ khi_luu, khi_mo_huong_dan: vi.fn() }))
    document.querySelector('#o-dia-chi').value = 'http://127.0.0.1:5174'
    document.querySelector('form').dispatchEvent(
      new Event('submit', { bubbles: true, cancelable: true }))
    expect(khi_luu).toHaveBeenCalledWith('http://127.0.0.1:5174')
  })

  it('đang kiểm tra thì khoá nút và ô nhập', () => {
    gan(manDau({ dang_ban: true, khi_luu: vi.fn(), khi_mo_huong_dan: vi.fn() }))
    expect(timNut('Đang kiểm tra…').disabled).toBe(true)
    expect(document.querySelector('#o-dia-chi').disabled).toBe(true)
  })

  it('lý do lỗi hiện ra và được đánh dấu alert cho trình đọc màn hình', () => {
    gan(manDau({ ly_do: 'Chỉ nhận máy của chính bạn.', khi_luu: vi.fn(),
      khi_mo_huong_dan: vi.fn() }))
    const alert = document.querySelector('[role="alert"]')
    expect(alert.textContent).toContain('Chỉ nhận máy của chính bạn.')
  })

  it('KHÔNG hứa hẹn dịch trang / phủ bản dịch', () => {
    gan(manDau({ khi_luu: vi.fn(), khi_mo_huong_dan: vi.fn() }))
    const chu = document.body.textContent.toLowerCase()
    for (const cam of ['dịch trang web', 'overlay', 'phủ bản dịch', 'quét trang']) {
      expect(chu).not.toContain(cam)
    }
  })
})

describe('màn chính — đã kết nối', () => {
  const chapter = {
    projectId: MA, title: 'Chương 1', status: 'active',
    updatedAt: '2026-08-30T11:00:00Z', soTrang: 3,
    trang: [
      { id: TRANG_A, thuTu: 1, trangThai: 'typeset_done' },
      { id: MA2, thuTu: 2, trangThai: 'queued' },
    ],
  }
  const nen = {
    dia_chi: 'http://127.0.0.1:5174', noi_duoc: true, bay_gio: T0,
    ghim: [{ projectId: MA, title: 'Chương 1', cachedAt: new Date(T0 - 30_000).toISOString() }],
    du_lieu: { [MA]: chapter },
  }

  it('hiện huy hiệu đã kết nối kèm địa chỉ đang dùng', () => {
    gan(manChinh(nen, viecGia()))
    expect(document.body.textContent).toContain('Đã kết nối local')
    expect(document.body.textContent).toContain('http://127.0.0.1:5174')
  })

  it('hai CTA chính có mặt và gọi đúng việc', () => {
    const viec = viecGia()
    gan(manChinh(nen, viec))
    timNut('Tạo chapter mới').click()
    timNut('Mở Translation').click()
    expect(viec.khi_tao_chapter).toHaveBeenCalledOnce()
    expect(viec.khi_mo_trang_chu).toHaveBeenCalledOnce()
  })

  it('trang đã căn chữ -> nút Mở rà soát và Xuất được BẬT', () => {
    const viec = viecGia()
    gan(manChinh(nen, viec))
    expect(timNut('Mở rà soát').disabled).toBe(false)
    expect(timNut('Xuất').disabled).toBe(false)
    timNut('Mở rà soát').click()
    expect(viec.khi_mo_ra_soat).toHaveBeenCalledWith(TRANG_A)
  })

  it('chưa trang nào căn chữ -> nút bị TẮT kèm lý do, không ẩn đi', () => {
    const viec = viecGia()
    gan(manChinh({
      ...nen,
      du_lieu: { [MA]: { ...chapter, trang: [{ id: TRANG_A, trangThai: 'queued' }] } },
    }, viec))
    const xuat = timNut('Xuất')
    expect(xuat.disabled).toBe(true)
    expect(xuat.title).toContain('Chưa có trang nào')
    xuat.click()
    expect(viec.khi_xuat).not.toHaveBeenCalled()
  })

  it('nút làm mới là THỦ CÔNG và có nhãn cho trình đọc màn hình', () => {
    const viec = viecGia()
    gan(manChinh(nen, viec))
    const lam_moi = document.querySelector('[aria-label="Làm mới trạng thái chapter"]')
    expect(lam_moi).not.toBeNull()
    lam_moi.click()
    expect(viec.khi_lam_moi).toHaveBeenCalledOnce()
  })

  it('đang làm mới thì nút bị khoá', () => {
    gan(manChinh({ ...nen, dang_lam_moi: true }, viecGia()))
    expect(document.querySelector('[aria-label="Làm mới trạng thái chapter"]').disabled).toBe(true)
  })

  it('mọi nút trong danh sách đều có nhãn đọc được kèm tên chapter', () => {
    gan(manChinh(nen, viecGia()))
    for (const chu of ['Xem tiến độ', 'Mở rà soát', 'Xuất', 'Bỏ ghim']) {
      expect(timNut(chu).getAttribute('aria-label')).toContain('Chương 1')
    }
  })

  it('tên chapter vào DOM bằng văn bản — thẻ HTML trong tên KHÔNG được dựng', () => {
    gan(manChinh({
      ...nen,
      ghim: [{ projectId: MA, cachedAt: new Date(T0).toISOString() }],
      du_lieu: { [MA]: { ...chapter, title: '<img src=x onerror=alert(1)>' } },
    }, viecGia()))
    expect(document.querySelector('img')).toBeNull()
    expect(document.body.textContent).toContain('<img src=x onerror=alert(1)>')
  })

  it('chưa ghim gì -> nói rõ danh sách phải mở từ web app, không giả vờ "chưa có chapter"', () => {
    gan(manChinh({ ...nen, ghim: [], du_lieu: {} }, viecGia()))
    expect(document.body.textContent).toContain('Danh sách chapter đầy đủ cần được mở từ ứng dụng')
    expect(document.querySelectorAll('li.muc')).toHaveLength(0)
  })
})

describe('màn chính — KHÔNG kết nối được', () => {
  const nen = {
    dia_chi: 'http://127.0.0.1:5174', noi_duoc: false, bay_gio: T0,
    ghim: [{
      projectId: MA, title: 'Chương 1', status: 'active',
      cachedAt: new Date(T0 - 3 * 3600_000).toISOString(),
    }],
    du_lieu: {},
  }

  it('nêu CẢ BA lý do có thể, kể cả CORS', () => {
    gan(manChinh(nen, viecGia()))
    const chu = document.body.textContent
    expect(chu).toContain('Không kết nối được Translation local')
    expect(chu).toContain('chưa chạy')
    expect(chu).toContain('Sai địa chỉ hoặc sai cổng')
    expect(chu).toContain('CORS')
  })

  it('KHÔNG hiện danh sách rỗng như thể chưa có chapter nào', () => {
    gan(manChinh(nen, viecGia()))
    expect(document.querySelectorAll('li.muc')).toHaveLength(1)
    expect(document.body.textContent).not.toContain('Chưa ghim chapter nào')
  })

  it('số liệu cũ được DÁN NHÃN tuổi, không trình bày như số mới', () => {
    gan(manChinh(nen, viecGia()))
    expect(document.body.textContent).toContain('Số liệu cũ')
    expect(document.body.textContent).toContain('3 giờ trước')
  })

  it('không có dữ liệu tươi -> nút rà soát/xuất TẮT, không đoán bừa', () => {
    gan(manChinh(nen, viecGia()))
    expect(timNut('Mở rà soát').disabled).toBe(true)
    expect(timNut('Xuất').disabled).toBe(true)
    expect(timNut('Mở rà soát').title).toContain('Cần đọc được dữ liệu từ máy chủ')
  })

  it('vẫn mở được web app — đây là giá trị cốt lõi của chế độ chỉ-mở-link', () => {
    const viec = viecGia()
    gan(manChinh(nen, viec))
    expect(timNut('Tạo chapter mới').disabled).toBe(false)
    timNut('Tạo chapter mới').click()
    expect(viec.khi_tao_chapter).toHaveBeenCalledOnce()
  })

  it('nút Xem tiến độ vẫn bật: chỉ cần mã là mở được, không cần đọc dữ liệu', () => {
    const viec = viecGia()
    gan(manChinh(nen, viec))
    timNut('Xem tiến độ').click()
    expect(viec.khi_mo_chapter).toHaveBeenCalledWith(MA)
  })
})

describe('màn chính — CHƯA kiểm xong kết nối', () => {
  // Lỗi này lộ ra ở lượt đo thật: panel nhấp nháy "Chưa kết nối Translation local" trong lúc
  // lượt kiểm còn đang chạy — tức là khẳng định một thất bại chưa hề đo được.
  const nen = {
    dia_chi: 'http://127.0.0.1:5174', noi_duoc: null, bay_gio: T0,
    ghim: [{ projectId: MA, title: 'Chương 1', cachedAt: new Date(T0).toISOString() }],
    du_lieu: {},
  }

  it('nói "đang kiểm tra", KHÔNG nói "chưa kết nối"', () => {
    gan(manChinh(nen, viecGia()))
    const chu = document.body.textContent
    expect(chu).toContain('Đang kiểm tra kết nối')
    expect(chu).not.toContain('Chưa kết nối Translation local')
  })

  it('KHÔNG hiện khối lý do hỏng khi chưa hỏi máy chủ', () => {
    gan(manChinh(nen, viecGia()))
    expect(document.body.textContent).not.toContain('Không kết nối được Translation local')
  })

  it('vẫn mở được web app trong lúc đang kiểm', () => {
    const viec = viecGia()
    gan(manChinh(nen, viec))
    timNut('Tạo chapter mới').click()
    expect(viec.khi_tao_chapter).toHaveBeenCalledOnce()
  })

  it('nút cần dữ liệu tươi vẫn TẮT — chưa có bằng chứng thì chưa bật', () => {
    gan(manChinh(nen, viecGia()))
    expect(timNut('Xuất').disabled).toBe(true)
  })

  it('undefined cũng được coi là chưa biết, không phải hỏng', () => {
    gan(manChinh({ ...nen, noi_duoc: undefined }, viecGia()))
    expect(document.body.textContent).toContain('Đang kiểm tra kết nối')
  })
})

describe('ghim chapter bằng mã', () => {
  const nen = { dia_chi: 'http://127.0.0.1:5174', noi_duoc: true, ghim: [], du_lieu: {},
    bay_gio: T0 }

  it('nói rõ VÌ SAO phải nhập tay (máy chủ không có API liệt kê)', () => {
    gan(manChinh(nen, viecGia()))
    expect(document.body.textContent).toContain('không có API liệt kê chapter')
  })

  it('nút Ghim chapter PHẢI là submit', () => {
    const viec = viecGia()
    gan(manChinh(nen, viec))
    const b = timNut('Ghim chapter')
    expect(b.type).toBe('submit')
    document.querySelector('#o-ma').value = MA
    b.click()
    expect(viec.khi_ghim).toHaveBeenCalledWith(MA, expect.any(Function))
  })

  it('gửi form thì chuyển giá trị đã gõ sang khi_ghim', () => {
    const viec = viecGia()
    gan(manChinh(nen, viec))
    document.querySelector('#o-ma').value = MA
    document.querySelectorAll('form')[0].dispatchEvent(
      new Event('submit', { bubbles: true, cancelable: true }))
    expect(viec.khi_ghim).toHaveBeenCalledWith(MA, expect.any(Function))
  })

  it('lỗi ghim hiện ra dưới dạng alert', () => {
    gan(manChinh({ ...nen, loi_ghim: 'Mã chapter phải là chuỗi UUID' }, viecGia()))
    expect(document.querySelector('[role="alert"]').textContent).toContain('UUID')
  })
})

describe('xoá dữ liệu — xác nhận ngay trong panel', () => {
  const nen = { dia_chi: 'http://127.0.0.1:5174', noi_duoc: true, ghim: [], du_lieu: {},
    bay_gio: T0 }

  it('bấm lần đầu chỉ HỎI, chưa xoá', () => {
    const viec = viecGia()
    gan(manChinh(nen, viec))
    timNut('Xoá dữ liệu extension').click()
    expect(viec.khi_hoi_xoa).toHaveBeenCalledOnce()
    expect(viec.khi_xac_nhan_xoa).not.toHaveBeenCalled()
  })

  it('khối xác nhận nói RÕ backend không bị xoá', () => {
    gan(manChinh({ ...nen, hoi_xoa: true }, viecGia()))
    const chu = document.body.textContent
    expect(chu).toContain('TRONG TRÌNH DUYỆT')
    expect(chu).toContain('KHÔNG bị xoá')
    expect(document.querySelector('[role="alertdialog"]')).not.toBeNull()
  })

  it('có cả nút Xoá và Huỷ, gọi đúng việc', () => {
    const viec = viecGia()
    gan(manChinh({ ...nen, hoi_xoa: true }, viec))
    timNut('Huỷ').click()
    expect(viec.khi_huy_xoa).toHaveBeenCalledOnce()
    timNut('Xoá').click()
    expect(viec.khi_xac_nhan_xoa).toHaveBeenCalledOnce()
  })
})

describe('tiếp cận — bàn phím và trình đọc màn hình', () => {
  const nen = {
    dia_chi: 'http://127.0.0.1:5174', noi_duoc: true, bay_gio: T0,
    ghim: [{ projectId: MA, title: 'Chương 1', cachedAt: new Date(T0).toISOString() }],
    du_lieu: { [MA]: { projectId: MA, title: 'Chương 1', status: 'active',
      trang: [{ id: TRANG_A, trangThai: 'typeset_done' }] } },
  }

  it('mọi nút đều là <button> thật — Tab/Enter/Space chạy sẵn, không cần div giả', () => {
    gan(manChinh(nen, viecGia()))
    const bam_duoc = document.querySelectorAll('button, a[href], input')
    for (const n of bam_duoc) {
      expect(['BUTTON', 'A', 'INPUT']).toContain(n.tagName)
      expect(n.getAttribute('tabindex')).not.toBe('-1')
    }
    expect(document.querySelectorAll('[role="button"]')).toHaveLength(0)
  })

  it('trạng thái có CHỮ, không chỉ có màu', () => {
    gan(manChinh(nen, viecGia()))
    for (const hh of document.querySelectorAll('.huy-hieu')) {
      const chu = hh.textContent.replace(/[✓•!✕–]/g, '').trim()
      expect(chu.length).toBeGreaterThan(0)
    }
  })

  it('nút chỉ có ký hiệu thì phải có aria-label', () => {
    gan(manChinh(nen, viecGia()))
    for (const b of document.querySelectorAll('button')) {
      const chu = b.textContent.trim()
      if (chu.length <= 2) expect(b.getAttribute('aria-label')).toBeTruthy()
    }
  })

  it('ô nhập mã có nhãn và mô tả nối bằng aria-describedby', () => {
    gan(manChinh({ ...nen, ghim: [], du_lieu: {} }, viecGia()))
    const o = document.querySelector('#o-ma')
    expect(document.querySelector('label[for="o-ma"]')).not.toBeNull()
    expect(document.getElementById(o.getAttribute('aria-describedby'))).not.toBeNull()
  })
})
