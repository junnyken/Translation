/** Phủ chữ dịch lên trang truyện đang đọc (E19-4).
 *
 * Tiêm khi người dùng bấm biểu tượng, không tiêm sẵn vào mọi trang.
 *
 * Nạp hai module thuần bằng `import()` động thay vì chép lại logic vào đây: chúng có bộ test
 * riêng (`tests/chon-anh.test.js`, `tests/toa-do.test.js`), còn tệp này chỉ sống được trong
 * trình duyệt thật. Chép lại = có hai bản và một bản sẽ lệch.
 */
;(async () => {
  const CO = '__translation_doc_truyen__'
  if (window[CO]?.dangChay) return
  window[CO] = window[CO] || { daDich: new Map() }
  window[CO].dangChay = true

  const { chonTrangTruyen } = await import(chrome.runtime.getURL('src/lib/chon-anh.js'))
  const { coChu, quyDoi, sanSangQuyDoi } = await import(chrome.runtime.getURL('src/lib/toa-do.js'))

  const bang = document.createElement('div')
  bang.style.cssText = [
    'position:fixed', 'z-index:2147483647', 'right:16px', 'bottom:16px',
    'max-width:320px', 'padding:10px 12px', 'border-radius:8px',
    'background:#111', 'color:#fff', 'font:13px/1.45 system-ui,sans-serif',
    'box-shadow:0 4px 16px rgba(0,0,0,.35)', 'white-space:pre-wrap',
  ].join(';')
  document.body.appendChild(bang)
  const noi = (t) => { bang.textContent = t }
  const xong = (t, giay = 6) => { noi(t); setTimeout(() => bang.remove(), giay * 1000) }

  function vePhu(el, vung) {
    document.getElementById('translation-lop-phu')?.remove()
    const lop = document.createElement('div')
    lop.id = 'translation-lop-phu'
    lop.style.cssText = 'position:absolute;z-index:2147483646;pointer-events:none'
    document.body.appendChild(lop)

    const ve = () => {
      if (!el.isConnected || !sanSangQuyDoi(el)) { lop.remove(); return }
      const r = el.getBoundingClientRect()
      lop.innerHTML = ''
      // Toạ độ TÀI LIỆU (cộng scroll) nên lớp phủ trôi theo trang khi cuộn, không phải vẽ lại
      // ở mỗi khung hình.
      Object.assign(lop.style, {
        left: `${r.left + window.scrollX}px`, top: `${r.top + window.scrollY}px`,
        width: `${r.width}px`, height: `${r.height}px`,
      })

      for (const v of vung) {
        if (!v.ban_dich) continue
        const o = quyDoi(v, {
          naturalWidth: el.naturalWidth, naturalHeight: el.naturalHeight,
          clientWidth: r.width, clientHeight: r.height,
        })
        const hop = document.createElement('div')
        hop.textContent = v.ban_dich
        hop.title = v.chu_goc || ''
        Object.assign(hop.style, {
          position: 'absolute',
          left: `${o.left}px`, top: `${o.top}px`,
          width: `${o.width}px`, height: `${o.height}px`,
          // Nền đục để che chữ gốc: chế độ này KHÔNG xoá chữ khỏi ảnh, không che thì hai lớp
          // chữ chồng lên nhau và không đọc được lớp nào.
          background: 'rgba(255,255,255,.94)', color: '#000',
          border: v.kem_tin_cay ? '1px dashed #e0a800' : '1px solid rgba(0,0,0,.15)',
          borderRadius: '6px',
          font: `${coChu(o, v.ban_dich.length)}px/1.2 system-ui,sans-serif`,
          padding: '2px 3px', boxSizing: 'border-box',
          display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center',
          // Chữ Việt dài hơn chữ Nhật và chế độ này KHÔNG chạy bước căn chữ, nên không có bảo
          // đảm nào là chữ vừa ô. Cho cuộn trong ô còn hơn cắt mất chữ.
          overflow: 'auto', overflowWrap: 'anywhere', pointerEvents: 'auto',
        })
        lop.appendChild(hop)
      }
    }

    ve()
    // Đổi cỡ cửa sổ / trang tự co ảnh ⇒ vẽ lại, nếu không lớp phủ lệch khỏi bong bóng.
    new ResizeObserver(ve).observe(el)
    window.addEventListener('resize', ve, { passive: true })
  }

  const mo_ta = [...document.images].map((el) => {
    const r = el.getBoundingClientRect()
    return {
      el, src: el.currentSrc || el.src,
      naturalWidth: el.naturalWidth, naturalHeight: el.naturalHeight,
      clientWidth: r.width, clientHeight: r.height, top: r.top, bottom: r.bottom,
    }
  })
  const chon = chonTrangTruyen(mo_ta, { caoKhungNhin: window.innerHeight })
  if (!chon.anh) {
    window[CO].dangChay = false
    xong(
      `Không tìm thấy trang truyện trên màn hình.\n${chon.ly_do}.\n`
      + `Đã xem ${mo_ta.length} ảnh.`
      + (chon.bi_loai.length ? `\nVí dụ bị loại: ${chon.bi_loai[0].ly_do.join(', ')}.` : '')
      + `\n\nTrang vẽ bằng canvas hoặc chống sao chép thì tiện ích không lấy được ảnh.`,
      12,
    )
    return
  }

  const anh = chon.anh
  // Nhớ theo URL ảnh: bấm lại đúng trang đó thì vẽ lại ngay, không chạy lại 45 giây. Máy chủ cố
  // ý KHÔNG lọc trùng — làm vậy sẽ cần thêm cột vân tay và một lượt băm mỗi lần tải lên.
  const da_co = window[CO].daDich.get(anh.src)
  if (da_co) {
    vePhu(anh.el, da_co)
    window[CO].dangChay = false
    xong('Đã phủ lại bản dịch có sẵn.', 3)
    return
  }

  noi(`Đang dịch trang này…\n(${chon.ly_do})`)

  let tra
  try {
    tra = await chrome.runtime.sendMessage({ viec: 'dich-anh', url: anh.src })
  } catch (e) {
    window[CO].dangChay = false
    xong(`Không gọi được tiện ích nền: ${e}`, 10)
    return
  }
  window[CO].dangChay = false

  if (!tra?.ok) {
    const them = tra?.ma === 401
      ? '\n\nPhiên đăng nhập đã hết. Mở Tuỳ chọn của tiện ích để đăng nhập lại.'
      : ''
    xong(`Không dịch được.\n${tra?.loi || 'không rõ lý do'}${them}`, 12)
    return
  }

  window[CO].daDich.set(anh.src, tra.vung)
  vePhu(anh.el, tra.vung)
  const co_chu = tra.vung.filter((v) => v.ban_dich).length
  xong(`Xong: ${co_chu}/${tra.vung.length} bong bóng có bản dịch.`, 5)
})()
