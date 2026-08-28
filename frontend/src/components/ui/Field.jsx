import { useId } from 'react'

/** Ô nhập có nhãn LIÊN KẾT thật (`htmlFor`/`id`), mô tả và lỗi.
 *
 * Nhãn không liên kết thì bấm vào nhãn không focus được ô, và trình đọc màn hình đọc ra một ô
 * trống không tên — đó là lỗi tiếp cận cơ bản nhất và cũng hay gặp nhất.
 */
export function Field({ nhan, moTa, loi, batBuoc, children }) {
  const id = useId()
  const idMoTa = moTa || loi ? `${id}-mo-ta` : undefined
  return (
    <div className="o-nhap">
      <label className="nhan-o" htmlFor={id}>
        {nhan}
        {batBuoc && <span className="bat-buoc" aria-hidden="true"> *</span>}
      </label>
      {children({ id, 'aria-describedby': idMoTa, 'aria-invalid': loi ? true : undefined })}
      {(moTa || loi) && (
        <p className={`mo-ta-o${loi ? ' co-loi' : ''}`} id={idMoTa}>{loi || moTa}</p>
      )}
    </div>
  )
}

export function Input({ nhan, moTa, loi, batBuoc, ...rest }) {
  return (
    <Field nhan={nhan} moTa={moTa} loi={loi} batBuoc={batBuoc}>
      {(a) => <input className="o" {...a} {...rest} />}
    </Field>
  )
}

export function Select({ nhan, moTa, loi, batBuoc, children, ...rest }) {
  return (
    <Field nhan={nhan} moTa={moTa} loi={loi} batBuoc={batBuoc}>
      {(a) => <select className="o" {...a} {...rest}>{children}</select>}
    </Field>
  )
}
