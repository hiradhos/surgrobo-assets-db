import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react'
import { LayoutGrid, List, ChevronLeft, ChevronRight } from 'lucide-react'
import type { Asset, FilterState } from '../types'
import { DEFAULT_FILTERS } from '../types'
import SearchPanel from '../components/SearchPanel'
import AssetGrid from '../components/AssetGrid'
import StatsBanner, { matchesCategory } from '../components/StatsBanner'
import type { CategoryFilter } from '../components/StatsBanner'
import AssetListRow from '../components/AssetListRow'

type ViewMode = 'grid' | 'list'

function applyFilters(assets: Asset[], f: FilterState) {
  return assets.filter(asset => {
    if (f.query) {
      const q = f.query.toLowerCase()
      const haystack = [
        asset.name ?? '',
        asset.description ?? '',
        asset.arxivTitle ?? '',
        asset.githubRepo ?? '',
        ...(asset.authors ?? []),
        ...(asset.tags ?? []),
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
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all')
  const [page, setPage] = useState(0)

  const PAGE_SIZE = 25

  const filtered = useMemo(() => {
    const base = applyFilters(assets, filters)
    return categoryFilter === 'all' ? base : base.filter(a => matchesCategory(a, categoryFilter))
  }, [assets, filters, categoryFilter])

  // Reset to first page whenever the filtered set changes
  useEffect(() => { setPage(0) }, [filtered])

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const paginated  = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

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
      <StatsBanner
        assets={assets}
        activeCategory={categoryFilter}
        onCategoryClick={setCategoryFilter}
      />

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
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              {filtered.length === assets.length
                ? `All ${assets.length.toLocaleString()} assets`
                : `${filtered.length.toLocaleString()} of ${assets.length.toLocaleString()} assets`}
            </h2>

            <div className="flex items-center gap-2">
              {adminAuth && (
                <span className="text-[11px] text-slate-400 dark:text-slate-500">Admin logged in</span>
              )}
              <div className="flex items-center gap-0.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-0.5 shadow-sm">
                <button
                  onClick={() => setViewMode('grid')}
                  className={[
                    'rounded-md p-1.5 transition-all',
                    viewMode === 'grid'
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300',
                  ].join(' ')}
                  title="Grid view"
                >
                  <LayoutGrid size={14} />
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className={[
                    'rounded-md p-1.5 transition-all',
                    viewMode === 'list'
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300',
                  ].join(' ')}
                  title="List view"
                >
                  <List size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* Results */}
          {viewMode === 'grid' ? (
            <AssetGrid
              assets={paginated}
              selectable={editMode}
              selectedIds={selected}
              onToggleSelect={toggleSelect}
            />
          ) : (
            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-sm divide-y divide-slate-100 dark:divide-slate-700/50">
              {paginated.length === 0 ? (
                <AssetGrid assets={[]} />
              ) : (
                paginated.map(asset => (
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

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-slate-200 dark:border-slate-700">
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Page {page + 1} of {totalPages} &mdash; showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} of {filtered.length.toLocaleString()}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="flex items-center gap-1 rounded px-2.5 py-1.5 text-xs font-medium border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft size={13} /> Prev
                </button>
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  const idx = totalPages <= 7 ? i : page < 4 ? i : page > totalPages - 5 ? totalPages - 7 + i : page - 3 + i
                  return (
                    <button
                      key={idx}
                      onClick={() => setPage(idx)}
                      className={[
                        'w-8 h-8 rounded text-xs font-medium border transition-colors',
                        idx === page
                          ? 'bg-blue-600 text-white border-blue-600'
                          : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700',
                      ].join(' ')}
                    >
                      {idx + 1}
                    </button>
                  )
                })}
                <button
                  onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                  disabled={page === totalPages - 1}
                  className="flex items-center gap-1 rounded px-2.5 py-1.5 text-xs font-medium border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Next <ChevronRight size={13} />
                </button>
              </div>
            </div>
          )}

        </div>
      </div>

    </div>
  )
}
