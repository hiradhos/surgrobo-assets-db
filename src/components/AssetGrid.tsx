import { PackageOpen } from 'lucide-react'
import type { Asset } from '../types'
import AssetCard from './AssetCard'

interface AssetGridProps {
  assets: Asset[]
}

export default function AssetGrid({ assets }: AssetGridProps) {
  if (assets.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4 text-center animate-fade-in">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-white/[0.03] border border-white/[0.06]">
          <PackageOpen size={28} className="text-gray-600" />
        </div>
        <div>
          <p className="text-sm font-medium text-gray-400">No assets match your filters</p>
          <p className="text-xs text-gray-600 mt-1">Try broadening your search or clearing some filters</p>
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      {assets.map(asset => (
        <AssetCard key={asset.id} asset={asset} />
      ))}
    </div>
  )
}
