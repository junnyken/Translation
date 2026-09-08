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
  // `dangXepHang`: src đang được xếp hàng trước (§ dưới) — chặn xếp trùng khi bấm dịch liên tiếp
  // nhiều trang trước khi lượt xếp hàng của trang trước kịp xong.
  window[CO] = window[CO] || { daDich: new Map(), dangXepHang: new Set() }
  window[CO].dangChay = true

  const { chonTrangKeTiep, chonTrangTruyen } = await import(chrome.runtime.getURL('src/lib/chon-anh.js'))
  const { coChu, quyDoi, sanSangQuyDoi } = await import(chrome.runtime.getURL('src/lib/toa-do.js'))

  const bang = document.createElement('div')
  bang.style.cssText = [
    'position:fixed', 'z-index:2147483647', 'right:16px', 'bottom:16px',
    'max-width:320px', 'padding:10px 12px', 'border-radius:8px',
    'background:#111', 'color:#fff', 'font:13px/1.45 system-ui,sans-serif',
    'box-shadow:0 4px 16px rgba(0,0,0,.35)', 'white-space:pre-wrap',
  ].join(';')
  document.body.appendChild(bang)
  const V = chrome.runtime.getManifest().version
  // Gắn phiên bản vào MỌI thông báo: người dùng tải gói .zip về máy nên bản đang chạy có thể cũ
  // hơn bản vừa sửa, và hai lượt thử vừa rồi không có cách nào phân biệt "bản sửa không ăn thua"
  // với "bản sửa chưa tới máy".
  const noi = (t) => { bang.textContent = `[v${V}] ${t}` }
  const xong = (t, giay = 6) => { noi(t); setTimeout(() => bang.remove(), giay * 1000) }

  function vePhu(el, vung) {
    document.getElementById('translation-lop-phu')?.remove()
    const lop = document.createElement('div')
    lop.id = 'translation-lop-phu'
    // `fixed` + toạ độ KHUNG NHÌN, gắn vào <html> chứ không vào <body>.
    //
    // Bản đầu dùng `absolute` + toạ độ tài liệu (cộng `window.scrollX/scrollY`) và gắn vào
    // `document.body`. Hỏng trên trang thật đầu tiên thử (07/09) — lớp phủ rơi xuống góc dưới
    // bên trái, ngoài hẳn ảnh. Hai lỗi chồng nhau, cả hai đều không test đơn vị nào bắt được:
    //
    // 1. `absolute` neo theo TỔ TIÊN ĐÃ ĐỊNH VỊ gần nhất, không phải theo tài liệu. Trang đó là
    //    lightbox nên ảnh nằm trong hộp đã định vị ⇒ phép tính toạ độ tài liệu rơi vào hệ quy
    //    chiếu khác.
    // 2. Cộng độ cuộn trong lightbox là sai hẳn: ảnh nằm trong hộp cố định, trang nền không
    //    cuộn, nên phần cộng thêm đẩy lớp phủ lệch đúng bằng độ cuộn.
    //
    // `getBoundingClientRect()` vốn đã trả toạ độ khung nhìn, nên `fixed` dùng thẳng được, không
    // phải cộng trừ gì. Gắn vào `documentElement` để không dính `transform` của <body>.
    lop.style.cssText = 'position:fixed;z-index:2147483646;pointer-events:none'
    document.documentElement.appendChild(lop)

    // Khai báo TRƯỚC `ve`, vì `ve` gọi `dung`. `const` không được nâng lên đầu phạm vi: để
    // `dung` ở dưới thì nó chỉ chạy đúng nhờ thứ tự gọi may mắn, và một lần đổi thứ tự là ném
    // "Cannot access before initialization" ngay lúc bấm — không phải lúc nạp, nên mắt thường
    // không thấy. Đúng bẫy này đã cắn một lần ở giao diện web (BangChuaCoChu.jsx).
    const ro = new ResizeObserver(() => ve())
    const dung = () => {
      ro.disconnect()
      window.removeEventListener('scroll', goiVe, true)
      window.removeEventListener('resize', goiVe)
      lop.remove()
    }
    const goiVe = () => ve()

    const ve = () => {
      if (!el.isConnected || !sanSangQuyDoi(el)) { dung(); return }
      const r = el.getBoundingClientRect()
      lop.innerHTML = ''
      if (r.width < 1 || r.height < 1) { lop.style.display = 'none'; return }
      lop.style.display = ''
      Object.assign(lop.style, {
        left: `${r.left}px`, top: `${r.top}px`,
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
          // Nền đục HẾT CỠ để che chữ gốc: chế độ này KHÔNG xoá chữ khỏi ảnh, còn hở dù chỉ vài
          // % cũng lộ chữ Nhật mờ mờ chồng sau chữ Việt (thấy trên trang thật 07/09, để ở .94).
          background: 'rgba(255,255,255,1)', color: '#000',
          border: v.kem_tin_cay ? '1px dashed #e0a800' : '1px solid rgba(0,0,0,.15)',
          borderRadius: '6px',
          font: `${coChu(o, v.ban_dich.length)}px/1.2 system-ui,sans-serif`,
          padding: '2px 3px', boxSizing: 'border-box',
          display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center',
          // Chữ Việt dài hơn chữ Nhật và chế độ này KHÔNG chạy bước căn chữ, nên không có bảo
          // đảm nào là chữ vừa ô. Cuộn là LƯỚI AN TOÀN cuối cùng — vòng co chữ dưới đây mới là
          // thứ chính, chạy trước khi cần tới cuộn.
          overflow: 'auto', overflowWrap: 'anywhere', pointerEvents: 'auto',
        })
        lop.appendChild(hop)

        // `coChu()` chỉ ước lượng bằng diện tích/số ký tự, không đo chữ thật — không có gì bảo
        // đảm nó vừa khung. Đo THẬT bằng scrollHeight/scrollWidth sau khi đã nằm trong DOM (trước
        // đó trình duyệt chưa layout, đọc số lúc đó là rác), rồi co dần tới khi vừa hoặc chạm sàn.
        let px = coChu(o, v.ban_dich.length)
        while (px > 8 && (hop.scrollHeight > hop.clientHeight + 1 || hop.scrollWidth > hop.clientWidth + 1)) {
          px -= 1
          hop.style.fontSize = `${px}px`
        }
      }
    }

    // Toạ độ khung nhìn đổi mỗi khi cuộn, nên PHẢI vẽ lại khi cuộn — đây là cái giá của
    // `fixed`, và là cái giá đúng: đổi lại nó không phụ thuộc tổ tiên nào cả.
    //
    // `capture: true` để bắt cả cuộn BÊN TRONG một hộp con (lightbox cuộn nội bộ, trang nền
    // đứng yên) — nghe ở `window` không có capture sẽ bỏ sót đúng ca đó.
    ve()
    ro.observe(el)
    window.addEventListener('scroll', ve, { passive: true, capture: true })
    window.addEventListener('resize', ve, { passive: true })
  }

  // Đọc ẢNH THẬT bằng canvas ngay tại đây trước khi nhờ service worker tải lại bằng URL.
  //
  // Bắt buộc phải thử ở ĐÂY: `blob:`/`data:` mà trang tự tạo (MangaPlus tự giải mã ảnh rồi phát
  // qua `blob:` — đo được 07/09) chỉ sống trong đúng tài liệu đã tạo ra nó. Service worker là một
  // ngữ cảnh THỰC THI khác (kể cả cùng origin), `fetch()` một `blob:` từ đó luôn ném lỗi mạng
  // trần trụi "Failed to fetch" — không phải lỗi cấu hình, không có cách nào sửa bằng quyền hay
  // header. Canvas ở ĐÚNG tài liệu đang hiển thị ảnh thì không bị coi là khác nguồn, nên đọc được.
  //
  // Ảnh https bình thường (đa số trang) thì NGƯỢC LẠI: rất nhiều máy chủ không gắn CORS header,
  // vẽ lên canvas ở đây sẽ "nhiễm bẩn" (`SecurityError` khi xuất byte) — đó là lý do bản đầu cố ý
  // tránh canvas, dồn hết việc tải xuống service worker. Nên thử canvas TRƯỚC, hỏng thì rơi về
  // đường cũ (gửi URL, để service worker tự tải bằng `host_permissions`) — không đoán trước loại
  // ảnh nào đi đường nào.
  async function docByteAnh(el) {
    try {
      const canvas = document.createElement('canvas')
      canvas.width = el.naturalWidth
      canvas.height = el.naturalHeight
      canvas.getContext('2d').drawImage(el, 0, 0)
      const blob = await new Promise((resolve, reject) => {
        canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('canvas rỗng'))), 'image/png')
      })
      const bytes = new Uint8Array(await blob.arrayBuffer())
      let nhi_phan = ''
      for (let i = 0; i < bytes.length; i += 0x8000) {
        nhi_phan += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
      }
      return { anh_base64: btoa(nhi_phan), anh_mime: blob.type || 'image/png' }
    } catch {
      // Nhiễm bẩn (ảnh cross-origin không CORS) hoặc lỗi khác — rơi về gửi URL cho service worker.
      return { anh_base64: null, anh_mime: null }
    }
  }

  /**
   * Xếp hàng dịch trước TỐI ĐA MỘT trang kế tiếp — trong lúc người dùng còn đang đọc trang hiện
   * tại, không phải quét cả chapter (cố ý loại ở `PLAN_E19` §8, xem `docs/ARCH.md` §E19.6f).
   *
   * Chạy NỀN, không chờ, không báo lỗi ra thông báo chính: đây là việc làm trước cho êm, người
   * dùng không đang đứng chờ nó như trang họ vừa bấm. Chỉ nạp được trên trang cuộn dọc liên tục
   * giữ sẵn vài trang kế cận trong DOM (đo trên MangaPlus: 22-36 `<img>` cùng lúc) — trang kiểu
   * "bấm Tiếp" mới nạp ảnh mới thì `chonTrangKeTiep` trả `null`, không có gì để xếp hàng.
   */
  function xepHangTrangKeTiep(mo_ta_hien_tai, boQuaSrc) {
    const ke = chonTrangKeTiep(mo_ta_hien_tai, { caoKhungNhin: window.innerHeight, boQuaSrc })
    if (!ke.anh) return
    const src = ke.anh.src
    if (window[CO].daDich.has(src) || window[CO].dangXepHang.has(src)) return
    window[CO].dangXepHang.add(src)
    ;(async () => {
      try {
        const { anh_base64, anh_mime } = await docByteAnh(ke.anh.el)
        const tra_ke = await chrome.runtime.sendMessage({
          viec: 'dich-anh', url: src, anh_base64, anh_mime,
        })
        if (tra_ke?.ok) window[CO].daDich.set(src, tra_ke.vung)
      } catch {
        // Im lặng có chủ đích — bấm dịch lại trang đó sau này sẽ chạy như bình thường (không
        // cache), không phải lỗi cần người dùng xử lý ngay.
      } finally {
        window[CO].dangXepHang.delete(src)
      }
    })()
  }

  // Tách hàm vì cần gọi LẠI sau khi chờ dịch xong (~45s) để xếp hàng trước trang kế tiếp — dùng
  // mô tả chụp từ ĐẦU quy trình lúc đó đã cũ 45 giây, đúng loại "phần tử có thể đã chết giữa
  // chừng" vừa gặp ở chính ảnh đang dịch (§E19.6e).
  function layMoTa() {
    return [...document.images].map((el) => {
      const r = el.getBoundingClientRect()
      // `filter` áp lên chính thẻ HOẶC một tổ tiên (lightbox hay bọc ảnh nền trong một lớp riêng
      // rồi mờ cả lớp đó, không mờ thẳng trên <img>). Leo lên vài cấp cho chắc, không chỉ đọc trên el.
      let mo = false
      for (let n = el, dem = 0; n instanceof Element && dem < 4; n = n.parentElement, dem++) {
        const f = getComputedStyle(n).filter
        if (f && f !== 'none') { mo = true; break }
      }
      return {
        el, src: el.currentSrc || el.src,
        naturalWidth: el.naturalWidth, naturalHeight: el.naturalHeight,
        clientWidth: r.width, clientHeight: r.height, top: r.top, bottom: r.bottom, mo,
      }
    })
  }

  const mo_ta = layMoTa()
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
    xepHangTrangKeTiep(layMoTa(), anh.src)
    return
  }

  noi(`Đang dịch trang này…\n(${chon.ly_do})`)

  const { anh_base64, anh_mime } = await docByteAnh(anh.el)

  let tra
  try {
    tra = await chrome.runtime.sendMessage({ viec: 'dich-anh', url: anh.src, anh_base64, anh_mime })
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
    // "Failed to fetch" không kèm mã lỗi HTTP nào — không phân biệt được "mạng chập chờn" với
    // "trang cố ý chặn tải ảnh" (URL ký hạn dùng ngắn, hoặc <img src> là `blob:` chỉ sống được
    // trong đúng tab đang mở nó, service worker ở ngữ cảnh khác tải lại chắc chắn hỏng). Nhiều
    // trang manga (vd MangaPlus) còn chặn cả chuột phải lẫn phím tắt mở DevTools nên người dùng
    // không tự soi được — in thẳng vào đây thay vì bắt đi tìm cách khác.
    const do_do = [
      `thẻ: <${anh.el.tagName.toLowerCase()}>`,
      `src: ${String(anh.src).slice(0, 60)}${anh.src.length > 60 ? '…' : ''}`,
      `ảnh thật: ${anh.el.naturalWidth}x${anh.el.naturalHeight}`,
      `số <img>: ${document.images.length} · số <canvas>: ${document.getElementsByTagName('canvas').length}`,
    ].join('\n')
    xong(`Không dịch được.\n${tra?.loi || 'không rõ lý do'}${them}\n\n${do_do}`, 20)
    return
  }

  window[CO].daDich.set(anh.src, tra.vung)
  vePhu(anh.el, tra.vung)
  // Chụp lại DOM MỚI (không dùng `mo_ta` cũ 45 giây) — độc lập với việc lớp phủ trang hiện tại
  // có vẽ được hay không: dù trang này chết giữa chừng, vị trí đọc thật của người dùng bây giờ
  // vẫn đáng để xếp hàng trước, không phụ thuộc kết quả vẽ lớp phủ.
  xepHangTrangKeTiep(layMoTa(), anh.src)
  const co_chu = tra.vung.filter((v) => v.ban_dich).length

  // Kèm SỐ ĐO vị trí. Hai lượt sửa vừa rồi đều đoán sai nguyên nhân lớp phủ lệch, vì ảnh chụp
  // màn hình cho thấy "sai" nhưng không cho biết sai ở đâu. Ba con số dưới đây phân biệt được:
  //   - khung ảnh ≈ chỗ ảnh đang hiện  ⇒ chọn đúng phần tử, lỗi ở phép đặt lớp phủ
  //   - khung ảnh ≠ chỗ ảnh đang hiện  ⇒ vẽ nhầm phần tử (hai <img> cùng src, bản nền vs bản lightbox)
  const r = anh.el.getBoundingClientRect()
  const lop = document.getElementById('translation-lop-phu')
  const lop_r = lop?.getBoundingClientRect()
  const so_do = [
    `ảnh: ${Math.round(r.left)},${Math.round(r.top)} ${Math.round(r.width)}x${Math.round(r.height)}`,
    `lớp phủ: ${lop_r ? `${Math.round(lop_r.left)},${Math.round(lop_r.top)} ${Math.round(lop_r.width)}x${Math.round(lop_r.height)}` : 'KHÔNG CÓ'}`,
    `ảnh thật: ${anh.el.naturalWidth}x${anh.el.naturalHeight}`,
    `số <img> đủ lớn: ${1 + chon.bi_loai.length} xét, chọn 1`,
  ].join('\n')

  // `vePhu` tự gỡ lớp phủ ngay khi phát hiện `el.isConnected === false` (xem hàm `dung` bên
  // trên) — đúng để không vẽ rác lên một phần tử đã chết, nhưng "Xong: X/Y" phía dưới vẫn nói
  // như thể mọi thứ ổn trong khi màn hình KHÔNG hiện gì cả. Đo được 08/09 trên MangaPlus: sau
  // ~45s chờ dịch, `<img>` gốc đã bị chính trang gỡ/thay (SPA tự vẽ lại), lớp phủ vừa tạo xong
  // đã tự huỷ. Phải nói ĐÚNG "không vẽ được" thay vì "xong" — im lặng thất bại còn tệ hơn báo lỗi.
  if (!anh.el.isConnected || !lop) {
    xong(
      `Dịch xong (${co_chu}/${tra.vung.length} bong bóng có bản dịch) NHƯNG không vẽ được lên `
      + `trang: ảnh đã biến mất khỏi trang trong lúc chờ (trang tự vẽ lại/đổi ảnh khi bạn cuộn `
      + `hoặc trang tự làm mới nội dung). Cuộn về đúng trang rồi bấm dịch lại — với ảnh dạng `
      + `\`blob:\` (MangaPlus và tương tự), ảnh mới sẽ có địa chỉ khác nên có thể phải chờ lại `
      + `từ đầu, không dùng lại được bản dịch vừa xong.\n\n${so_do}`,
      20,
    )
    return
  }

  xong(`Xong: ${co_chu}/${tra.vung.length} bong bóng có bản dịch.\n\n${so_do}`, 40)
})()
