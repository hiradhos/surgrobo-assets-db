import { useEffect, useMemo, useState } from 'react'
import { LayoutGrid, List, Shield, Trash2, X } from 'lucide-react'
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
    if (asset.year < f.yearRange[0] || asset.year > f.yearRange[1])                 return false
    return true
  })
}

export default function DatabasePage() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [adminOpen, setAdminOpen] = useState(false)
  const [adminUser, setAdminUser] = useState('')
  const [adminPass, setAdminPass] = useState('')
  const [adminAuth, setAdminAuth] = useState<string | null>(null)
  const [editMode, setEditMode] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetch('/db-assets.json')
      .then(r => r.json())
      .then(setAssets)
      .catch(console.error)
  }, [])

  const filtered = useMemo(() => applyFilters(assets, filters), [assets, filters])

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectAllVisible = () => {
    setSelected(prev => {
      const next = new Set(prev)
      filtered.forEach(a => {
        if (a.sourceKey) next.add(a.sourceKey)
      })
      return next
    })
  }

  const clearSelection = () => setSelected(new Set())

  const handleAdminLogin = () => {
    if (adminUser === 'admin' && adminPass === 'choggedFunction69') {
      const token = btoa(`${adminUser}:${adminPass}`)
      setAdminAuth(token)
      setAdminOpen(false)
    }
  }

  const handleDeleteSelected = async () => {
    if (!adminAuth || selected.size === 0) return
    const resp = await fetch('http://localhost:8123/delete', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Basic ${adminAuth}`,
      },
      body: JSON.stringify({ sourceKeys: Array.from(selected) }),
    })
    if (!resp.ok) return
    const toDelete = new Set(selected)
    setAssets(prev => prev.filter(a => !a.sourceKey || !toDelete.has(a.sourceKey)))
    clearSelection()
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
              {adminAuth ? (
                <button
                  onClick={() => setEditMode(v => !v)}
                  className={[
                    'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all border',
                    editMode
                      ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                      : 'text-gray-400 hover:text-gray-200 border-white/[0.06]',
                  ].join(' ')}
                >
                  <Shield size={14} />
                  {editMode ? 'Exit Edit' : 'Edit Mode'}
                </button>
              ) : (
                <button
                  onClick={() => setAdminOpen(true)}
                  className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium border border-white/[0.06] text-gray-400 hover:text-gray-200 transition-all"
                >
                  <Shield size={14} />
                  Admin Login
                </button>
              )}
              {editMode && (
                <>
                  <button
                    onClick={selectAllVisible}
                    className="rounded-md px-3 py-1.5 text-xs font-medium border border-white/[0.06] text-gray-400 hover:text-gray-200 transition-all"
                  >
                    Select All
                  </button>
                  <button
                    onClick={clearSelection}
                    className="rounded-md px-3 py-1.5 text-xs font-medium border border-white/[0.06] text-gray-400 hover:text-gray-200 transition-all"
                  >
                    Clear
                  </button>
                  <button
                    onClick={handleDeleteSelected}
                    className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium border border-red-500/30 text-red-300 hover:bg-red-500/10 transition-all"
                  >
                    <Trash2 size={14} />
                    Delete ({selected.size})
                  </button>
                </>
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

      {adminOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center px-4">
          <div className="w-full max-w-sm rounded-xl border border-white/[0.08] bg-[#0b1324] p-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">Admin Login</h3>
              <button onClick={() => setAdminOpen(false)} className="text-gray-500 hover:text-gray-300">
                <X size={16} />
              </button>
            </div>
            <div className="mt-4 space-y-3">
              <input
                value={adminUser}
                onChange={e => setAdminUser(e.target.value)}
                placeholder="Username"
                className="w-full rounded-md bg-black/30 border border-white/[0.08] px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-cyan-400/40"
              />
              <input
                type="password"
                value={adminPass}
                onChange={e => setAdminPass(e.target.value)}
                placeholder="Password"
                className="w-full rounded-md bg-black/30 border border-white/[0.08] px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-cyan-400/40"
              />
              <button
                onClick={handleAdminLogin}
                className="w-full rounded-md bg-cyan-500/20 border border-cyan-500/30 px-3 py-2 text-sm font-medium text-cyan-200 hover:bg-cyan-500/30 transition-all"
              >
                Login
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
