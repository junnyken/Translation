/** Thiếu cấu hình thì phải nói ĐÚNG thiếu cái gì, và câu nói phải đưa người dùng tới chỗ sửa.
 *
 * Ca thật 07/09: người dùng nạp tiện ích, bấm dịch, nhận "Chưa đặt địa chỉ máy chủ Translation."
 * — đúng, nhưng họ không tìm ra trang tuỳ chọn (nó nằm sau chrome://extensions → Chi tiết → kéo
 * xuống cuối). Câu báo lỗi đúng mà không đưa tới chỗ sửa được thì chỉ là một câu báo lỗi.
 */
import { describe, expect, it } from 'vitest'
import { lyDoThieuCauHinh } from '../src/lib/api.js'

describe('kiểm cấu hình trước khi dịch', () => {
  it('đủ địa chỉ và mã phiên thì không cản', () => {
    expect(lyDoThieuCauHinh({ diaChi: 'https://x', maPhien: 'abc' })).toBeNull()
  })

  it('thiếu địa chỉ: nói rõ thiếu ĐỊA CHỈ, không nói chung chung', () => {
    const t = lyDoThieuCauHinh({ diaChi: '', maPhien: 'abc' })
    expect(t).toMatch(/địa chỉ/i)
    expect(t).toMatch(/đã mở trang cài đặt/i)
  })

  it('có địa chỉ nhưng chưa đăng nhập: nói ĐĂNG NHẬP, không đổ cho địa chỉ', () => {
    const t = lyDoThieuCauHinh({ diaChi: 'https://x', maPhien: '' })
    expect(t).toMatch(/đăng nhập/i)
    expect(t).not.toMatch(/địa chỉ/i)
  })

  it('thiếu cả hai thì báo ĐỊA CHỈ trước — đó là thứ phải nhập trước', () => {
    expect(lyDoThieuCauHinh({ diaChi: '', maPhien: '' })).toMatch(/địa chỉ/i)
  })

  it('mọi câu đều CHỈ ĐƯỜNG, không chỉ báo lỗi suông', () => {
    for (const c of [{ diaChi: '', maPhien: '' }, { diaChi: 'https://x', maPhien: '' }]) {
      expect(lyDoThieuCauHinh(c)).toMatch(/đã mở trang cài đặt/i)
    }
  })
})
