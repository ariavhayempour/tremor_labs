import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Equal, Info, History, UserRound, NotebookPen, Coffee, ArrowLeft, Check, Camera, Cable, Usb, Activity, ArrowDownToLine, ArrowRight, ChartNoAxesColumnIncreasing, Clock3, CodeXml, FileText, Hand, House, Menu, MoveUp, Pause, Play, RotateCcw, ShieldCheck, SlidersHorizontal, Sofa, X, type LucideIcon } from 'lucide-react'

const icons: Record<string, LucideIcon> = {
  history: History, user: UserRound, journal: NotebookPen, coffee: Coffee, back: ArrowLeft, check: Check, camera: Camera, connect: Cable, sensor: Usb, home: House, dashboard: ChartNoAxesColumnIncreasing, report: FileText,
  settings: SlidersHorizontal, dev: CodeXml, arrow: ArrowRight, shield: ShieldCheck,
  clock: Clock3, rest: Sofa, posture: MoveUp, reach: ArrowDownToLine, tap: Hand,
  up: ArrowUp, down: ArrowDown, same: Equal, chevronLeft: ChevronLeft, chevronRight: ChevronRight, info: Info,
  wave: Activity, menu: Menu, pause: Pause, play: Play, reset: RotateCcw, close: X,
}

export function Icon({ name, size = 22 }: { name: string; size?: number }) {
  const Symbol = icons[name] ?? Activity
  return <Symbol size={size} strokeWidth={1.7} aria-hidden="true" />
}
