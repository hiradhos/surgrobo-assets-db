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

// ── Anatomy-specific metadata ───────────────────────────────────────────────────

/** How the anatomy model was produced */
export type CreationMethod =
  | 'ct-scan'
  | 'mri'
  | 'photogrammetry'
  | 'synthetic'
  | 'anatomist'
  | 'cadaver'
  | 'unknown'

/** Pathological or normal state of the anatomy */
export type ConditionType =
  | 'healthy'
  | 'tumor'
  | 'fracture'
  | 'defect'
  | 'variant'
  | 'pathologic'
  | 'unknown'

/** Biological sex of the anatomy source */
export type Sex = 'male' | 'female' | 'unknown'

/** Which anatomy database collection the record came from */
export type SourceCollection =
  | 'humanatlas'
  | 'medshapenet'
  | 'nih3d'
  | 'bodyparts3d'
  | 'anatomytool'
  | 'sketchfab'
  | 'embodi3d'
  | 'thingiverse'
  | 'other'

// ── Asset source ───────────────────────────────────────────────────────────────
export type SourceType = 'arxiv' | 'github' | 'atlas-database' | 'dataset' | 'manual'

// ── Core asset record ──────────────────────────────────────────────────────────
export interface Asset {
  id: string
  name: string
  description: string
  fileTypes: FileType[]
  // Classification (from LLM for GitHub assets; structured for atlas assets)
  patientType: PatientType
  organSystem: OrganSystem
  bodyPart?: string           // specific organ name, e.g. "liver", "femur"
  sex?: Sex
  conditionType?: ConditionType
  creationMethod?: CreationMethod
  category?: string           // surgical-robot-model | anatomical-model | etc.
  surgicalSystem: SurgicalSystem
  rlFrameworks: RLFramework[]
  // Source provenance
  sourceType: SourceType
  sourceCollection?: SourceCollection | null  // non-null only for atlas-database entries
  arxivId?: string
  arxivTitle?: string
  githubRepo?: string
  githubStars?: number
  authors?: string[]
  year?: number
  tags: string[]
  downloadUrl?: string
  previewUrl?: string
  sourceKey?: string
  license?: string
  citation?: string
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
  sourceCollections: SourceCollection[]
  conditionTypes: ConditionType[]
  creationMethods: CreationMethod[]
  sexes: Sex[]
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
  sourceCollections: [],
  conditionTypes: [],
  creationMethods: [],
  sexes: [],
  yearRange: [2018, 2026],
}

// ── Display helpers ────────────────────────────────────────────────────────────
export const FILE_TYPE_COLORS: Record<FileType, string> = {
  USD:  'bg-violet-100 text-violet-700 border-violet-300 dark:bg-violet-900/30 dark:text-violet-300 dark:border-violet-700/50',
  OBJ:  'bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-700/50',
  STL:  'bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700/50',
  URDF: 'bg-orange-100 text-orange-700 border-orange-300 dark:bg-orange-900/30 dark:text-orange-300 dark:border-orange-700/50',
  FBX:  'bg-yellow-100 text-yellow-700 border-yellow-300 dark:bg-yellow-900/30 dark:text-yellow-300 dark:border-yellow-700/50',
  PLY:  'bg-pink-100 text-pink-700 border-pink-300 dark:bg-pink-900/30 dark:text-pink-300 dark:border-pink-700/50',
  GLTF: 'bg-teal-100 text-teal-700 border-teal-300 dark:bg-teal-900/30 dark:text-teal-300 dark:border-teal-700/50',
  SDF:  'bg-red-100 text-red-700 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700/50',
  DAE:  'bg-indigo-100 text-indigo-700 border-indigo-300 dark:bg-indigo-900/30 dark:text-indigo-300 dark:border-indigo-700/50',
  MJCF: 'bg-amber-100 text-amber-700 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700/50',
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

export const CONDITION_TYPE_LABELS: Record<ConditionType, string> = {
  'healthy':    'Healthy / Reference',
  'tumor':      'Tumor / Cancer',
  'fracture':   'Fracture',
  'defect':     'Congenital Defect',
  'variant':    'Anatomic Variant',
  'pathologic': 'Pathologic',
  'unknown':    'Unknown',
}

export const CREATION_METHOD_LABELS: Record<CreationMethod, string> = {
  'ct-scan':       'CT Scan',
  'mri':           'MRI',
  'photogrammetry':'Photogrammetry',
  'synthetic':     'Synthetic / Procedural',
  'anatomist':     "Anatomist's Rendition",
  'cadaver':       'Cadaver Dissection',
  'unknown':       'Unknown',
}

export const SEX_LABELS: Record<Sex, string> = {
  'male':    'Male',
  'female':  'Female',
  'unknown': 'Unknown',
}

export const SOURCE_COLLECTION_LABELS: Record<SourceCollection, string> = {
  'humanatlas':  'Human Reference Atlas (HuBMAP)',
  'medshapenet': 'MedShapeNet 2.0',
  'nih3d':       'NIH 3D Print Exchange',
  'bodyparts3d': 'BodyParts3D',
  'anatomytool': 'AnatomyTool.org',
  'sketchfab':   'Sketchfab',
  'embodi3d':    'Embodi3D',
  'thingiverse': 'Thingiverse',
  'other':       'Other',
}
