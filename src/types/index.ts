// ── File formats ───────────────────────────────────────────────────────────────
export type FileType = 'USD' | 'OBJ' | 'STL' | 'URDF' | 'FBX' | 'PLY' | 'GLTF' | 'SDF' | 'DAE' | 'MJCF'

// ── Patient / anatomy parameters ───────────────────────────────────────────────
export type PatientType = 'adult' | 'pediatric' | 'neonatal' | 'phantom' | 'generic'

export type OrganSystem =
  | 'cardiac'
  | 'hepatobiliary'
  | 'urologic'
  | 'gynecologic'
  | 'colorectal'
  | 'thoracic'
  | 'neurologic'
  | 'orthopedic'
  | 'vascular'
  | 'gastrointestinal'
  | 'general'

// ── Surgical platforms ─────────────────────────────────────────────────────────
export type SurgicalSystem =
  | 'davinci-xi'
  | 'davinci-x'
  | 'davinci-sp'
  | 'davinci-si'
  | 'versius'
  | 'hugo'
  | 'senhance'
  | 'ottava'
  | 'mira'
  | 'raven-ii'
  | 'lbr-med'
  | 'generic'
  | 'manual'

// ── RL / simulation frameworks ─────────────────────────────────────────────────
export type RLFramework =
  | 'isaac-sim'
  | 'mujoco'
  | 'gazebo'
  | 'pybullet'
  | 'orbit'
  | 'robosuite'
  | 'sapien'
  | 'webots'
  | 'other'

// ── Asset source ───────────────────────────────────────────────────────────────
export type SourceType = 'arxiv' | 'github' | 'dataset' | 'manual'

// ── Core asset record ──────────────────────────────────────────────────────────
export interface Asset {
  id: string
  name: string
  description: string
  fileTypes: FileType[]
  patientType: PatientType
  organSystem: OrganSystem
  surgicalSystem: SurgicalSystem
  rlFrameworks: RLFramework[]
  sourceType: SourceType
  arxivId?: string
  arxivTitle?: string
  githubRepo?: string
  githubStars?: number
  authors?: string[]
  year: number
  tags: string[]
  downloadUrl?: string
  license?: string
  addedAt: string
  thumbnailColor?: string  // used for placeholder avatar color
}

// ── arXiv scraper types ────────────────────────────────────────────────────────
export interface GitHubRepo {
  url: string
  owner: string
  name: string
  stars: number
  description: string
  detectedFileTypes: FileType[]
  lastUpdated: string
  license?: string
}

export interface ArxivPaper {
  id: string
  title: string
  authors: string[]
  abstract: string
  publishedAt: string
  updatedAt: string
  categories: string[]
  githubRepos: GitHubRepo[]
  detectedFileTypes: FileType[]
  inDatabase: boolean
}

// ── Search / filter state ──────────────────────────────────────────────────────
export interface FilterState {
  query: string
  patientTypes: PatientType[]
  organSystems: OrganSystem[]
  surgicalSystems: SurgicalSystem[]
  fileTypes: FileType[]
  rlFrameworks: RLFramework[]
  sourcetypes: SourceType[]
  yearRange: [number, number]
}

export const DEFAULT_FILTERS: FilterState = {
  query: '',
  patientTypes: [],
  organSystems: [],
  surgicalSystems: [],
  fileTypes: [],
  rlFrameworks: [],
  sourcetypes: [],
  yearRange: [2018, 2026],
}

// ── Display helpers ────────────────────────────────────────────────────────────
export const FILE_TYPE_COLORS: Record<FileType, string> = {
  USD:  'bg-violet-500/20 text-violet-300 border-violet-500/30',
  OBJ:  'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  STL:  'bg-blue-500/20 text-blue-300 border-blue-500/30',
  URDF: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  FBX:  'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  PLY:  'bg-pink-500/20 text-pink-300 border-pink-500/30',
  GLTF: 'bg-teal-500/20 text-teal-300 border-teal-500/30',
  SDF:  'bg-red-500/20 text-red-300 border-red-500/30',
  DAE:  'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  MJCF: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
}

export const ORGAN_LABELS: Record<OrganSystem, string> = {
  cardiac:         'Cardiac',
  hepatobiliary:   'Hepatobiliary',
  urologic:        'Urologic',
  gynecologic:     'Gynecologic',
  colorectal:      'Colorectal',
  thoracic:        'Thoracic',
  neurologic:      'Neurologic',
  orthopedic:      'Orthopedic',
  vascular:        'Vascular',
  gastrointestinal:'GI Tract',
  general:         'General',
}

export const SURGICAL_SYSTEM_LABELS: Record<SurgicalSystem, string> = {
  'davinci-xi': 'da Vinci Xi',
  'davinci-x':  'da Vinci X',
  'davinci-sp': 'da Vinci SP',
  'davinci-si': 'da Vinci Si',
  'versius':    'Versius',
  'hugo':       'Hugo RAS',
  'senhance':   'Senhance',
  'ottava':     'Ottava',
  'mira':       'MIRA',
  'raven-ii':   'Raven II',
  'lbr-med':    'LBR Med',
  'generic':    'Generic',
  'manual':     'Manual / Laparoscopic',
}

export const RL_FRAMEWORK_LABELS: Record<RLFramework, string> = {
  'isaac-sim': 'Isaac Sim',
  'mujoco':    'MuJoCo',
  'gazebo':    'Gazebo',
  'pybullet':  'PyBullet',
  'orbit':     'ORBIT',
  'robosuite': 'robosuite',
  'sapien':    'SAPIEN',
  'webots':    'Webots',
  'other':     'Other',
}
