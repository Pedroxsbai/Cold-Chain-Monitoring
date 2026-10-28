import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { CloseIcon } from './icons'

interface ModalProps {
  title: string
  open: boolean
  onClose: () => void
  children: ReactNode
}

/** Native <dialog>: focus trap, Escape and backdrop handled by the browser. */
export function Modal({ title, open, onClose, children }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      className="modal"
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose()
      }}
      aria-labelledby="modal-title"
    >
      {open ? (
        <>
          <div className="modal-head">
            <h2 id="modal-title">{title}</h2>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Fermer">
              <CloseIcon width={18} height={18} />
            </button>
          </div>
          <div className="modal-body">{children}</div>
        </>
      ) : null}
    </dialog>
  )
}
