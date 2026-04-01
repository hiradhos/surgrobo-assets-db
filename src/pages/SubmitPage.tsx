import { useState } from 'react'
import { CheckCircle2, Upload, Link2, AlertCircle } from 'lucide-react'
import type { FileType, OrganSystem, PatientType, RLFramework, SourceType, SurgicalSystem } from '../types'
import {
  ORGAN_LABELS, SURGICAL_SYSTEM_LABELS, RL_FRAMEWORK_LABELS, FILE_TYPE_COLORS,
} from '../types'
import FileTypeBadge from '../components/FileTypeBadge'

const FILE_TYPES: FileType[]   = ['USD', 'OBJ', 'STL', 'URDF', 'FBX', 'PLY', 'GLTF', 'SDF', 'DAE', 'MJCF']
const ORGAN_OPTS: OrganSystem[] = ['cardiac','hepatobiliary','urologic','gynecologic','colorectal','thoracic','neurologic','orthopedic','vascular','gastrointestinal','general']
const ROBOT_OPTS: SurgicalSystem[] = ['davinci-xi','davinci-x','davinci-sp','davinci-si','versius','hugo','senhance','ottava','mira','raven-ii','lbr-med','generic','manual']
const RL_OPTS: RLFramework[]   = ['isaac-sim','mujoco','gazebo','pybullet','orbit','robosuite','sapien','webots','other']
const PATIENT_OPTS: PatientType[] = ['adult','pediatric','neonatal','phantom','generic']

function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-1.5">{children}</label>
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 py-2.5 px-3 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20 transition-colors"
    />
  )
}

function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      rows={3}
      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 py-2.5 px-3 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20 transition-colors resize-none"
    />
  )
}

function Select({ value, onChange, children }: { value: string; onChange: (v: string) => void; children: React.ReactNode }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 py-2.5 px-3 text-sm text-slate-900 dark:text-slate-100 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20 transition-colors"
    >
      {children}
    </select>
  )
}

function ToggleChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded border px-2.5 py-1 text-[11px] font-medium transition-all',
        active
          ? 'border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
          : 'border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:bg-blue-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400 dark:hover:border-blue-700 dark:hover:text-blue-300',
      ].join(' ')}
    >
      {children}
    </button>
  )
}

function SectionCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-sm p-6 flex flex-col gap-4">
      {children}
    </div>
  )
}

function toggle<T>(arr: T[], val: T): T[] {
  return arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]
}

export default function SubmitPage() {
  const [submitted, setSubmitted] = useState(false)
  const [form, setForm] = useState({
    name: '',
    description: '',
    fileTypes: [] as FileType[],
    patientType: 'adult' as PatientType,
    organSystem: 'general' as OrganSystem,
    surgicalSystem: 'generic' as SurgicalSystem,
    rlFrameworks: [] as RLFramework[],
    sourceType: 'github' as SourceType,
    githubRepo: '',
    arxivId: '',
    downloadUrl: '',
    license: '',
    tags: '',
    authors: '',
    year: String(new Date().getFullYear()),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
  }

  if (submitted) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-24 flex flex-col items-center gap-6 text-center animate-fade-in">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/30 border border-emerald-300 dark:border-emerald-700/50">
          <CheckCircle2 size={40} className="text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <h3 className="text-xl font-bold text-slate-900 dark:text-white">Asset Submitted</h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
            Your asset has been submitted for review. It will appear in the database once validated.
          </p>
        </div>
        <button
          onClick={() => setSubmitted(false)}
          className="rounded-lg bg-blue-600 hover:bg-blue-700 px-6 py-2.5 text-sm font-medium text-white transition-colors"
        >
          Submit Another
        </button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">

      <div className="mb-8">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Submit an Asset</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Manually add a surgical robotics simulation asset from GitHub, a dataset repository, or a published paper.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">

        {/* Basic info */}
        <SectionCard>
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <Upload size={14} className="text-blue-600 dark:text-blue-400" />
            Asset Information
          </h3>

          <div>
            <Label>Asset Name *</Label>
            <Input
              required
              placeholder="e.g. da Vinci Xi Needle Driver — USD Scene"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            />
          </div>

          <div>
            <Label>Description *</Label>
            <Textarea
              required
              placeholder="Describe the asset, its contents, and intended use in surgical simulation / RL..."
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Authors</Label>
              <Input
                placeholder="Last, F.; Last, F. (comma-separated)"
                value={form.authors}
                onChange={e => setForm(f => ({ ...f, authors: e.target.value }))}
              />
            </div>
            <div>
              <Label>Year</Label>
              <Input
                type="number"
                min={2015}
                max={2030}
                value={form.year}
                onChange={e => setForm(f => ({ ...f, year: e.target.value }))}
              />
            </div>
          </div>

          <div>
            <Label>Tags</Label>
            <Input
              placeholder="comma-separated: suturing, deformable, tissue, needle"
              value={form.tags}
              onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
            />
          </div>
        </SectionCard>

        {/* File formats */}
        <SectionCard>
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <FileTypeBadge type="USD" size="sm" />
            File Formats *
          </h3>
          <div className="flex flex-wrap gap-2">
            {FILE_TYPES.map(ft => (
              <button
                type="button"
                key={ft}
                onClick={() => setForm(f => ({ ...f, fileTypes: toggle(f.fileTypes, ft) }))}
                className={[
                  'rounded border font-mono text-[11px] font-medium px-2 py-0.5 transition-all',
                  form.fileTypes.includes(ft)
                    ? FILE_TYPE_COLORS[ft]
                    : 'border-slate-200 bg-white text-slate-500 hover:border-blue-200 hover:bg-blue-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 dark:hover:border-slate-600',
                ].join(' ')}
              >
                .{ft}
              </button>
            ))}
          </div>
          {form.fileTypes.length === 0 && (
            <div className="flex items-center gap-2 text-[11px] text-amber-600 dark:text-amber-400">
              <AlertCircle size={12} />
              Select at least one file format
            </div>
          )}
        </SectionCard>

        {/* Clinical parameters */}
        <SectionCard>
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Clinical Parameters</h3>

          <div>
            <Label>Patient Type</Label>
            <div className="flex flex-wrap gap-2">
              {PATIENT_OPTS.map(p => (
                <ToggleChip key={p} active={form.patientType === p} onClick={() => setForm(f => ({ ...f, patientType: p }))}>
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </ToggleChip>
              ))}
            </div>
          </div>

          <div>
            <Label>Organ System</Label>
            <Select value={form.organSystem} onChange={v => setForm(f => ({ ...f, organSystem: v as OrganSystem }))}>
              {ORGAN_OPTS.map(o => (
                <option key={o} value={o}>{ORGAN_LABELS[o]}</option>
              ))}
            </Select>
          </div>

          <div>
            <Label>Surgical System</Label>
            <Select value={form.surgicalSystem} onChange={v => setForm(f => ({ ...f, surgicalSystem: v as SurgicalSystem }))}>
              {ROBOT_OPTS.map(r => (
                <option key={r} value={r}>{SURGICAL_SYSTEM_LABELS[r]}</option>
              ))}
            </Select>
          </div>

          <div>
            <Label>RL / Simulation Frameworks</Label>
            <div className="flex flex-wrap gap-2">
              {RL_OPTS.map(fw => (
                <ToggleChip
                  key={fw}
                  active={form.rlFrameworks.includes(fw)}
                  onClick={() => setForm(f => ({ ...f, rlFrameworks: toggle(f.rlFrameworks, fw) }))}
                >
                  {RL_FRAMEWORK_LABELS[fw]}
                </ToggleChip>
              ))}
            </div>
          </div>
        </SectionCard>

        {/* Source links */}
        <SectionCard>
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <Link2 size={14} className="text-blue-600 dark:text-blue-400" />
            Source & Links
          </h3>

          <div>
            <Label>Source Type</Label>
            <div className="flex flex-wrap gap-2">
              {(['arxiv', 'github', 'dataset', 'manual'] as SourceType[]).map(s => (
                <ToggleChip key={s} active={form.sourceType === s} onClick={() => setForm(f => ({ ...f, sourceType: s }))}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </ToggleChip>
              ))}
            </div>
          </div>

          {(form.sourceType === 'arxiv' || form.sourceType === 'github') && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>GitHub Repo (owner/name)</Label>
                <Input
                  placeholder="org/repo-name"
                  value={form.githubRepo}
                  onChange={e => setForm(f => ({ ...f, githubRepo: e.target.value }))}
                />
              </div>
              <div>
                <Label>arXiv ID</Label>
                <Input
                  placeholder="2403.12345"
                  value={form.arxivId}
                  onChange={e => setForm(f => ({ ...f, arxivId: e.target.value }))}
                />
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Download / DOI URL</Label>
              <Input
                type="url"
                placeholder="https://..."
                value={form.downloadUrl}
                onChange={e => setForm(f => ({ ...f, downloadUrl: e.target.value }))}
              />
            </div>
            <div>
              <Label>License</Label>
              <Input
                placeholder="MIT, CC BY 4.0, Apache 2.0..."
                value={form.license}
                onChange={e => setForm(f => ({ ...f, license: e.target.value }))}
              />
            </div>
          </div>
        </SectionCard>

        {/* Submit */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => setForm(f => ({ ...f, name: '', description: '' }))}
            className="rounded-lg border border-slate-300 dark:border-slate-600 px-5 py-2.5 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:border-slate-400 transition-colors"
          >
            Clear
          </button>
          <button
            type="submit"
            disabled={!form.name || !form.description || form.fileTypes.length === 0}
            className="flex items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-700 px-6 py-2.5 text-sm font-semibold text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <CheckCircle2 size={14} />
            Submit Asset
          </button>
        </div>

      </form>
    </div>
  )
}
