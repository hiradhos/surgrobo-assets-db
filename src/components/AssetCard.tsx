import { Download, ExternalLink, Star, Github, BookOpen, Tag } from 'lucide-react'
import type { Asset } from '../types'
import { ORGAN_LABELS, SURGICAL_SYSTEM_LABELS } from '../types'
import FileTypeBadge from './FileTypeBadge'

interface AssetCardProps {
  asset: Asset
  selectable?: boolean
  selected?: boolean
  onToggleSelect?: (id: string) => void
}

const SOURCE_BADGE: Record<string, { label: string; className: string }> = {
  arxiv:            { label: 'arXiv',        className: 'bg-red-500/10 text-red-400 border-red-500/20' },
  github:           { label: 'GitHub',       className: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  'atlas-database': { label: 'Atlas DB',     className: 'bg-violet-500/10 text-violet-400 border-violet-500/20' },
  dataset:          { label: 'Dataset Hub',  className: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  manual:           { label: 'Manual Entry', className: 'bg-gray-500/10 text-gray-400 border-gray-500/20' },
}

const PATIENT_BADGE: Record<string, string> = {
  adult:     'text-sky-300',
  pediatric: 'text-amber-300',
  neonatal:  'text-pink-300',
  phantom:   'text-violet-300',
  generic:   'text-gray-400',
}

export default function AssetCard({ asset, selectable, selected, onToggleSelect }: AssetCardProps) {
  const src = SOURCE_BADGE[asset.sourceType] ?? SOURCE_BADGE['manual']

  return (
    <div className="glass glass-hover rounded-xl overflow-hidden flex flex-col group animate-fade-in relative">
      {selectable && (
        <label className="absolute right-3 top-3 z-10 flex items-center gap-2 text-[11px] text-gray-300 bg-black/40 border border-white/10 rounded px-2 py-1">
          <input
            type="checkbox"
            className="h-3 w-3 accent-cyan-400"
            checked={!!selected}
            onChange={() => asset.sourceKey && onToggleSelect?.(asset.sourceKey)}
          />
          Select
        </label>
      )}

      {/* Color stripe + avatar */}
      <div
        className="h-1 w-full"
        style={{ background: `linear-gradient(90deg, ${asset.thumbnailColor ?? '#06b6d4'}44, transparent)` }}
      />

      <div className="p-4 flex flex-col gap-3 flex-1">

        {/* Top row */}
        <div
          className="relative overflow-hidden rounded-lg border border-white/[0.06]"
          style={{
            background: `linear-gradient(135deg, ${asset.thumbnailColor ?? '#06b6d4'}33, transparent)`,
          }}
        >
          {asset.previewUrl ? (
            <img
              src={asset.previewUrl}
              alt={asset.name}
              className="h-36 w-full object-cover"
              loading="lazy"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="h-36 w-full flex items-center justify-center text-xs uppercase tracking-wider text-gray-400">
              {asset.fileTypes.slice(0, 2).join(' / ') || 'Preview'}
            </div>
          )}
        </div>
        <div className="flex items-start justify-between gap-2">
          <div
            className="h-9 w-9 shrink-0 rounded-lg flex items-center justify-center text-sm font-bold"
            style={{
              background: `${asset.thumbnailColor ?? '#06b6d4'}22`,
              color: asset.thumbnailColor ?? '#06b6d4',
              border: `1px solid ${asset.thumbnailColor ?? '#06b6d4'}33`,
            }}
          >
            {asset.fileTypes[0]?.[0] ?? '?'}
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <span className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border ${src.className}`}>
              {src.label}
            </span>
            {asset.githubStars !== undefined && (
              <span className="flex items-center gap-0.5 text-[10px] text-yellow-400">
                <Star size={10} fill="currentColor" />
                {asset.githubStars >= 1000
                  ? `${(asset.githubStars / 1000).toFixed(1)}k`
                  : asset.githubStars}
              </span>
            )}
          </div>
        </div>

        {/* Title */}
        <div>
          <h3 className="text-sm font-semibold text-white leading-snug line-clamp-2 group-hover:text-cyan-300 transition-colors">
            {asset.name}
          </h3>
          {asset.authors && asset.authors.length > 0 && (
            <p className="mt-0.5 text-[11px] text-gray-500 truncate">
              {asset.authors.slice(0, 3).join(', ')}
              {asset.authors.length > 3 && ` +${asset.authors.length - 3}`}
              {' · '}
              <span className="text-gray-600">{asset.year}</span>
            </p>
          )}
        </div>

        {/* Description */}
        <p className="text-[12px] text-gray-400 leading-relaxed line-clamp-3">
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
          <span className="text-gray-500">{ORGAN_LABELS[asset.organSystem]}</span>
          <span className="text-gray-600">{SURGICAL_SYSTEM_LABELS[asset.surgicalSystem]}</span>
        </div>

        {/* Tags */}
        {asset.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {asset.tags.slice(0, 4).map(tag => (
              <span
                key={tag}
                className="flex items-center gap-0.5 rounded bg-white/[0.03] border border-white/[0.05] px-1.5 py-0.5 text-[10px] text-gray-500"
              >
                <Tag size={8} className="text-gray-600" />
                {tag}
              </span>
            ))}
            {asset.tags.length > 4 && (
              <span className="text-[10px] text-gray-600">+{asset.tags.length - 4}</span>
            )}
          </div>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Footer actions */}
        <div className="flex items-center justify-between pt-2 border-t border-white/[0.05] mt-1">
          <div className="flex items-center gap-2">
            {asset.arxivId && (
              <a
                href={`https://arxiv.org/abs/${asset.arxivId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-[11px] text-gray-500 hover:text-red-400 transition-colors"
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
                className="flex items-center gap-1 text-[11px] text-gray-500 hover:text-emerald-400 transition-colors"
              >
                <Github size={12} />
                <span className="truncate max-w-[100px]">{asset.githubRepo.split('/')[1]}</span>
              </a>
            )}
          </div>

          <div className="flex items-center gap-1.5">
            {asset.license && (
              <span className="text-[10px] text-gray-600 border border-white/[0.05] rounded px-1.5 py-0.5">
                {asset.license}
              </span>
            )}
            {asset.downloadUrl && (
              <a
                href={asset.downloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 rounded-md bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-1 text-[11px] font-medium text-cyan-300 hover:bg-cyan-500/20 transition-all"
              >
                <Download size={11} />
                Get
              </a>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}
