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
  const [isDark, setIsDark] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('theme') === 'dark'
    }
    return false
  })

  useEffect(() => {
    const root = document.documentElement
    if (isDark) {
      root.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      root.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [isDark])

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
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
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
        isDark={isDark}
        onToggleDark={() => setIsDark(v => !v)}
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
        {view === 'submit' && <SubmitPage />}
      </main>

      <footer className="mt-16 border-t border-slate-200 dark:border-slate-700/50 py-6 text-center bg-white dark:bg-slate-900">
        <p className="text-xs text-slate-500 dark:text-slate-500">
          Netter-DB
          {' · '}
          <a href="https://github.com" className="hover:text-slate-700 dark:hover:text-slate-300 transition-colors">GitHub</a>
          {' · '}
          <a href="https://arxiv.org" className="hover:text-slate-700 dark:hover:text-slate-300 transition-colors">arXiv</a>
        </p>
      </footer>
    </div>
  )
}
