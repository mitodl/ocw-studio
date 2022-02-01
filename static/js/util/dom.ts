export const scrollToElement = (container: HTMLElement, selector: string) => {
  const errorElement = container.querySelector<HTMLElement>(selector)
  if (!errorElement) {
    return
  }
  const { matches: prefersReducedMotion } = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  )
  errorElement.scrollIntoView({
    behavior: prefersReducedMotion ? "auto" : "smooth",
    block:    "center"
  })
  errorElement.focus({ preventScroll: true })
}
