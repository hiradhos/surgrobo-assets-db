import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Database, Plus, Github, Shield, Trash2, X } from 'lucide-react'

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
}: HeaderProps) {
  const navItems: { id: View; label: string; icon: React.ReactNode }[] = [
    { id: 'database', label: 'Database', icon: <Database size={15} /> },
    { id: 'submit',   label: 'Submit',   icon: <Plus size={15} /> },
  ]

  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-[#070d1a]/90 backdrop-blur-xl">
      <div className="mx-auto max-w-screen-2xl px-6">
        <div className="flex h-14 items-center justify-between gap-8">

          {/* Logo */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/10 border border-cyan-500/20">
              <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-cyan-400" strokeWidth={2} strokeLinecap="round">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" />
                <path d="M12 8v4l3 3" />
                <path d="M7 12h1m8 0h1M12 7v1m0 8v1" />
              </svg>
            </div>
            <div>
              <span className="text-sm font-semibold tracking-tight text-white">SurgSim</span>
              <span className="ml-0.5 text-sm font-semibold tracking-tight text-cyan-400">DB</span>
              <span className="ml-2 hidden text-[11px] font-medium text-gray-500 sm:inline">
                Surgical Robotics Asset Database
              </span>
            </div>
          </div>

          {/* Nav */}
          <nav className="flex items-center gap-1">
            {navItems.map(item => (
              <button
                key={item.id}
                onClick={() => onViewChange(item.id)}
                className={[
                  'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all',
                  activeView === item.id
                    ? 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/20'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-white/[0.04]',
                ].join(' ')}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </nav>

          {/* Right meta */}
          <div className="flex items-center gap-4 shrink-0">
            {activeView === 'database' && (
              <div className="flex items-center gap-2">
                {adminAuth ? (
                  <button
                    onClick={onToggleEdit}
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
                  <AdminLoginButton onAuth={onAdminAuth} />
                )}
                {editMode && (
                  <>
                    <button
                      onClick={onSelectAllVisible}
                      className="rounded-md px-3 py-1.5 text-xs font-medium border border-white/[0.06] text-gray-400 hover:text-gray-200 transition-all"
                    >
                      Select All
                    </button>
                    <button
                      onClick={onClearSelection}
                      className="rounded-md px-3 py-1.5 text-xs font-medium border border-white/[0.06] text-gray-400 hover:text-gray-200 transition-all"
                    >
                      Clear
                    </button>
                    <button
                      onClick={onDeleteSelected}
                      disabled={selectedCount === 0}
                      className={[
                        'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium border transition-all',
                        selectedCount === 0
                          ? 'cursor-not-allowed border-red-500/10 text-red-300/40'
                          : 'border-red-500/30 text-red-300 hover:bg-red-500/10',
                      ].join(' ')}
                    >
                      <Trash2 size={14} />
                      Delete ({selectedCount})
                    </button>
                  </>
                )}
              </div>
            )}
            <div className="hidden sm:flex items-center gap-1.5 rounded-full bg-white/[0.04] border border-white/[0.06] px-3 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[11px] font-medium text-gray-400">
                {totalAssets} assets indexed
              </span>
            </div>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              <Github size={14} />
              <span className="hidden sm:inline">GitHub</span>
            </a>
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
        className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium border border-white/[0.06] text-gray-400 hover:text-gray-200 transition-all"
      >
        <Shield size={14} />
        Admin Login
      </button>
      {adminOpen && typeof document !== 'undefined'
        ? createPortal(
          <div className="fixed inset-0 z-[100] bg-black/50 flex items-center justify-center px-4">
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
          </div>,
          document.body,
        )
        : null}
    </>
  )
}
