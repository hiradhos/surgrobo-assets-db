import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react'
import { LayoutGrid, List } from 'lucide-react'
import type { Asset, FilterState } from '../types'
import { DEFAULT_FILTERS } from '../types'
import SearchPanel from '../components/SearchPanel'
import AssetGrid from '../components/AssetGrid'
import StatsBanner from '../components/StatsBanner'
import AssetListRow from '../components/AssetListRow'

type ViewMode = 'grid' | 'list'

function applyFilters(assets: Asset[], f: FilterState) {
  return assets.filter(asset => {
    if (f.query) {
      const q = f.query.toLowerCase()
      const haystack = [
        asset.name,
        asset.description,
        asset.arxivTitle ?? '',
        asset.githubRepo ?? '',
        ...(asset.authors ?? []),
        ...asset.tags,
      ].join(' ').toLowerCase()
      if (!haystack.includes(q)) return false
    }
    if (f.patientTypes.length   && !f.patientTypes.includes(asset.patientType))     return false
    if (f.organSystems.length   && !f.organSystems.includes(asset.organSystem))     return false
    if (f.surgicalSystems.length && !f.surgicalSystems.includes(asset.surgicalSystem)) return false
    if (f.fileTypes.length      && !f.fileTypes.some(ft => asset.fileTypes.includes(ft))) return false
    if (f.rlFrameworks.length   && !f.rlFrameworks.some(fw => asset.rlFrameworks.includes(fw))) return false
    if (f.sourcetypes.length    && !f.sourcetypes.includes(asset.sourceType))       return false
    if (typeof asset.year === 'number' && (asset.year < f.yearRange[0] || asset.year > f.yearRange[1])) return false
    return true
  })
}

interface DatabasePageProps {
  assets: Asset[]
  adminAuth: string | null
  editMode: boolean
  selected: Set<string>
  setSelected: Dispatch<SetStateAction<Set<string>>>
  onVisibleKeysChange: (keys: string[]) => void
}

export default function DatabasePage({
  assets,
  adminAuth,
  editMode,
  selected,
  setSelected,
  onVisibleKeysChange,
}: DatabasePageProps) {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')

  const filtered = useMemo(() => applyFilters(assets, filters), [assets, filters])

  useEffect(() => {
    const keys = filtered.map(a => a.sourceKey).filter(Boolean) as string[]
    onVisibleKeysChange(keys)
  }, [filtered, onVisibleKeysChange])

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="mx-auto max-w-screen-2xl px-6 py-8">

      {/* Stats banner */}
      <StatsBanner assets={assets} />

      <div className="flex items-start gap-8">

        {/* Sidebar filters */}
        <SearchPanel
          filters={filters}
          onChange={setFilters}
          resultCount={filtered.length}
        />

        {/* Main content */}
        <div className="flex-1 min-w-0">

          {/* Toolbar */}
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-300">
              {filtered.length === assets.length
                ? `All ${assets.length} assets`
                : `${filtered.length} of ${assets.length} assets`}
            </h2>

            <div className="flex items-center gap-1 bg-white/[0.03] border border-white/[0.06] rounded-lg p-0.5">
              <button
                onClick={() => setViewMode('grid')}
                className={[
                  'rounded-md p-1.5 transition-all',
                  viewMode === 'grid' ? 'bg-white/[0.08] text-gray-200' : 'text-gray-600 hover:text-gray-400',
                ].join(' ')}
                title="Grid view"
              >
                <LayoutGrid size={14} />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={[
                  'rounded-md p-1.5 transition-all',
                  viewMode === 'list' ? 'bg-white/[0.08] text-gray-200' : 'text-gray-600 hover:text-gray-400',
                ].join(' ')}
                title="List view"
              >
                <List size={14} />
              </button>
            </div>

            <div className="flex items-center gap-2">
              {adminAuth && (
                <span className="text-[11px] text-gray-500">Admin logged in</span>
              )}
            </div>
          </div>

          {/* Results */}
          {viewMode === 'grid' ? (
            <AssetGrid
              assets={filtered}
              selectable={editMode}
              selectedIds={selected}
              onToggleSelect={toggleSelect}
            />
          ) : (
            <div className="flex flex-col divide-y divide-white/[0.04]">
              {filtered.length === 0 ? (
                <AssetGrid assets={[]} />
              ) : (
                filtered.map(asset => (
                  <AssetListRow
                    key={asset.id}
                    asset={asset}
                    selectable={editMode}
                    selected={asset.sourceKey ? selected.has(asset.sourceKey) : false}
                    onToggleSelect={toggleSelect}
                  />
                ))
              )}
            </div>
          )}

        </div>
      </div>

    </div>
  )
}
