import { useEffect, useState } from 'react'
import Header from './components/Header'
import DatabasePage from './pages/DatabasePage'
import SubmitPage from './pages/SubmitPage'

type View = 'database' | 'submit'

export default function App() {
  const [view, setView] = useState<View>('database')
  const [totalAssets, setTotalAssets] = useState(0)

  useEffect(() => {
    fetch('/db-assets.json')
      .then(r => r.json())
      .then((data: unknown[]) => setTotalAssets(data.length))
      .catch(console.error)
  }, [])

  return (
    <div className="min-h-screen bg-[#070d1a] bg-grid">
      <Header
        activeView={view}
        onViewChange={setView}
        totalAssets={totalAssets}
      />

      <main>
        {view === 'database' && <DatabasePage />}
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
