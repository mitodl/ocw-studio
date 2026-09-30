import { getCookie } from "./api/util"

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

/**
 * Navigate to `url` with a POST form submission carrying the CSRF token, for
 * Django views that reject GET (e.g. login and logout).
 */
export function postTo(url: string): void {
  const form = document.createElement("form")
  form.method = "post"
  form.action = url
  const csrf = document.createElement("input")
  csrf.type = "hidden"
  csrf.name = "csrfmiddlewaretoken"
  csrf.value = getCookie("csrftoken")
  form.appendChild(csrf)
  document.body.appendChild(form)
  form.submit()
}
