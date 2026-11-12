import { AlertTriangle, X } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'

const SIZES = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' }

/** Accessible dialog: Escape closes, focus moves inside, background scroll is locked. */
export function Modal({ open, onClose, title, description, size = 'md', children, footer }) {
  const titleId = useId()
  const panelRef = useRef(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  })

  useEffect(() => {
    if (!open) return undefined
    const previouslyFocused = document.activeElement
    const onKey = (event) => event.key === 'Escape' && onCloseRef.current()
    document.addEventListener('keydown', onKey)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusable = panelRef.current?.querySelector(
      'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])',
    )
    focusable?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      previouslyFocused?.focus?.()
    }
  }, [open])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-navy-950/40 backdrop-blur-[1px]" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`relative flex max-h-[92vh] w-full flex-col rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl ${SIZES[size]}`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-4">
          <div>
            <h2 id={titleId} className="text-base font-semibold text-slate-900">
              {title}
            </h2>
            {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            aria-label="Close dialog"
          >
            <X className="size-5" />
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-5">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-3">{footer}</div>
        )}
      </div>
    </div>
  )
}

/**
 * Confirmation for destructive or important actions. With `inputLabel`, it also
 * collects a short note (e.g. a cancellation reason) passed to onConfirm.
 */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  tone = 'danger',
  inputLabel,
  inputPlaceholder,
  onConfirm,
  onClose,
}) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const close = () => {
    setNote('')
    onClose()
  }
  const confirm = async () => {
    setBusy(true)
    try {
      await onConfirm(note.trim() || null)
      setNote('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title={title}
      size="sm"
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={close} disabled={busy}>
            Back
          </button>
          <button
            type="button"
            className={tone === 'danger' ? 'btn-danger' : 'btn-primary'}
            onClick={confirm}
            disabled={busy}
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </>
      }
    >
      <div className="flex gap-3">
        {tone === 'danger' && (
          <span className="h-fit rounded-full bg-red-50 p-2 text-red-600">
            <AlertTriangle className="size-5" aria-hidden="true" />
          </span>
        )}
        <div className="flex-1 space-y-3">
          <p className="text-sm text-slate-600">{message}</p>
          {inputLabel && (
            <label className="block">
              <span className="label">{inputLabel}</span>
              <textarea
                className="input min-h-20"
                value={note}
                placeholder={inputPlaceholder}
                maxLength={255}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
          )}
        </div>
      </div>
    </Modal>
  )
}
