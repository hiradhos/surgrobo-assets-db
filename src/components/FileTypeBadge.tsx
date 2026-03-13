import type { FileType } from '../types'
import { FILE_TYPE_COLORS } from '../types'

interface FileTypeBadgeProps {
  type: FileType
  size?: 'sm' | 'md'
}

export default function FileTypeBadge({ type, size = 'md' }: FileTypeBadgeProps) {
  return (
    <span
      className={[
        'inline-flex items-center rounded border font-mono font-medium tracking-wide',
        FILE_TYPE_COLORS[type],
        size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-[11px]',
      ].join(' ')}
    >
      .{type}
    </span>
  )
}
