import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

// `import.meta.url` không phải file:// dưới môi trường jsdom, nên lấy gốc từ thư mục chạy vitest.
const GOC = process.cwd()
const manifest = JSON.parse(readFileSync(join(GOC, 'manifest.json'), 'utf8'))

/** Quyền chỉ được thêm khi có audit + phê duyệt bằng văn bản (spec E1 §E). */
const QUYEN_CAM = [
  'scripting', 'activeTab', 'tabs', 'webRequest', 'webRequestBlocking',
  'declarativeNetRequest', 'downloads', 'history', 'bookmarks',
  'clipboardRead', 'clipboardWrite', 'cookies', 'management',
  'nativeMessaging', 'debugger', 'proxy', 'privacy', 'desktopCapture',
  'tabCapture', 'pageCapture', 'geolocation', 'unlimitedStorage',
]

function tepNguon(thu_muc = join(GOC, 'src'), gom = []) {
  for (const ten of readdirSync(thu_muc)) {
    const d = join(thu_muc, ten)
    if (statSync(d).isDirectory()) tepNguon(d, gom)
    else if (/\.(js|html)$/.test(ten)) gom.push(d)
  }
  return gom
}

const NGUON = tepNguon().map((d) => ({ duong_dan: d, chu: readFileSync(d, 'utf8') }))

describe('ảnh chụp manifest — chốt chặn quyền', () => {
  it('là Manifest V3', () => {
    expect(manifest.manifest_version).toBe(3)
  })

  it('KHÔNG có content_scripts', () => {
    expect(manifest.content_scripts).toBeUndefined()
  })

  it('host_permissions rỗng', () => {
    expect(manifest.host_permissions).toEqual([])
  })

  it('KHÔNG có <all_urls> hay ký tự đại diện ở bất kỳ đâu trong manifest', () => {
    const chu = JSON.stringify(manifest)
    expect(chu).not.toContain('<all_urls>')
    expect(chu).not.toContain('*://')
    expect(chu).not.toContain('file:///')
  })

  it('quyền đúng bằng {storage, sidePanel} — không hơn', () => {
    expect([...manifest.permissions].sort()).toEqual(['sidePanel', 'storage'])
  })

  it.each(QUYEN_CAM)('KHÔNG xin quyền %s', (q) => {
    expect(manifest.permissions).not.toContain(q)
    expect(manifest.optional_permissions ?? []).not.toContain(q)
  })

  it('KHÔNG có optional_host_permissions', () => {
    expect(manifest.optional_host_permissions).toBeUndefined()
  })

  it('service worker là module đóng gói sẵn, không phải mã tải từ xa', () => {
    expect(manifest.background.type).toBe('module')
    expect(manifest.background.service_worker).toBe('src/service-worker.js')
    expect(existsSync(join(GOC, manifest.background.service_worker))).toBe(true)
  })

  it('KHÔNG khai externally_connectable hay web_accessible_resources', () => {
    expect(manifest.externally_connectable).toBeUndefined()
    expect(manifest.web_accessible_resources).toBeUndefined()
  })

  it('mọi tệp manifest trỏ tới đều có thật trong gói', () => {
    const can = [
      manifest.background.service_worker,
      manifest.side_panel.default_path,
      manifest.options_page,
      ...Object.values(manifest.icons),
      ...Object.values(manifest.action.default_icon),
    ]
    for (const d of can) expect(existsSync(join(GOC, d)), `thiếu tệp ${d}`).toBe(true)
  })
})

describe('quét mã nguồn — không có đường nào đọc trang web hay giấu bí mật', () => {
  it.each([
    ['đọc/ghi DOM của tab', /chrome\.scripting|executeScript|insertCSS/],
    ['đọc thông tin tab', /chrome\.tabs\.query|tab\.url|captureVisibleTab/],
    ['chặn request', /chrome\.webRequest|declarativeNetRequest/],
    ['tải tệp', /chrome\.downloads/],
    ['lịch sử / dấu trang', /chrome\.history|chrome\.bookmarks/],
    ['đọc bộ nhớ tạm', /navigator\.clipboard\.read/],
    ['mã động', /\beval\(|new Function\(/],
    ['nạp script từ xa', /import\(\s*['"`]https?:/],
  ])('không có: %s', (_ten, mau) => {
    const dinh = NGUON.filter((t) => mau.test(t.chu)).map((t) => t.duong_dan)
    expect(dinh).toEqual([])
  })

  it('không có mẫu API key nào nằm trong mã', () => {
    // Gemini (AIza…), OpenAI (sk-…), và chuỗi gán bí mật kiểu `apiKey = "..."`.
    const mau = /AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9]{20,}|(api[_-]?key|secret|password)\s*[:=]\s*['"][^'"]{8,}/i
    const dinh = NGUON.filter((t) => mau.test(t.chu)).map((t) => t.duong_dan)
    expect(dinh).toEqual([])
  })

  it('không nhúng địa chỉ http(s) ra ngoài loopback', () => {
    const mau = /https?:\/\/(?!localhost|127\.0\.0\.1)[a-z0-9-]+\.[a-z]/gi
    for (const t of NGUON) {
      const dinh = t.chu.match(mau) ?? []
      expect(dinh, `${t.duong_dan} có địa chỉ ngoài: ${dinh.join(', ')}`).toEqual([])
    }
  })

  it('không có script nội tuyến trong HTML (CSP của MV3 chặn, phải phát hiện sớm)', () => {
    for (const t of NGUON.filter((x) => x.duong_dan.endsWith('.html'))) {
      const the_script = t.chu.match(/<script\b[^>]*>/g) ?? []
      for (const the of the_script) {
        expect(the, `${t.duong_dan}: thẻ script thiếu src`).toContain('src=')
      }
      expect(t.chu, `${t.duong_dan}: có thuộc tính on*`).not.toMatch(/\son(click|load|error)=/i)
    }
  })

  it('dữ liệu máy chủ vào DOM bằng textContent, không bằng innerHTML', () => {
    const dinh = NGUON.filter((t) => /\.innerHTML\s*=|outerHTML\s*=|insertAdjacentHTML/.test(t.chu))
    expect(dinh.map((t) => t.duong_dan)).toEqual([])
  })

  it('không có vòng hỏi ngầm chạy nền', () => {
    const dinh = NGUON.filter((t) => /setInterval\(|chrome\.alarms/.test(t.chu))
    expect(dinh.map((t) => t.duong_dan)).toEqual([])
  })

  it('service worker KHÔNG giữ trạng thái quan trọng trong biến toàn cục', () => {
    const sw = readFileSync(join(GOC, 'src/service-worker.js'), 'utf8')
    // Chỉ được có khai báo import + đăng ký sự kiện; không `let`/`var` ở mức tệp.
    expect(sw).not.toMatch(/^\s*(let|var)\s/m)
    expect(sw).not.toMatch(/^const\s+\w+\s*=\s*(\[|\{)/m)
  })
})

describe('tài liệu đi kèm gói', () => {
  it('có PRIVACY.md và README.md', () => {
    expect(existsSync(join(GOC, 'PRIVACY.md'))).toBe(true)
    expect(existsSync(join(GOC, 'README.md'))).toBe(true)
  })

  it('PRIVACY.md nói rõ những thứ KHÔNG lưu', () => {
    const chu = readFileSync(join(GOC, 'PRIVACY.md'), 'utf8')
    for (const tu of ['API key', 'OCR', 'bản dịch', 'content_script', 'host_permissions']) {
      expect(chu).toContain(tu)
    }
  })

  it('không có bước build — thứ Chrome nạp chính là thứ trong repo', () => {
    const pkg = JSON.parse(readFileSync(join(GOC, 'package.json'), 'utf8'))
    expect(pkg.scripts.build).toBeUndefined()
    expect(existsSync(join(GOC, 'dist'))).toBe(false)
  })
})
