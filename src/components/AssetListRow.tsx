import { Star, Github, BookOpen, Download, ExternalLink } from 'lucide-react'
import type { Asset } from '../types'
import { ORGAN_LABELS, SURGICAL_SYSTEM_LABELS } from '../types'
import FileTypeBadge from './FileTypeBadge'

interface AssetListRowProps {
  asset: Asset
}

const PATIENT_BADGE: Record<string, string> = {
  adult:     'text-sky-400',
  pediatric: 'text-amber-400',
  neonatal:  'text-pink-400',
  phantom:   'text-violet-400',
  generic:   'text-gray-500',
}

export default function AssetListRow({ asset }: AssetListRowProps) {
  return (
    <div className="group flex items-start gap-4 py-3.5 px-2 rounded-lg hover:bg-white/[0.02] transition-colors">

      {/* Color dot + avatar */}
      <div
        className="h-8 w-8 shrink-0 rounded-lg flex items-center justify-center text-xs font-bold mt-0.5"
        style={{
          background: `${asset.thumbnailColor ?? '#06b6d4'}22`,
          color: asset.thumbnailColor ?? '#06b6d4',
          border: `1px solid ${asset.thumbnailColor ?? '#06b6d4'}33`,
        }}
      >
        {asset.fileTypes[0]?.[0] ?? '?'}
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start gap-3 flex-wrap">
          <h3 className="text-sm font-medium text-white group-hover:text-cyan-300 transition-colors leading-snug">
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
          <span className="text-gray-500">{ORGAN_LABELS[asset.organSystem]}</span>
          <span className="text-gray-600">{SURGICAL_SYSTEM_LABELS[asset.surgicalSystem]}</span>
          {asset.authors && (
            <span className="text-gray-600">
              {asset.authors.slice(0, 2).join(', ')}
              {asset.authors.length > 2 ? ' et al.' : ''}
              {' · '}{asset.year}
            </span>
          )}
        </div>
      </div>

      {/* Right side actions */}
      <div className="flex items-center gap-3 shrink-0 mt-0.5">
        {asset.githubStars !== undefined && (
          <span className="flex items-center gap-0.5 text-[11px] text-yellow-400">
            <Star size={10} fill="currentColor" />
            {asset.githubStars >= 1000 ? `${(asset.githubStars / 1000).toFixed(1)}k` : asset.githubStars}
          </span>
        )}
        {asset.arxivId && (
          <a
            href={`https://arxiv.org/abs/${asset.arxivId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-600 hover:text-red-400 transition-colors"
            title={`arXiv:${asset.arxivId}`}
          >
            <BookOpen size={13} />
          </a>
        )}
        {asset.githubRepo && (
          <a
            href={`https://github.com/${asset.githubRepo}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-600 hover:text-emerald-400 transition-colors"
          >
            <Github size={13} />
          </a>
        )}
        {asset.downloadUrl && (
          <a
            href={asset.downloadUrl}
            className="flex items-center gap-1 rounded bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 text-[11px] text-cyan-400 hover:bg-cyan-500/20 transition-all"
          >
            <Download size={11} />
            Get
          </a>
        )}
      </div>

    </div>
  )
}
