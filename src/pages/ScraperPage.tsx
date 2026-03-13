import { useState } from 'react'
import {
  Search, RefreshCw, ExternalLink, Github, Star,
  CheckCircle2, PlusCircle, ChevronDown, ChevronUp,
  FileCode2, Rss, AlertCircle,
} from 'lucide-react'
import type { ArxivPaper, GitHubRepo } from '../types'
import { FILE_TYPE_COLORS } from '../types'
import { MOCK_PAPERS } from '../data/mockPapers'
import FileTypeBadge from '../components/FileTypeBadge'

const SEARCH_PRESETS = [
  'surgical robot simulation reinforcement learning',
  'robotic surgery USD URDF simulation',
  'laparoscopic tissue deformation RL',
  'da Vinci robot Isaac Sim MuJoCo',
  'surgical skill assessment simulation',
]

function RepoCard({ repo, compact }: { repo: GitHubRepo; compact?: boolean }) {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Github size={13} className="text-gray-400 shrink-0" />
          <a
            href={repo.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 truncate transition-colors"
          >
            {repo.owner}/{repo.name}
          </a>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="flex items-center gap-0.5 text-[11px] text-yellow-400">
            <Star size={10} fill="currentColor" />
            {repo.stars >= 1000 ? `${(repo.stars / 1000).toFixed(1)}k` : repo.stars}
          </span>
          {repo.license && (
            <span className="text-[10px] text-gray-600 border border-white/[0.05] rounded px-1.5 py-0.5">
              {repo.license}
            </span>
          )}
        </div>
      </div>

      {!compact && repo.description && (
        <p className="text-[11px] text-gray-500 line-clamp-2">{repo.description}</p>
      )}

      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1">
          {repo.detectedFileTypes.map(ft => (
            <FileTypeBadge key={ft} type={ft} size="sm" />
          ))}
        </div>
        <span className="text-[10px] text-gray-600 shrink-0">
          Updated {new Date(repo.lastUpdated).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}
        </span>
      </div>
    </div>
  )
}

function PaperCard({ paper, onAdd }: { paper: ArxivPaper; onAdd: (p: ArxivPaper) => void }) {
  const [expanded, setExpanded] = useState(false)
  const [added, setAdded] = useState(paper.inDatabase)

  const handleAdd = () => {
    setAdded(true)
    onAdd(paper)
  }

  return (
    <div className={[
      'glass rounded-xl overflow-hidden flex flex-col transition-all animate-fade-in',
      added ? 'border-emerald-500/20' : '',
    ].join(' ')}>

      <div
        className="h-0.5 w-full"
        style={{
          background: added
            ? 'linear-gradient(90deg, #10b98144, transparent)'
            : 'linear-gradient(90deg, #ef444444, transparent)',
        }}
      />

      <div className="p-5 flex flex-col gap-3">

        {/* Header row */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="flex items-center gap-1 text-[10px] font-semibold text-red-400 bg-red-500/10 border border-red-500/20 rounded px-1.5 py-0.5">
                <Rss size={9} />
                arXiv
              </span>
              <span className="text-[10px] text-gray-600 font-mono">{paper.id}</span>
              <span className="text-[10px] text-gray-600">
                {new Date(paper.publishedAt).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
              </span>
            </div>
            <h3 className="text-sm font-semibold text-white leading-snug">
              {paper.title}
            </h3>
            <p className="text-[11px] text-gray-500 mt-1">
              {paper.authors.slice(0, 4).join(', ')}
              {paper.authors.length > 4 && ` · +${paper.authors.length - 4} more`}
            </p>
          </div>

          <div className="flex flex-col items-end gap-2 shrink-0">
            {added ? (
              <span className="flex items-center gap-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1.5 text-[11px] font-medium text-emerald-400">
                <CheckCircle2 size={12} />
                In DB
              </span>
            ) : (
              <button
                onClick={handleAdd}
                className="flex items-center gap-1.5 rounded-md bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-1.5 text-[11px] font-medium text-cyan-300 hover:bg-cyan-500/20 transition-all"
              >
                <PlusCircle size={12} />
                Add to DB
              </button>
            )}
            <a
              href={`https://arxiv.org/abs/${paper.id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-gray-600 hover:text-gray-400 flex items-center gap-1 transition-colors"
            >
              <ExternalLink size={11} />
              View paper
            </a>
          </div>
        </div>

        {/* Categories */}
        <div className="flex flex-wrap gap-1.5">
          {paper.categories.map(cat => (
            <span key={cat} className="text-[10px] font-mono text-gray-500 bg-white/[0.03] border border-white/[0.05] rounded px-1.5 py-0.5">
              {cat}
            </span>
          ))}
          {paper.detectedFileTypes.map(ft => (
            <FileTypeBadge key={ft} type={ft} size="sm" />
          ))}
        </div>

        {/* Abstract toggle */}
        <div>
          <button
            onClick={() => setExpanded(e => !e)}
            className="flex items-center gap-1 text-[11px] text-gray-500 hover:text-gray-300 transition-colors"
          >
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {expanded ? 'Hide abstract' : 'Show abstract'}
          </button>
          {expanded && (
            <p className="mt-2 text-[12px] text-gray-400 leading-relaxed animate-fade-in border-l-2 border-white/[0.06] pl-3">
              {paper.abstract}
            </p>
          )}
        </div>

        {/* GitHub repos */}
        {paper.githubRepos.length > 0 && (
          <div>
            <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Github size={11} />
              Detected GitHub Repos ({paper.githubRepos.length})
            </p>
            <div className="flex flex-col gap-2">
              {paper.githubRepos.map(repo => (
                <RepoCard key={repo.url} repo={repo} />
              ))}
            </div>
          </div>
        )}

        {paper.githubRepos.length === 0 && (
          <div className="flex items-center gap-2 text-[11px] text-gray-600 bg-white/[0.02] rounded-lg p-2.5">
            <AlertCircle size={12} className="text-yellow-600" />
            No GitHub repositories detected for this paper
          </div>
        )}

      </div>
    </div>
  )
}

export default function ScraperPage() {
  const [query, setQuery] = useState(SEARCH_PRESETS[0])
  const [isLoading, setIsLoading] = useState(false)
  const [papers, setPapers] = useState<ArxivPaper[]>(MOCK_PAPERS)
  const [lastFetched, setLastFetched] = useState<string>('just now')
  const [addedCount, setAddedCount] = useState(MOCK_PAPERS.filter(p => p.inDatabase).length)

  const handleScrape = () => {
    setIsLoading(true)
    setTimeout(() => {
      setIsLoading(false)
      setLastFetched('just now')
    }, 1800)
  }

  const handleAdd = (_paper: ArxivPaper) => {
    setAddedCount(c => c + 1)
  }

  return (
    <div className="mx-auto max-w-screen-2xl px-6 py-8">

      {/* Page header */}
      <div className="mb-8">
        <h2 className="text-xl font-bold text-white">arXiv Scraper</h2>
        <p className="text-sm text-gray-500 mt-1">
          Search recent arXiv preprints for surgical robotics assets. Detected GitHub repositories are
          scanned for .USD, .OBJ, .STL, .URDF, and other simulation file formats.
        </p>
      </div>

      {/* Search bar */}
      <div className="glass rounded-xl p-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleScrape()}
              placeholder="arXiv search query..."
              className="w-full rounded-lg border border-white/[0.07] bg-white/[0.03] py-2.5 pl-9 pr-4 text-sm text-gray-200 placeholder-gray-600 outline-none focus:border-cyan-500/40 transition-colors"
            />
          </div>
          <button
            onClick={handleScrape}
            disabled={isLoading}
            className="flex items-center gap-2 rounded-lg bg-cyan-500/10 border border-cyan-500/20 px-5 py-2.5 text-sm font-medium text-cyan-300 hover:bg-cyan-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            {isLoading ? 'Fetching...' : 'Fetch Latest'}
          </button>
        </div>

        {/* Preset queries */}
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="text-[11px] text-gray-600 self-center">Quick search:</span>
          {SEARCH_PRESETS.map(preset => (
            <button
              key={preset}
              onClick={() => setQuery(preset)}
              className={[
                'rounded-md border px-2.5 py-1 text-[11px] transition-all',
                query === preset
                  ? 'border-cyan-500/30 bg-cyan-500/10 text-cyan-400'
                  : 'border-white/[0.06] text-gray-500 hover:text-gray-400 hover:border-white/[0.10]',
              ].join(' ')}
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      {/* Stats bar */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span>
            <span className="text-white font-semibold">{papers.length}</span> papers found
          </span>
          <span>
            <span className="text-emerald-400 font-semibold">{addedCount}</span> added to database
          </span>
          <span>
            Last fetched: <span className="text-gray-400">{lastFetched}</span>
          </span>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-gray-500">
          <FileCode2 size={12} />
          Scanning for:
          {(['USD', 'STL', 'OBJ', 'URDF', 'MJCF', 'PLY'] as const).map(ft => (
            <span key={ft} className={`rounded border font-mono text-[10px] px-1.5 py-0.5 ${FILE_TYPE_COLORS[ft]}`}>
              .{ft}
            </span>
          ))}
        </div>
      </div>

      {/* Paper list */}
      <div className="flex flex-col gap-4">
        {papers.map(paper => (
          <PaperCard key={paper.id} paper={paper} onAdd={handleAdd} />
        ))}
      </div>

    </div>
  )
}
