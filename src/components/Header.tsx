import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Database, Plus, Github, Shield, Trash2, X, Moon, Sun } from 'lucide-react'

type View = 'database' | 'submit'

interface HeaderProps {
  activeView: View
  onViewChange: (v: View) => void
  totalAssets: number
  adminAuth: string | null
  onAdminAuth: (token: string | null) => void
  editMode: boolean
  onToggleEdit: () => void
  selectedCount: number
  onSelectAllVisible: () => void
  onClearSelection: () => void
  onDeleteSelected: () => void
  isDark: boolean
  onToggleDark: () => void
}

export default function Header({
  activeView,
  onViewChange,
  totalAssets,
  adminAuth,
  onAdminAuth,
  editMode,
  onToggleEdit,
  selectedCount,
  onSelectAllVisible,
  onClearSelection,
  onDeleteSelected,
  isDark,
  onToggleDark,
}: HeaderProps) {
  const navItems: { id: View; label: string; icon: React.ReactNode }[] = [
    { id: 'database', label: 'Browse', icon: <Database size={14} /> },
    { id: 'submit',   label: 'Submit', icon: <Plus size={14} /> },
  ]

  return (
    <header className="sticky top-0 z-50 bg-[#1e3a5f] dark:bg-slate-900 border-b border-[#16304f] dark:border-slate-700/50 shadow-md">
      <div className="mx-auto max-w-screen-2xl px-6">
        <div className="relative flex h-14 items-center justify-between gap-6">

          {/* Logo */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-white/10 border border-white/20">
              <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-white" strokeWidth={2} strokeLinecap="round">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" />
                <path d="M12 8v4l3 3" />
                <path d="M7 12h1m8 0h1M12 7v1m0 8v1" />
              </svg>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold tracking-tight text-white">Netter-DB</span>
            </div>
          </div>

          {/* Nav — absolutely centered so flanking content width doesn't affect position */}
          <nav className="absolute left-1/2 -translate-x-1/2 flex items-center gap-1">
            {navItems.map(item => (
              <button
                key={item.id}
                onClick={() => onViewChange(item.id)}
                className={[
                  'flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded transition-all',
                  activeView === item.id
                    ? 'bg-white/15 text-white border-b-2 border-blue-300'
                    : 'text-white/70 hover:text-white hover:bg-white/10',
                ].join(' ')}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </nav>

          {/* Right actions */}
          <div className="flex items-center gap-3 shrink-0">
            {activeView === 'database' && (
              <div className="flex items-center gap-2">
                {adminAuth ? (
                  <button
                    onClick={onToggleEdit}
                    className={[
                      'flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-all border',
                      editMode
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                        : 'text-white/60 hover:text-white border-white/20 hover:border-white/40',
                    ].join(' ')}
                  >
                    <Shield size={13} />
                    {editMode ? 'Exit Edit' : 'Edit Mode'}
                  </button>
                ) : (
                  <AdminLoginButton onAuth={onAdminAuth} />
                )}
                {editMode && (
                  <>
                    <button
                      onClick={onSelectAllVisible}
                      className="rounded px-3 py-1.5 text-xs font-medium border border-white/20 text-white/60 hover:text-white transition-all"
                    >
                      Select All
                    </button>
                    <button
                      onClick={onClearSelection}
                      className="rounded px-3 py-1.5 text-xs font-medium border border-white/20 text-white/60 hover:text-white transition-all"
                    >
                      Clear
                    </button>
                    <button
                      onClick={onDeleteSelected}
                      disabled={selectedCount === 0}
                      className={[
                        'flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium border transition-all',
                        selectedCount === 0
                          ? 'cursor-not-allowed border-red-500/20 text-red-300/40'
                          : 'border-red-400/40 text-red-300 hover:bg-red-500/20',
                      ].join(' ')}
                    >
                      <Trash2 size={13} />
                      Delete ({selectedCount})
                    </button>
                  </>
                )}
              </div>
            )}

            {/* Asset count */}
            <div className="hidden sm:flex items-center gap-1.5 rounded-full bg-white/10 border border-white/15 px-3 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[11px] font-medium text-white/70">
                {totalAssets.toLocaleString()} assets
              </span>
            </div>

            {/* GitHub */}
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs text-white/60 hover:text-white transition-colors"
            >
              <Github size={15} />
              <span className="hidden sm:inline">GitHub</span>
            </a>

            {/* Dark mode toggle */}
            <button
              onClick={onToggleDark}
              className="flex items-center justify-center h-7 w-7 rounded text-white/60 hover:text-white hover:bg-white/10 transition-colors"
              title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDark ? <Sun size={15} /> : <Moon size={15} />}
            </button>
          </div>

        </div>
      </div>
    </header>
  )
}

function AdminLoginButton({ onAuth }: { onAuth: (token: string) => void }) {
  const [adminOpen, setAdminOpen] = useState(false)
  const [adminUser, setAdminUser] = useState('')
  const [adminPass, setAdminPass] = useState('')

  const handleAdminLogin = () => {
    if (adminUser === 'admin' && adminPass === 'choggedFunction69') {
      const token = btoa(`${adminUser}:${adminPass}`)
      onAuth(token)
      setAdminOpen(false)
      setAdminUser('')
      setAdminPass('')
    }
  }

  return (
    <>
      <button
        onClick={() => setAdminOpen(true)}
        className="flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium border border-white/20 text-white/60 hover:text-white transition-all"
      >
        <Shield size={13} />
        Admin
      </button>
      {adminOpen && typeof document !== 'undefined'
        ? createPortal(
          <div className="fixed inset-0 z-[100] bg-black/50 backdrop-blur-sm flex items-center justify-center px-4">
            <div className="w-full max-w-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Admin Login</h3>
                <button onClick={() => setAdminOpen(false)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                  <X size={16} />
                </button>
              </div>
              <div className="space-y-3">
                <input
                  value={adminUser}
                  onChange={e => setAdminUser(e.target.value)}
                  placeholder="Username"
                  className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-400"
                />
                <input
                  type="password"
                  value={adminPass}
                  onChange={e => setAdminPass(e.target.value)}
                  placeholder="Password"
                  className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-400"
                />
                <button
                  onClick={handleAdminLogin}
                  className="w-full rounded-lg bg-blue-600 hover:bg-blue-700 px-3 py-2 text-sm font-medium text-white transition-colors"
                >
                  Login
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )
        : null}
    </>
  )
}
