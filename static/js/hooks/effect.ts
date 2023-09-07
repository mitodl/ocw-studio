import { DependencyList, EffectCallback, useEffect } from "react"

/**
 * A debounced useEffect! Usage for this hook is identical to
 * 'vanilla' `useEffect`, except for the fact that your effect will
 * return at most every `delay` ms.
 */
export function useDebouncedEffect(
  effect: EffectCallback,
  deps: DependencyList,
  delay = 200,
) {
  useEffect(() => {
    const id = setTimeout(effect, delay)

    return () => {
      clearTimeout(id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, effect, delay])
}
