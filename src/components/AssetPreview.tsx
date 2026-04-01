import type { Asset } from '../types'

interface AssetPreviewProps {
  asset: Asset
  className?: string
}

function escapeXml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function buildPlaceholder(asset: Asset) {
  const label = asset.fileTypes[0] ?? 'ASSET'
  const title = escapeXml(asset.name || 'Asset')
  const color = asset.thumbnailColor ?? '#2563eb'
  const svg = [
    '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360" role="img">',
    '<defs>',
    '<linearGradient id="g" x1="0" x2="1" y1="0" y2="1">',
    `<stop offset="0%" stop-color="${color}" stop-opacity="0.15"/>`,
    `<stop offset="100%" stop-color="${color}" stop-opacity="0.04"/>`,
    '</linearGradient>',
    '</defs>',
    '<rect width="640" height="360" fill="#f8fafc"/>',
    '<rect width="640" height="360" fill="url(#g)"/>',
    `<text x="32" y="72" fill="${color}" font-size="48" font-family="Arial, sans-serif" font-weight="700">${label}</text>`,
    `<text x="32" y="112" fill="#64748b" font-size="18" font-family="Arial, sans-serif">${title}</text>`,
    '</svg>',
  ].join('')
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

export default function AssetPreview({ asset, className }: AssetPreviewProps) {
  const fallback = buildPlaceholder(asset)
  const src = asset.previewUrl?.trim() || fallback
  const containerClass = [
    'relative overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50',
    className ?? 'h-36 w-full',
  ].join(' ')

  return (
    <div className={containerClass}>
      <img
        src={src}
        alt={asset.name}
        loading="lazy"
        className="h-full w-full object-cover"
        onError={(event) => {
          const target = event.currentTarget
          if (target.src !== fallback) target.src = fallback
        }}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/20 via-transparent to-transparent" />
      <div className="absolute bottom-2 left-2 rounded bg-white/80 dark:bg-slate-900/80 border border-slate-200/50 dark:border-slate-700/50 px-2 py-0.5 text-[10px] font-semibold text-slate-700 dark:text-slate-300">
        {asset.fileTypes[0] ?? 'ASSET'}
      </div>
    </div>
  )
}
