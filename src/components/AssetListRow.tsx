import { useState } from 'react'
import { Github, BookOpen, Download } from 'lucide-react'
import type { Asset } from '../types'
import { ORGAN_LABELS, SURGICAL_SYSTEM_LABELS } from '../types'
import FileTypeBadge from './FileTypeBadge'
import CitationModal from './CitationModal'

interface AssetListRowProps {
  asset: Asset
  selectable?: boolean
  selected?: boolean
  onToggleSelect?: (id: string) => void
}

const PATIENT_BADGE: Record<string, string> = {
  adult:     'text-sky-700 dark:text-sky-300',
  pediatric: 'text-amber-700 dark:text-amber-300',
  neonatal:  'text-pink-700 dark:text-pink-300',
  phantom:   'text-violet-700 dark:text-violet-300',
  generic:   'text-slate-500 dark:text-slate-400',
}

export default function AssetListRow({ asset, selectable, selected, onToggleSelect }: AssetListRowProps) {
  const [showCitation, setShowCitation] = useState(false)

  return (
    <div className="group flex items-start gap-4 py-3 px-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">

      {/* Checkbox */}
      {selectable && (
        <div className="flex items-center pt-0.5">
          <input
            type="checkbox"
            className="h-3.5 w-3.5 accent-blue-600"
            checked={!!selected}
            onChange={() => asset.sourceKey && onToggleSelect?.(asset.sourceKey)}
          />
        </div>
      )}

      {/* Thumbnail or avatar */}
      {asset.previewUrl ? (
        <div className="h-12 w-12 shrink-0 overflow-hidden rounded-md border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800">
          <img
            src={asset.previewUrl.replace(/\/medshapenet_previews\/(.+)\.svg$/, '/medshapenet_previews/$1.png')}
            alt={asset.name}
            className="h-full w-full object-cover"
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        </div>
      ) : (
        <div
          className="h-9 w-9 shrink-0 rounded-md flex items-center justify-center text-xs font-bold mt-0.5 border"
          style={{
            background: `${asset.thumbnailColor ?? '#2563eb'}18`,
            color: asset.thumbnailColor ?? '#2563eb',
            borderColor: `${asset.thumbnailColor ?? '#2563eb'}40`,
          }}
        >
          {asset.fileTypes[0]?.[0] ?? '?'}
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start gap-3 flex-wrap">
          <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors leading-snug">
            {asset.name}
          </h3>
          <div className="flex flex-wrap gap-1">
            {asset.fileTypes.map(ft => (
              <FileTypeBadge key={ft} type={ft} size="sm" />
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 mt-1 text-[11px]">
          <span className={PATIENT_BADGE[asset.patientType]}>
            {asset.patientType.charAt(0).toUpperCase() + asset.patientType.slice(1)}
          </span>
          <span className="text-slate-500 dark:text-slate-400">{ORGAN_LABELS[asset.organSystem]}</span>
          <span className="text-slate-400 dark:text-slate-500">{SURGICAL_SYSTEM_LABELS[asset.surgicalSystem]}</span>
          {asset.authors && (
            <span className="text-slate-400 dark:text-slate-500">
              {asset.authors.slice(0, 2).join(', ')}
              {asset.authors.length > 2 ? ' et al.' : ''}
              {' · '}{asset.year}
            </span>
          )}
        </div>
      </div>

      {/* Right side actions */}
      <div className="flex items-center gap-3 shrink-0 mt-0.5">
        {asset.arxivId && (
          <a
            href={`https://arxiv.org/abs/${asset.arxivId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
            title={`arXiv:${asset.arxivId}`}
          >
            <BookOpen size={14} />
          </a>
        )}
        {asset.githubRepo && (
          <a
            href={`https://github.com/${asset.githubRepo}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors"
          >
            <Github size={14} />
          </a>
        )}
        {asset.downloadUrl && (
          <button
            onClick={() => asset.citation ? setShowCitation(true) : window.open(asset.downloadUrl, '_blank')}
            className="flex items-center gap-1 rounded bg-blue-600 hover:bg-blue-700 px-2.5 py-1 text-[11px] font-medium text-white transition-colors"
          >
            <Download size={11} />
            Get
          </button>
        )}
        {showCitation && asset.citation && (
          <CitationModal
            assetName={asset.name}
            citation={asset.citation}
            downloadUrl={asset.downloadUrl}
            onClose={() => setShowCitation(false)}
          />
        )}
      </div>

    </div>
  )
}
