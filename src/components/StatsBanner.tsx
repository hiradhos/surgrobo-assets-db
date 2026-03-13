import type { Asset } from '../types'
import { Database, FileCode2, GitFork, BookOpen } from 'lucide-react'

interface StatsBannerProps {
  assets: Asset[]
}

export default function StatsBanner({ assets }: StatsBannerProps) {
  const arxivCount  = assets.filter(a => a.sourceType === 'arxiv').length
  const githubCount = assets.filter(a => a.githubRepo).length
  const fileTypeSet = new Set(assets.flatMap(a => a.fileTypes))
  const robotCount  = new Set(assets.map(a => a.surgicalSystem).filter(s => s !== 'generic' && s !== 'manual')).size

  const stats = [
    { icon: <Database size={16} className="text-cyan-400" />,   label: 'Total Assets',   value: assets.length },
    { icon: <BookOpen size={16} className="text-violet-400" />, label: 'arXiv Papers',   value: arxivCount },
    { icon: <GitFork size={16} className="text-emerald-400" />, label: 'GitHub Repos',   value: githubCount },
    { icon: <FileCode2 size={16} className="text-amber-400" />, label: 'File Formats',   value: fileTypeSet.size },
    { icon: <span className="text-pink-400 text-base leading-none">&#x2695;</span>,       label: 'Robot Systems', value: robotCount },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
      {stats.map(s => (
        <div
          key={s.label}
          className="glass rounded-xl p-4 flex items-center gap-3"
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.04]">
            {s.icon}
          </div>
          <div>
            <p className="text-xl font-bold text-white leading-none">{s.value}</p>
            <p className="text-[11px] text-gray-500 mt-0.5">{s.label}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
