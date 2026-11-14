import type { CSSProperties } from 'react'

const colors = ['#346cf5', '#65c7ff', '#9a77f5', '#ffb54a', '#f57ca9', '#59ccb5']
const pieces = Array.from({ length: 36 }, (_, index) => {
  const angle = index * 2.39996
  const distance = 65 + (index * 19 % 66)
  return {
    '--burst-x': `${Math.cos(angle) * distance}px`,
    '--burst-y': `${Math.sin(angle) * distance - 15}px`,
    '--burst-delay': `${index % 6 * 18}ms`,
    '--burst-turn': `${index * 37}deg`,
    backgroundColor: colors[index % colors.length],
    borderRadius: index % 4 === 0 ? '50%' : '1px',
  } as CSSProperties
})

export function ConfettiBurst() {
  return <span className="confetti-burst" aria-hidden="true">{pieces.map((style, index) => <span key={index} className="confetti-piece" style={style}/>)}</span>
}
