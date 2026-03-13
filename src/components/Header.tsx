import { Database, Plus, Github } from 'lucide-react'

type View = 'database' | 'submit'

interface HeaderProps {
  activeView: View
  onViewChange: (v: View) => void
  totalAssets: number
}

export default function Header({ activeView, onViewChange, totalAssets }: HeaderProps) {
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
