import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const contentSrc = fs.readFileSync(path.join(ROOT, 'src', 'content', 'index.js'), 'utf8')

function loadLaVungSfx() {
  const m = contentSrc.match(/(  const TU_TUONG_THANH_SFX =[\s\S]*?\n  function laVungSfx\(v\) \{[\s\S]*?\n  \})/)
  if (!m) throw new Error('Không tìm thấy laVungSfx trong src/content/index.js')
  const build = new Function(`${m[1]}\nreturn laVungSfx;`)
  return build()
}

describe('nhận diện SFX và bảo vệ bóng thoại có dấu ba chấm', () => {
  const laVungSfx = loadLaVungSfx()

  it('không coi thoại ngắn 1-2 từ có "..." hay "…" hay "~~~" là SFX để khỏi nuốt bản dịch (p5)', () => {
    expect(laVungSfx({ chu_dich: 'Ồ...', chu_goc: '啪…' })).toBe(false)
    expect(laVungSfx({ chu_dich: 'Hừm…', chu_goc: '唔…' })).toBe(false)
    expect(laVungSfx({ chu_dich: 'Này...!', chu_goc: '喂…!' })).toBe(false)
    expect(laVungSfx({ chu_dich: 'Hả...!', chu_goc: 'えっ…!', _laBongKhepKin: true })).toBe(false)
    expect(laVungSfx({ chu_dich: 'Đi thôi~~~', chu_goc: '啪…啪吼噢~~~' })).toBe(false)
  })

  it('vẫn nhận đúng từ tượng thanh có lặp chữ cái thật hoặc thuộc danh sách SFX', () => {
    expect(laVungSfx({ chu_dich: 'Grrrr...', chu_goc: 'ギュルル' })).toBe(true)
    expect(laVungSfx({ chu_dich: 'Áááá!!!', chu_goc: 'ぎゃああ' })).toBe(true)
    expect(laVungSfx({ chu_dich: 'RẦM!', chu_goc: 'ドン' })).toBe(true)
    expect(laVungSfx({ chu_dich: 'ĐÙNG ĐÙNG', chu_goc: 'ゴゴゴ' })).toBe(true)
    expect(laVungSfx({ chu_dich: '', chu_goc: 'WHOOSH' })).toBe(true)
  })

  it('đồng bộ phiên bản 5.24.5 trên manifest, package, popup và options', () => {
    const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'manifest.json'), 'utf8'))
    const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'))
    const popupHtml = fs.readFileSync(path.join(ROOT, 'src', 'popup', 'index.html'), 'utf8')
    const optionsHtml = fs.readFileSync(path.join(ROOT, 'src', 'options', 'index.html'), 'utf8')
    expect(manifest.version).toBe('5.24.6')
    expect(pkg.version).toBe('5.24.6')
    expect(popupHtml).toContain('v5.24.6')
    expect(optionsHtml).toContain('v5.24.6')
  })

  it('giữ nguyên SFX ngoài bóng thoại (주절 - -, ~~~꼬르르, GULP, ビュウ ガタガタ) nhưng giữ thoại thật (응응, 선배..., 나니)', () => {
    expect(laVungSfx({ ban_dich: 'Lầm bầm - -', chu_goc: '주절 - -', _laBongKhepKin: true })).toBe(true)
    expect(laVungSfx({ ban_dich: 'Lầm bầm~', chu_goc: '주절 ~', _laBongKhepKin: false })).toBe(true)
    expect(laVungSfx({ ban_dich: 'Sôi bụng', chu_goc: '~~~꼬르르', _laBongKhepKin: false })).toBe(true)
    expect(laVungSfx({ ban_dich: 'Ực', chu_goc: 'GULP', _laBongKhepKin: false })).toBe(true)
    expect(laVungSfx({ ban_dich: 'Tức', chu_goc: '픽', _laBongKhepKin: false })).toBe(true)
    expect(laVungSfx({ ban_dich: 'Vù lạch cạch', chu_goc: 'ビュウ ガタガタ', _laBongKhepKin: false })).toBe(true)
    expect(laVungSfx({ ban_dich: 'Ừ, ừ.', chu_goc: '응응', _laBongKhepKin: true })).toBe(false)
    expect(laVungSfx({ ban_dich: 'Ừ, ừ.', chu_goc: '응응', _laBongKhepKin: false })).toBe(false)
    expect(laVungSfx({ ban_dich: 'Tiền bối...', chu_goc: '선배...', _laBongKhepKin: false })).toBe(false)
    expect(laVungSfx({ ban_dich: 'Cái gì...?', chu_goc: 'なに…？', _laBongKhepKin: false })).toBe(false)
  })

  it('giữ ngưỡng nhận biên panel occluded (>= 0.52) và chặn screentone khỏi wToi (lum3x3 <= 72)', () => {
    expect(contentSrc).toContain('spanWB * 0.52')
    expect(contentSrc).toContain('spanHB * 0.52')
    expect(contentSrc).toContain('lum3x3[npos] <= 72')
    expect(contentSrc).toContain('laHatScreentoneGanXam')
  })
})
