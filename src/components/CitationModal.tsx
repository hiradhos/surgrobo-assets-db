import { useEffect, useRef, useState } from 'react'
import { Copy, Check, X, Download } from 'lucide-react'

interface CitationModalProps {
  assetName: string
  citation: string
  downloadUrl?: string
  onClose: () => void
}

export default function CitationModal({ assetName, citation, downloadUrl, onClose }: CitationModalProps) {
  const [copied, setCopied] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  function handleCopy() {
    navigator.clipboard.writeText(citation).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onClose()
  }

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      onClick={handleOverlayClick}
    >
      <div className="w-full max-w-lg rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-xl flex flex-col gap-4 p-6 animate-fade-in">

        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Please cite this asset</h2>
            <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
              If you use <span className="font-medium text-slate-700 dark:text-slate-300">{assetName}</span> in your work, please include the citation below.
            </p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded-md p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X size={15} />
          </button>
        </div>

        {/* Citation box */}
        <div className="relative rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800">
          <textarea
            readOnly
            value={citation}
            rows={4}
            className="w-full resize-none bg-transparent px-3.5 py-3 pr-10 text-[12px] text-slate-700 dark:text-slate-300 font-mono leading-relaxed focus:outline-none"
          />
          <button
            onClick={handleCopy}
            title="Copy to clipboard"
            className="absolute right-2.5 top-2.5 rounded-md p-1.5 text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors"
          >
            {copied ? <Check size={14} className="text-emerald-600 dark:text-emerald-400" /> : <Copy size={14} />}
          </button>
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-end gap-2 pt-1">
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-200 dark:border-slate-700 px-4 py-1.5 text-[12px] text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:border-slate-300 transition-colors"
          >
            OK
          </button>
          {downloadUrl && (
            <a
              href={downloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={onClose}
              className="flex items-center gap-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 px-4 py-1.5 text-[12px] font-medium text-white transition-colors"
            >
              <Download size={12} />
              Continue to download
            </a>
          )}
        </div>

      </div>
    </div>
  )
}
