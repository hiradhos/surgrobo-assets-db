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
