import { Search, X, ChevronDown, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import type { FilterState, FileType, OrganSystem, PatientType, SourceType, SurgicalSystem } from '../types'
import {
  ORGAN_LABELS,
  SURGICAL_SYSTEM_LABELS,
  FILE_TYPE_COLORS,
  DEFAULT_FILTERS,
} from '../types'

interface SearchPanelProps {
  filters: FilterState
  onChange: (f: FilterState) => void
  resultCount: number
}

type FilterSection = 'patient' | 'organ' | 'robot' | 'format' | 'source'

const PATIENT_OPTIONS: { value: PatientType; label: string; sub?: string }[] = [
  { value: 'adult',     label: 'Adult',     sub: '>18 yr' },
  { value: 'pediatric', label: 'Pediatric', sub: '1–18 yr' },
  { value: 'neonatal',  label: 'Neonatal',  sub: '0–28 d' },
  { value: 'phantom',   label: 'Phantom' },
  { value: 'generic',   label: 'Generic' },
]

const ORGAN_OPTIONS: OrganSystem[] = [
  'cardiac', 'hepatobiliary', 'urologic', 'gynecologic', 'colorectal',
  'thoracic', 'neurologic', 'orthopedic', 'vascular', 'gastrointestinal', 'general',
]

const ROBOT_OPTIONS: SurgicalSystem[] = [
  'davinci-xi', 'davinci-x', 'davinci-sp', 'davinci-si',
  'versius', 'hugo', 'senhance', 'ottava', 'mira', 'raven-ii', 'lbr-med',
  'generic', 'manual',
]

const FORMAT_OPTIONS: FileType[] = ['USD', 'OBJ', 'STL', 'URDF', 'FBX', 'PLY', 'GLTF', 'SDF', 'DAE', 'MJCF']

const SOURCE_OPTIONS: { value: SourceType; label: string }[] = [
  { value: 'arxiv',   label: 'arXiv' },
  { value: 'github',  label: 'GitHub' },
  { value: 'dataset', label: 'Dataset Hub' },
  { value: 'manual',  label: 'Manual Entry' },
]

function SectionHeader({
  title,
  expanded,
  onToggle,
  activeCount,
}: {
  title: string
  expanded: boolean
  onToggle: () => void
  activeCount: number
}) {
  return (
    <button
      onClick={onToggle}
      className="w-full flex items-center justify-between py-2 text-left group"
    >
      <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition-colors">
        {title}
        {activeCount > 0 && (
          <span className="flex h-4 w-4 items-center justify-center rounded-full bg-blue-600 text-[10px] font-bold text-white">
            {activeCount}
          </span>
        )}
      </span>
      <ChevronDown
        size={13}
        className={['text-slate-400 dark:text-slate-500 transition-transform', expanded ? 'rotate-180' : ''].join(' ')}
      />
    </button>
  )
}

function ToggleChip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={[
        'rounded border px-2.5 py-1 text-[11px] font-medium transition-all text-left',
        active
          ? 'border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
          : 'border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400 dark:hover:border-blue-700 dark:hover:text-blue-300',
      ].join(' ')}
    >
      {children}
    </button>
  )
}

function toggle<T>(arr: T[], val: T): T[] {
  return arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]
}

export default function SearchPanel({ filters, onChange, resultCount }: SearchPanelProps) {
  const [expanded, setExpanded] = useState<Record<FilterSection, boolean>>({
    patient: true,
    organ:   true,
    robot:   true,
    format:  true,
    source:  true,
  })

  const toggle_section = (s: FilterSection) =>
    setExpanded(prev => ({ ...prev, [s]: !prev[s] }))

  const isDefault = JSON.stringify(filters) === JSON.stringify(DEFAULT_FILTERS)

  return (
    <aside className="w-60 shrink-0 flex flex-col gap-0">

      {/* Search box */}
      <div className="relative mb-4">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
        <input
          type="text"
          placeholder="Search assets, authors, tags..."
          value={filters.query}
          onChange={e => onChange({ ...filters, query: e.target.value })}
          className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 py-2 pl-8 pr-8 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20 transition-colors"
        />
        {filters.query && (
          <button
            onClick={() => onChange({ ...filters, query: '' })}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
          >
            <X size={13} />
          </button>
        )}
      </div>

      {/* Result count + reset */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-slate-500 dark:text-slate-400">
          <span className="text-slate-900 dark:text-white font-semibold">{resultCount}</span>{' '}
          result{resultCount !== 1 ? 's' : ''}
        </span>
        {!isDefault && (
          <button
            onClick={() => onChange({ ...DEFAULT_FILTERS })}
            className="flex items-center gap-1 text-[11px] text-slate-500 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
          >
            <RotateCcw size={11} />
            Reset
          </button>
        )}
      </div>

      <div className="flex flex-col divide-y divide-slate-100 dark:divide-slate-700/50">

        {/* Patient type */}
        <div className="py-3">
          <SectionHeader
            title="Patient"
            expanded={expanded.patient}
            onToggle={() => toggle_section('patient')}
            activeCount={filters.patientTypes.length}
          />
          {expanded.patient && (
            <div className="mt-2 flex flex-wrap gap-1.5 animate-fade-in">
              {PATIENT_OPTIONS.map(opt => (
                <ToggleChip
                  key={opt.value}
                  active={filters.patientTypes.includes(opt.value)}
                  onClick={() => onChange({ ...filters, patientTypes: toggle(filters.patientTypes, opt.value) })}
                >
                  <span>{opt.label}</span>
                  {opt.sub && <span className="ml-1 text-slate-400 dark:text-slate-500">{opt.sub}</span>}
                </ToggleChip>
              ))}
            </div>
          )}
        </div>

        {/* Organ system */}
        <div className="py-3">
          <SectionHeader
            title="Organ System"
            expanded={expanded.organ}
            onToggle={() => toggle_section('organ')}
            activeCount={filters.organSystems.length}
          />
          {expanded.organ && (
            <div className="mt-2 flex flex-wrap gap-1.5 animate-fade-in">
              {ORGAN_OPTIONS.map(opt => (
                <ToggleChip
                  key={opt}
                  active={filters.organSystems.includes(opt)}
                  onClick={() => onChange({ ...filters, organSystems: toggle(filters.organSystems, opt) })}
                >
                  {ORGAN_LABELS[opt]}
                </ToggleChip>
              ))}
            </div>
          )}
        </div>

        {/* Surgical robot */}
        <div className="py-3">
          <SectionHeader
            title="Surgical System"
            expanded={expanded.robot}
            onToggle={() => toggle_section('robot')}
            activeCount={filters.surgicalSystems.length}
          />
          {expanded.robot && (
            <div className="mt-2 flex flex-wrap gap-1.5 animate-fade-in">
              {ROBOT_OPTIONS.map(opt => (
                <ToggleChip
                  key={opt}
                  active={filters.surgicalSystems.includes(opt)}
                  onClick={() => onChange({ ...filters, surgicalSystems: toggle(filters.surgicalSystems, opt) })}
                >
                  {SURGICAL_SYSTEM_LABELS[opt]}
                </ToggleChip>
              ))}
            </div>
          )}
        </div>

        {/* File format */}
        <div className="py-3">
          <SectionHeader
            title="File Format"
            expanded={expanded.format}
            onToggle={() => toggle_section('format')}
            activeCount={filters.fileTypes.length}
          />
          {expanded.format && (
            <div className="mt-2 flex flex-wrap gap-1.5 animate-fade-in">
              {FORMAT_OPTIONS.map(opt => (
                <button
                  key={opt}
                  onClick={() => onChange({ ...filters, fileTypes: toggle(filters.fileTypes, opt) })}
                  className={[
                    'rounded border font-mono text-[11px] font-medium px-2 py-0.5 transition-all',
                    filters.fileTypes.includes(opt)
                      ? FILE_TYPE_COLORS[opt]
                      : 'border-slate-200 bg-white text-slate-500 hover:border-blue-200 hover:bg-blue-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 dark:hover:border-slate-600',
                  ].join(' ')}
                >
                  .{opt}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Source type */}
        <div className="py-3">
          <SectionHeader
            title="Source"
            expanded={expanded.source}
            onToggle={() => toggle_section('source')}
            activeCount={filters.sourcetypes.length}
          />
          {expanded.source && (
            <div className="mt-2 flex flex-wrap gap-1.5 animate-fade-in">
              {SOURCE_OPTIONS.map(opt => (
                <ToggleChip
                  key={opt.value}
                  active={filters.sourcetypes.includes(opt.value)}
                  onClick={() => onChange({ ...filters, sourcetypes: toggle(filters.sourcetypes, opt.value) })}
                >
                  {opt.label}
                </ToggleChip>
              ))}
            </div>
          )}
        </div>

      </div>
    </aside>
  )
}
