import { useState } from 'react'
import { Download, Github, BookOpen, Tag } from 'lucide-react'
import type { Asset } from '../types'
import { ORGAN_LABELS, SURGICAL_SYSTEM_LABELS } from '../types'
import FileTypeBadge from './FileTypeBadge'
import CitationModal from './CitationModal'

interface AssetCardProps {
  asset: Asset
  selectable?: boolean
  selected?: boolean
  onToggleSelect?: (id: string) => void
}

const SOURCE_BADGE: Record<string, { label: string; className: string }> = {
  arxiv:            { label: 'arXiv',        className: 'bg-red-100 text-red-700 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700/50' },
  github:           { label: 'GitHub',       className: 'bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-700/50' },
  'atlas-database': { label: 'Atlas DB',     className: 'bg-violet-100 text-violet-700 border-violet-300 dark:bg-violet-900/30 dark:text-violet-300 dark:border-violet-700/50' },
  dataset:          { label: 'Dataset Hub',  className: 'bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700/50' },
  manual:           { label: 'Manual Entry', className: 'bg-slate-100 text-slate-600 border-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:border-slate-600' },
}

const PATIENT_BADGE: Record<string, string> = {
  adult:     'text-sky-700 dark:text-sky-300',
  pediatric: 'text-amber-700 dark:text-amber-300',
  neonatal:  'text-pink-700 dark:text-pink-300',
  phantom:   'text-violet-700 dark:text-violet-300',
  generic:   'text-slate-500 dark:text-slate-400',
}

export default function AssetCard({ asset, selectable, selected, onToggleSelect }: AssetCardProps) {
  const src = SOURCE_BADGE[asset.sourceType] ?? SOURCE_BADGE['manual']
  const [showCitation, setShowCitation] = useState(false)

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-sm hover:shadow-md transition-shadow flex flex-col group animate-fade-in relative overflow-hidden">
      {selectable && (
        <label className="absolute right-3 top-3 z-10 flex items-center gap-2 text-[11px] text-slate-600 dark:text-slate-300 bg-white/90 dark:bg-slate-800/90 border border-slate-200 dark:border-slate-600 rounded px-2 py-1">
          <input
            type="checkbox"
            className="h-3 w-3 accent-blue-600"
            checked={!!selected}
            onChange={() => asset.sourceKey && onToggleSelect?.(asset.sourceKey)}
          />
          Select
        </label>
      )}

      {/* Top color accent bar */}
      <div
        className="h-1 w-full shrink-0"
        style={{ background: asset.thumbnailColor ?? '#2563eb' }}
      />

      <div className="p-4 flex flex-col gap-3 flex-1">

        {/* Preview image */}
        <div className="relative overflow-hidden rounded-md border border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40">
          {asset.previewUrl ? (
            <img
              src={asset.previewUrl.replace(/\/medshapenet_previews\/(.+)\.svg$/, '/medshapenet_previews/$1.png')}
              alt={asset.name}
              className="h-36 w-full object-cover"
              loading="lazy"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div
              className="h-36 w-full flex items-center justify-center"
              style={{ background: `linear-gradient(135deg, ${asset.thumbnailColor ?? '#2563eb'}18, ${asset.thumbnailColor ?? '#2563eb'}06)` }}
            >
              <span className="text-xs font-mono font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest">
                {asset.fileTypes.slice(0, 2).join(' / ') || 'Preview'}
              </span>
            </div>
          )}
        </div>

        {/* Source badge + stars row */}
        <div className="flex items-center justify-between gap-2">
          <div
            className="h-8 w-8 shrink-0 rounded-md flex items-center justify-center text-xs font-bold border"
            style={{
              background: `${asset.thumbnailColor ?? '#2563eb'}18`,
              color: asset.thumbnailColor ?? '#2563eb',
              borderColor: `${asset.thumbnailColor ?? '#2563eb'}40`,
            }}
          >
            {asset.fileTypes[0]?.[0] ?? '?'}
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <span className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border ${src.className}`}>
              {src.label}
            </span>
          </div>
        </div>

        {/* Title */}
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white leading-snug line-clamp-2 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
            {asset.name}
          </h3>
          {asset.authors && asset.authors.length > 0 && (
            <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400 truncate">
              {asset.authors.slice(0, 3).join(', ')}
              {asset.authors.length > 3 && ` +${asset.authors.length - 3}`}
              {' · '}
              <span className="text-slate-400 dark:text-slate-500">{asset.year}</span>
            </p>
          )}
        </div>

        {/* Description */}
        <p className="text-[12px] text-slate-600 dark:text-slate-400 leading-relaxed line-clamp-3">
          {asset.description}
        </p>

        {/* File type badges */}
        <div className="flex flex-wrap gap-1">
          {asset.fileTypes.map(ft => (
            <FileTypeBadge key={ft} type={ft} size="sm" />
          ))}
        </div>

        {/* Metadata row */}
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px]">
          <span className={`font-medium ${PATIENT_BADGE[asset.patientType]}`}>
            {asset.patientType.charAt(0).toUpperCase() + asset.patientType.slice(1)}
          </span>
          <span className="text-slate-500 dark:text-slate-400">{ORGAN_LABELS[asset.organSystem]}</span>
          <span className="text-slate-400 dark:text-slate-500">{SURGICAL_SYSTEM_LABELS[asset.surgicalSystem]}</span>
        </div>

        {/* Tags */}
        {asset.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {asset.tags.slice(0, 4).map(tag => (
              <span
                key={tag}
                className="flex items-center gap-0.5 rounded bg-slate-100 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 px-1.5 py-0.5 text-[10px] text-slate-500 dark:text-slate-400"
              >
                <Tag size={8} className="text-slate-400 dark:text-slate-500" />
                {tag}
              </span>
            ))}
            {asset.tags.length > 4 && (
              <span className="text-[10px] text-slate-400 dark:text-slate-500">+{asset.tags.length - 4}</span>
            )}
          </div>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Footer actions */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-700/50 mt-1">
          <div className="flex items-center gap-2">
            {asset.arxivId && (
              <a
                href={`https://arxiv.org/abs/${asset.arxivId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                title={asset.arxivTitle}
              >
                <BookOpen size={12} />
                <span>arXiv:{asset.arxivId}</span>
              </a>
            )}
            {asset.githubRepo && (
              <a
                href={`https://github.com/${asset.githubRepo}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors"
              >
                <Github size={12} />
                <span className="truncate max-w-[100px]">{asset.githubRepo.split('/')[1]}</span>
              </a>
            )}
          </div>

          <div className="flex items-center gap-1.5">
            {asset.license && (
              <span className="text-[10px] text-slate-400 dark:text-slate-500 border border-slate-200 dark:border-slate-600 rounded px-1.5 py-0.5">
                {asset.license}
              </span>
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

      </div>
    </div>
  )
}
