import { describe, expect, it } from 'vitest'
import { createHash } from 'node:crypto'
import { giaiPow } from './giai-pow.js'

function bit0Dau(hex) {
  const n = BigInt(`0x${hex}`)
  return 256 - n.toString(2).length
}

describe('giaiPow', () => {
  it('tìm được đáp án đạt đúng độ khó máy chủ kiểm', async () => {
    const ma = '1700000000.abcd1234.deadbeef'
    const dapAn = await giaiPow(ma, 10)
    expect(dapAn).toMatch(/^\d+$/)
    const hex = createHash('sha256').update(`${ma}:${dapAn}`).digest('hex')
    expect(bit0Dau(hex)).toBeGreaterThanOrEqual(10)
  })

  it('báo lỗi khi vượt giới hạn lượt thử thay vì treo', async () => {
    await expect(giaiPow('x', 64, { gioiHan: 50 })).rejects.toThrow()
  })
})
