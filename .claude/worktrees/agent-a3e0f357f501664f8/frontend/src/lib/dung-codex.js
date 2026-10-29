import { useEffect, useState } from 'react'
import * as api from '../api.js'

/** Trạng thái engine `chatgpt_codex` đọc từ `/healthz`, dùng chung cho mọi bộ chọn cách dịch.
 *
 * Một lời gọi cho cả trang (không mỗi bộ chọn một lời), và đăng nhập/đăng xuất ở khu quản trị
 * gọi `lamMoiCodex()` để các bộ chọn đổi theo ngay, không phải tải lại trang.
 * Lỗi mạng ⇒ coi như tắt: ẩn một lựa chọn an toàn hơn hiện một lựa chọn chắc chắn hỏng.
 */
const TAT = { bat: false, da_dang_nhap: false }
let giaTri = TAT
let daNap = false
const nguoiNghe = new Set()

function dat(v) {
  giaTri = v
  nguoiNghe.forEach((f) => f(v))
}

export async function lamMoiCodex() {
  try {
    const h = await api.layHealthz()
    dat({ bat: h?.codex?.bat === true, da_dang_nhap: h?.codex?.da_dang_nhap === true })
  } catch {
    dat(TAT)
  }
  daNap = true
}

/** Chỉ dùng cho test. */
export function datLaiCodex() { giaTri = TAT; daNap = false }

export function useCodex() {
  const [v, setV] = useState(giaTri)
  useEffect(() => {
    nguoiNghe.add(setV)
    if (!daNap) lamMoiCodex()
    else setV(giaTri)
    return () => { nguoiNghe.delete(setV) }
  }, [])
  return v
}
