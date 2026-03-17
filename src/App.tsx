import { useEffect, useState } from 'react'
import Header from './components/Header'
import DatabasePage from './pages/DatabasePage'
import SubmitPage from './pages/SubmitPage'
import type { Asset } from './types'

type View = 'database' | 'submit'

export default function App() {
  const [view, setView] = useState<View>('database')
  const [assets, setAssets] = useState<Asset[]>([])
  const [adminAuth, setAdminAuth] = useState<string | null>(null)
  const [editMode, setEditMode] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [visibleKeys, setVisibleKeys] = useState<string[]>([])

  useEffect(() => {
    fetch('/db-assets.json')
      .then(r => r.json())
      .then((data: Asset[]) => setAssets(data))
      .catch(console.error)
  }, [])

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
    setSelected(new Set())
  }

  const handleSelectAllVisible = () => {
    setSelected(prev => {
      const next = new Set(prev)
      visibleKeys.forEach(key => next.add(key))
      return next
    })
  }

  const handleClearSelection = () => setSelected(new Set())

  return (
    <div className="min-h-screen bg-[#070d1a] bg-grid">
      <Header
        activeView={view}
        onViewChange={setView}
        totalAssets={assets.length}
        adminAuth={adminAuth}
        onAdminAuth={setAdminAuth}
        editMode={editMode}
        onToggleEdit={() => setEditMode(v => !v)}
        selectedCount={selected.size}
        onSelectAllVisible={handleSelectAllVisible}
        onClearSelection={handleClearSelection}
        onDeleteSelected={handleDeleteSelected}
      />

      <main>
        {view === 'database' && (
          <DatabasePage
            assets={assets}
            adminAuth={adminAuth}
            editMode={editMode}
            selected={selected}
            setSelected={setSelected}
            onVisibleKeysChange={setVisibleKeys}
          />
        )}
        {view === 'submit'   && <SubmitPage />}
      </main>

      <footer className="mt-16 border-t border-white/[0.04] py-6 text-center">
        <p className="text-[11px] text-gray-700">
          SurgSim DB — Open Surgical Robotics Asset Database for RL Research
          {' · '}
          <a href="https://github.com" className="hover:text-gray-500 transition-colors">GitHub</a>
          {' · '}
          <a href="https://arxiv.org" className="hover:text-gray-500 transition-colors">arXiv</a>
        </p>
      </footer>
    </div>
  )
}
