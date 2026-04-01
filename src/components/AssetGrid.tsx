import { PackageOpen } from 'lucide-react'
import type { Asset } from '../types'
import AssetCard from './AssetCard'

interface AssetGridProps {
  assets: Asset[]
  selectable?: boolean
  selectedIds?: Set<string>
  onToggleSelect?: (id: string) => void
}

export default function AssetGrid({ assets, selectable, selectedIds, onToggleSelect }: AssetGridProps) {
  if (assets.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4 text-center animate-fade-in">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
          <PackageOpen size={28} className="text-slate-400 dark:text-slate-500" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-600 dark:text-slate-400">No assets match your filters</p>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Try broadening your search or clearing some filters</p>
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      {assets.map(asset => (
        <AssetCard
          key={asset.id}
          asset={asset}
          selectable={selectable}
          selected={asset.sourceKey ? selectedIds?.has(asset.sourceKey) : false}
          onToggleSelect={onToggleSelect}
        />
      ))}
    </div>
  )
}
