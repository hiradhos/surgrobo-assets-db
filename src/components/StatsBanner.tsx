import type { Asset } from '../types'
import { Database, Cpu, Stethoscope, Activity, GitBranch, Video } from 'lucide-react'

export type CategoryFilter = 'all' | 'anatomical' | 'robots' | 'infrastructure' | 'kinematics' | 'footage'

interface StatsBannerProps {
  assets: Asset[]
  activeCategory: CategoryFilter
  onCategoryClick: (cat: CategoryFilter) => void
}

const ROBOT_KEYWORDS = ['robot', 'davinci', 'da vinci', 'laparoscop', 'endoscop', 'manipulator', 'surgical arm']
const INFRA_KEYWORDS = [
  'instrument', 'trocar', 'needle', 'forceps', 'catheter', 'suture', 'stapler',
  'retractor', 'clamp', 'scissors', 'scalpel', 'cannula', 'hospital bed',
  'iv line', 'infusion', 'drape', 'surgical table', 'phantom', 'clipper',
  'dissector', 'grasper', 'electrocautery', 'cautery', 'bipolar', 'electrode',
  'speculum', 'dilator', 'syringe', 'pill', 'tablet', 'capsule', 'vial',
  'medication', 'drug', 'implant', 'prosthesis', 'prosthetic', 'drill', 'burr',
  'chisel', 'osteotome', 'curette', 'impactor', 'reamer', 'screw', 'bone plate',
]
const KINEMATICS_FILE_TYPES = new Set(['URDF', 'SDF', 'MJCF'])
const FOOTAGE_FILE_TYPES = new Set(['MP4', 'AVI', 'MOV', 'MKV', 'WEBM', 'VIDEO'])
// Only unambiguous multi-word phrases — avoids false positives on product names
const FOOTAGE_PHRASES = [
  'surgical video', 'endoscopic video', 'laparoscopic video', 'robotic video',
  'video dataset', 'video collection', 'video footage', 'video recording',
  'surgical footage', 'video data', 'surgical recording',
]

function assetText(a: Asset): string {
  return [a.name ?? '', a.description ?? '', ...(a.tags ?? [])].join(' ').toLowerCase()
}

// Trust the category field set by the backend; no sourceType-based fallback
function isAnatomical(a: Asset): boolean {
  return a.category === 'anatomical-model'
}

function isSurgicalRobot(a: Asset): boolean {
  if (isAnatomical(a)) return false
  if (a.surgicalSystem !== 'generic' && a.surgicalSystem !== 'manual') return true
  return ROBOT_KEYWORDS.some(k => assetText(a).includes(k))
}

function isORInfrastructure(a: Asset): boolean {
  // Respect backend-assigned category first
  if (a.category === 'or-infrastructure') return true
  if (isAnatomical(a)) return false
  return INFRA_KEYWORDS.some(k => assetText(a).includes(k))
}

function isKinematics(a: Asset): boolean {
  return (a.fileTypes ?? []).some(ft => KINEMATICS_FILE_TYPES.has(ft))
}

function isSurgicalFootage(a: Asset): boolean {
  if ((a.fileTypes ?? []).some(ft => FOOTAGE_FILE_TYPES.has(ft.toUpperCase()))) return true
  const text = assetText(a)
  return FOOTAGE_PHRASES.some(phrase => text.includes(phrase))
}

export function matchesCategory(a: Asset, cat: CategoryFilter): boolean {
  switch (cat) {
    case 'all':            return true
    case 'anatomical':     return isAnatomical(a)
    case 'robots':         return isSurgicalRobot(a)
    case 'infrastructure': return isORInfrastructure(a)
    case 'kinematics':     return isKinematics(a)
    case 'footage':        return isSurgicalFootage(a)
  }
}

export default function StatsBanner({ assets, activeCategory, onCategoryClick }: StatsBannerProps) {
  const stats: { cat: CategoryFilter; icon: React.ReactNode; label: string; value: number; accent: string; activeRing: string }[] = [
    {
      cat: 'all',
      icon: <Database size={18} />,
      label: 'Total Assets',
      value: assets.length,
      accent:     'border-l-blue-600 dark:border-l-blue-500',
      activeRing: 'ring-2 ring-blue-500 dark:ring-blue-400',
    },
    {
      cat: 'anatomical',
      icon: <Activity size={18} />,
      label: 'Anatomical Models',
      value: assets.filter(isAnatomical).length,
      accent:     'border-l-emerald-600 dark:border-l-emerald-400',
      activeRing: 'ring-2 ring-emerald-500 dark:ring-emerald-400',
    },
    {
      cat: 'robots',
      icon: <Cpu size={18} />,
      label: 'Surgical Robots',
      value: assets.filter(isSurgicalRobot).length,
      accent:     'border-l-violet-600 dark:border-l-violet-400',
      activeRing: 'ring-2 ring-violet-500 dark:ring-violet-400',
    },
    {
      cat: 'infrastructure',
      icon: <Stethoscope size={18} />,
      label: 'OR Infrastructure',
      value: assets.filter(isORInfrastructure).length,
      accent:     'border-l-amber-600 dark:border-l-amber-400',
      activeRing: 'ring-2 ring-amber-500 dark:ring-amber-400',
    },
    {
      cat: 'kinematics',
      icon: <GitBranch size={18} />,
      label: 'Kinematics Files',
      value: assets.filter(isKinematics).length,
      accent:     'border-l-sky-600 dark:border-l-sky-400',
      activeRing: 'ring-2 ring-sky-500 dark:ring-sky-400',
    },
    {
      cat: 'footage',
      icon: <Video size={18} />,
      label: 'Surgical Footage',
      value: assets.filter(isSurgicalFootage).length,
      accent:     'border-l-rose-600 dark:border-l-rose-400',
      activeRing: 'ring-2 ring-rose-500 dark:ring-rose-400',
    },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
      {stats.map(s => {
        const isActive = activeCategory === s.cat
        return (
          <button
            key={s.cat}
            onClick={() => onCategoryClick(isActive && s.cat !== 'all' ? 'all' : s.cat)}
            className={[
              'text-left bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 shadow-sm border-l-4 p-4 flex items-center gap-3 animate-fade-in transition-all',
              s.accent,
              isActive
                ? `${s.activeRing} shadow-md`
                : 'hover:shadow-md hover:border-slate-300 dark:hover:border-slate-600',
            ].join(' ')}
          >
            <div className={[
              'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors',
              isActive ? 'bg-slate-100 dark:bg-slate-600' : 'bg-slate-50 dark:bg-slate-700/50',
            ].join(' ')}>
              <span className={isActive ? 'text-slate-700 dark:text-slate-200' : 'text-slate-400 dark:text-slate-400'}>
                {s.icon}
              </span>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900 dark:text-white leading-none">
                {s.value.toLocaleString()}
              </p>
              <p className={[
                'text-[11px] mt-0.5 font-medium',
                isActive ? 'text-slate-600 dark:text-slate-300' : 'text-slate-500 dark:text-slate-400',
              ].join(' ')}>
                {s.label}
              </p>
            </div>
          </button>
        )
      })}
    </div>
  )
}
