import { beforeEach, describe, expect, it } from 'vitest'
import {
  HAN_BAN_CHUP_MS, KHOA_CAI_DAT, KHOA_CAM, KHOA_GHIM, SO_GHIM_TOI_DA,
  chotChanGhi, docCaiDat, docGhim, docMotGhim, donDeGhi,
} from '../src/lib/storage-schema.js'
import {
  boGhim, ghiCaiDat, ghimChapter, layCaiDat, layGhim, xoaHet,
} from '../src/lib/settings.js'

const MA = '67094721-c9e4-4231-896d-83b555205a42'
const MA2 = 'd6c604ed-75f0-4fcf-b2f8-1afe25ae8cb5'

/** Kho giả — đúng hình dạng `chrome.storage.local` (get/set/remove, bất đồng bộ). */
function khoGia(ban_dau = {}) {
  const noi_dung = { ...ban_dau }
  return {
    noi_dung,
    async get(khoa) {
      const ds = [].concat(khoa)
      const ra = {}
      for (const k of ds) if (k in noi_dung) ra[k] = noi_dung[k]
      return ra
    },
    async set(o) { Object.assign(noi_dung, o) },
    async remove(khoa) { for (const k of [].concat(khoa)) delete noi_dung[k] },
  }
}

describe('docCaiDat — dữ liệu hỏng phải lùi về mặc định, không được ném lỗi', () => {
  it.each([
    ['null', null],
    ['undefined', undefined],
    ['chuỗi', 'hong'],
    ['số', 42],
    ['mảng', []],
    ['thiếu schemaVersion', { translationBaseUrl: 'http://127.0.0.1:8010' }],
    ['schemaVersion lạ', { schemaVersion: 99, translationBaseUrl: 'http://127.0.0.1:8010' }],
  ])('%s -> mặc định', (_ten, vao) => {
    const { caiDat } = docCaiDat(vao)
    expect(caiDat.schemaVersion).toBe(1)
    expect(caiDat.translationBaseUrl).toBe('')
    expect(caiDat.preferredLaunchSurface).toBe('side_panel')
  })

  it('loại địa chỉ không phải loopback đã lỡ nằm trong kho', () => {
    const { caiDat, phaiDon } = docCaiDat({
      schemaVersion: 1, translationBaseUrl: 'http://evil.example:8010',
    })
    expect(caiDat.translationBaseUrl).toBe('')
    expect(phaiDon).toBe(true)
  })

  it('loại mặt tiền không có trong danh sách', () => {
    const { caiDat } = docCaiDat({ schemaVersion: 1, preferredLaunchSurface: 'toan-man-hinh' })
    expect(caiDat.preferredLaunchSurface).toBe('side_panel')
  })

  it('loại id không phải UUID', () => {
    const { caiDat } = docCaiDat({
      schemaVersion: 1, lastOpenedProjectId: '../../etc/passwd', lastOpenedPageId: 'x',
    })
    expect(caiDat.lastOpenedProjectId).toBeUndefined()
    expect(caiDat.lastOpenedPageId).toBeUndefined()
  })

  it('KHÔNG mang theo khoá lạ, kể cả khoá cấm', () => {
    const { caiDat, phaiDon } = docCaiDat({
      schemaVersion: 1,
      translationBaseUrl: 'http://127.0.0.1:8010',
      apiKey: 'AIza-bi-mat',
      ocr: 'chữ gốc đọc được',
      image: 'data:image/png;base64,xxx',
    })
    expect(caiDat.apiKey).toBeUndefined()
    expect(caiDat.ocr).toBeUndefined()
    expect(caiDat.image).toBeUndefined()
    expect(Object.keys(caiDat)).toEqual(expect.arrayContaining(['schemaVersion']))
    expect(phaiDon).toBe(true)
    expect(caiDat.translationBaseUrl).toBe('http://127.0.0.1:8010')
  })

  it('giữ lại đúng giá trị hợp lệ', () => {
    const { caiDat, phaiDon } = docCaiDat({
      schemaVersion: 1,
      translationBaseUrl: 'http://localhost:5174/',
      preferredLaunchSurface: 'side_panel',
      lastOpenedProjectId: MA.toUpperCase(),
      lastConnectionCheckAt: '2026-08-30T10:00:00.000Z',
    })
    expect(caiDat.translationBaseUrl).toBe('http://localhost:5174')
    expect(caiDat.lastOpenedProjectId).toBe(MA)
    expect(caiDat.lastConnectionCheckAt).toBe('2026-08-30T10:00:00.000Z')
    expect(phaiDon).toBe(false)
  })
})

describe('chotChanGhi — chặn ở lượt GHI, không chỉ ở lượt đọc', () => {
  it.each(KHOA_CAM)('từ chối khoá cấm: %s', (khoa) => {
    expect(() => chotChanGhi(KHOA_CAI_DAT, { schemaVersion: 1, [khoa]: 'x' })).toThrow()
  })

  it('từ chối khoá kho chưa khai báo', () => {
    expect(() => chotChanGhi('khoaLa', {})).toThrow()
  })

  it('từ chối ghim quá 5 mục', () => {
    const ds = Array.from({ length: 6 }, () => ({ projectId: MA, cachedAt: 'x' }))
    expect(() => chotChanGhi(KHOA_GHIM, ds)).toThrow()
  })

  it('từ chối trường lạ trong một mục ghim', () => {
    expect(() => chotChanGhi(KHOA_GHIM, [{ projectId: MA, cachedAt: 'x', ocrText: 'abc' }]))
      .toThrow()
  })

  it('cho qua bản hợp khuôn', () => {
    expect(chotChanGhi(KHOA_CAI_DAT, donDeGhi({ schemaVersion: 1, translationBaseUrl: '' })))
      .toBe(true)
    expect(chotChanGhi(KHOA_GHIM, [{
      projectId: MA, title: 'Chapter 1', status: 'active',
      updatedAt: '2026-08-30T10:00:00Z', cachedAt: '2026-08-30T10:00:00Z',
    }])).toBe(true)
  })
})

describe('docGhim — hạn dùng, số lượng, dữ liệu hỏng', () => {
  const bay_gio = Date.parse('2026-08-30T12:00:00.000Z')
  const moi = new Date(bay_gio - 60_000).toISOString()
  const cu = new Date(bay_gio - HAN_BAN_CHUP_MS - 60_000).toISOString()

  it('bản chụp còn hạn thì giữ nguyên tên/trạng thái', () => {
    const { ghim } = docGhim([{ projectId: MA, title: 'Chương 1', status: 'active', cachedAt: moi }],
      bay_gio)
    expect(ghim[0].title).toBe('Chương 1')
    expect(ghim[0].status).toBe('active')
  })

  it('bản chụp QUÁ HẠN thì bỏ tên/trạng thái, chỉ giữ mã', () => {
    // Số cũ không nhãn là số nói dối — thà không hiện gì còn hơn hiện trạng thái của hôm qua.
    const { ghim, phaiDon } = docGhim(
      [{ projectId: MA, title: 'Chương 1', status: 'active', cachedAt: cu }], bay_gio)
    expect(ghim[0].projectId).toBe(MA)
    expect(ghim[0].title).toBeUndefined()
    expect(ghim[0].status).toBeUndefined()
    expect(phaiDon).toBe(true)
  })

  it('cắt còn tối đa 5 mục', () => {
    const ds = Array.from({ length: 9 }, (_, i) => ({
      projectId: MA.slice(0, -1) + i.toString(16), cachedAt: moi,
    }))
    const { ghim, phaiDon } = docGhim(ds, bay_gio)
    expect(ghim).toHaveLength(SO_GHIM_TOI_DA)
    expect(phaiDon).toBe(true)
  })

  it('bỏ mục trùng mã', () => {
    const { ghim } = docGhim([
      { projectId: MA, cachedAt: moi }, { projectId: MA, cachedAt: moi },
    ], bay_gio)
    expect(ghim).toHaveLength(1)
  })

  it.each([
    ['không phải mảng', { a: 1 }],
    ['null', null],
  ])('%s -> danh sách rỗng', (_ten, vao) => {
    expect(docGhim(vao, bay_gio).ghim).toEqual([])
  })

  it.each([
    ['thiếu projectId', { cachedAt: moi }],
    ['projectId không phải UUID', { projectId: '../x', cachedAt: moi }],
    ['thiếu cachedAt', { projectId: MA }],
    ['cachedAt không đọc được', { projectId: MA, cachedAt: 'hôm qua' }],
    ['cachedAt ở tương lai', { projectId: MA, cachedAt: '2099-01-01T00:00:00Z' }],
  ])('loại mục hỏng: %s', (_ten, vao) => {
    expect(docMotGhim(vao, bay_gio)).toBeNull()
  })

  it('KHÔNG mang theo trường ngoài khuôn', () => {
    const muc = docMotGhim({
      projectId: MA, cachedAt: moi, title: 'X',
      ocrText: 'chữ gốc', imageBlob: 'xxx', apiKey: 'AIza', filePath: '/home/a/b.png',
    }, bay_gio)
    expect(Object.keys(muc).sort()).toEqual(['cachedAt', 'projectId', 'title'])
  })
})

describe('settings — vòng đời qua kho giả', () => {
  let kho
  beforeEach(() => { kho = khoGia() })

  it('kho rỗng -> mặc định, không ném lỗi', async () => {
    const c = await layCaiDat(kho)
    expect(c.translationBaseUrl).toBe('')
  })

  it('ghi rồi đọc lại giữ nguyên giá trị', async () => {
    await ghiCaiDat({ schemaVersion: 1, translationBaseUrl: 'http://127.0.0.1:8010' }, kho)
    expect((await layCaiDat(kho)).translationBaseUrl).toBe('http://127.0.0.1:8010')
  })

  it('dữ liệu hỏng trong kho được DỌN chứ không chỉ bị bỏ qua lúc đọc', async () => {
    kho.noi_dung[KHOA_CAI_DAT] = { schemaVersion: 1, apiKey: 'bi-mat', translationBaseUrl: 'x' }
    const c = await layCaiDat(kho)
    expect(c.translationBaseUrl).toBe('')
    expect(kho.noi_dung[KHOA_CAI_DAT].apiKey).toBeUndefined()
  })

  it('kho ném lỗi -> vẫn trả mặc định', async () => {
    const kho_hong = { get: async () => { throw new Error('kho hỏng') }, set: async () => {},
      remove: async () => {} }
    expect((await layCaiDat(kho_hong)).translationBaseUrl).toBe('')
    expect(await layGhim(kho_hong)).toEqual([])
  })

  it('ghim, ghim lại cùng mã thì đẩy lên đầu chứ không nhân đôi', async () => {
    await ghimChapter({ projectId: MA, title: 'A' }, kho)
    await ghimChapter({ projectId: MA2, title: 'B' }, kho)
    await ghimChapter({ projectId: MA, title: 'A moi' }, kho)
    const ds = await layGhim(kho)
    expect(ds).toHaveLength(2)
    expect(ds[0].projectId).toBe(MA)
    expect(ds[0].title).toBe('A moi')
  })

  it('bỏ ghim chỉ gỡ đúng một mục', async () => {
    await ghimChapter({ projectId: MA, title: 'A' }, kho)
    await ghimChapter({ projectId: MA2, title: 'B' }, kho)
    await boGhim(MA, kho)
    const ds = await layGhim(kho)
    expect(ds.map((g) => g.projectId)).toEqual([MA2])
  })

  it('xoá hết chỉ đụng hai khoá của tiện ích', async () => {
    kho.noi_dung.khoaCuaAiDo = 'giữ nguyên'
    await ghiCaiDat({ schemaVersion: 1, translationBaseUrl: 'http://127.0.0.1:8010' }, kho)
    await ghimChapter({ projectId: MA }, kho)
    await xoaHet(kho)
    expect(kho.noi_dung[KHOA_CAI_DAT]).toBeUndefined()
    expect(kho.noi_dung[KHOA_GHIM]).toBeUndefined()
    expect(kho.noi_dung.khoaCuaAiDo).toBe('giữ nguyên')
  })

  it('cài đặt sống sót qua "service worker khởi động lại" (đọc lại từ kho)', async () => {
    // Mô phỏng: worker bị Chrome tắt, mọi biến toàn cục mất, chỉ còn kho.
    await ghiCaiDat({
      schemaVersion: 1, translationBaseUrl: 'http://127.0.0.1:8010', lastOpenedProjectId: MA,
    }, kho)
    const sau_khi_dung_lai = await layCaiDat(kho)
    expect(sau_khi_dung_lai.translationBaseUrl).toBe('http://127.0.0.1:8010')
    expect(sau_khi_dung_lai.lastOpenedProjectId).toBe(MA)
  })

  it('không ghi được trường ngoài khuôn dù gọi thẳng ghiCaiDat', async () => {
    await expect(ghiCaiDat({ schemaVersion: 1, apiKey: 'x' }, kho)).resolves.toBeDefined()
    expect(kho.noi_dung[KHOA_CAI_DAT].apiKey).toBeUndefined()
  })
})
