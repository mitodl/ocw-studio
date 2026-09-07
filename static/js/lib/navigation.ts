/**
 * Thin wrappers around `window.location` mutations.
 *
 * jsdom makes `window.location` and its members (e.g. `reload`) unforgeable
 * and non-configurable, matching real browsers, so tests cannot mock them
 * directly via `jest.spyOn`/`Object.defineProperty`. Routing calls through
 * these functions keeps that behavior mockable with `jest.mock`.
 */
export function reloadPage(): void {
  window.location.reload()
}

export function redirectTo(url: string): void {
  window.location.href = url
}
