import { useLayoutEffect, useRef } from 'react'

export function usePageTransition(pathname: string) {
  const previousPath = useRef(pathname)
  useLayoutEffect(() => {
    if (previousPath.current === pathname) return
    previousPath.current = pathname
    window.scrollTo(0, 0)
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const page = document.querySelector<HTMLElement>('main')
    if (preference.matches || !page || typeof page.animate !== 'function') return
    const animation = page.animate([
      { opacity: 0, transform: 'scale(.99)' },
      { opacity: 1, transform: 'scale(1)' },
    ], { duration: 260, easing: 'cubic-bezier(.22,.75,.3,1)' })
    animation.id = 'page-enter'
    const stopMotion = () => { if (preference.matches) animation.cancel() }
    preference.addEventListener('change', stopMotion)
    return () => { animation.cancel(); preference.removeEventListener('change', stopMotion) }
  }, [pathname])
}
