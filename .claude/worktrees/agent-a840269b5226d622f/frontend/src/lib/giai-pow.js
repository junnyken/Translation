/** Giải proof-of-work chống bot của `/auth/register` (đường dự phòng khi không có Turnstile).
 *
 * Tìm chuỗi số `dapAn` sao cho `sha256("<ma>:<dapAn>")` có ít nhất `doKho` bit 0 ở đầu —
 * cùng luật với `_kiem_tra_ma_thach_thuc_pow` phía máy chủ. Độ khó 16 ≈ 65 nghìn lượt băm.
 */

function soBit0Dau(bytes) {
  let dem = 0
  for (const b of bytes) {
    if (b === 0) { dem += 8; continue }
    return dem + Math.clz32(b) - 24
  }
  return dem
}

export async function giaiPow(ma, doKho, { gioiHan = 1 << 24 } = {}) {
  const ma_hoa = new TextEncoder()
  for (let i = 0; i < gioiHan; i += 1) {
    const dapAn = String(i)
    const bam = await crypto.subtle.digest('SHA-256', ma_hoa.encode(`${ma}:${dapAn}`))
    if (soBit0Dau(new Uint8Array(bam)) >= doKho) return dapAn
  }
  throw new Error('Không giải được thách thức chống bot')
}
