import wait from "waait"

export function getCookie(name: string): string {
  let cookieValue = ""

  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";")

    for (let cookie of cookies) {
      cookie = cookie.trim()

      // Does this cookie string begin with the name we want?
      if (cookie.substring(0, name.length + 1) === `${name}=`) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
        break
      }
    }
  }
  return cookieValue
}

const sharedWaitPromises: Record<string, Promise<void> | undefined> = {},
  latestDebouncedFetchArgs: Record<string, Parameters<typeof fetch>> = {}

/**
 * Wait for a period of time. The first await will delay for the full length of time. If there are other awaits
 * of this function before the time elapses, those awaits will only delay until the time elapses.
 *
 * For example:
 *   0ms:   await sharedWait("key", 300)
 *   100ms: await sharedWait("key", 300)
 *   200ms: await sharedWait("key", 300)
 *   301ms: await sharedWait("key", 300)
 *
 * The first three awaits will resolve at 300ms. The fourth await will resolve at 600ms.
 */
export const sharedWait = async (
  key: string,
  delayMillis: number
): Promise<void> => {
  if (sharedWaitPromises[key]) {
    await sharedWaitPromises[key]
    return
  }

  let resolve
  sharedWaitPromises[key] = new Promise(_resolve => {
    resolve = _resolve
  })
  await wait(delayMillis)
  delete sharedWaitPromises[key]
  // @ts-ignore
  resolve()
}

/**
 * A debounced fetch function which will make the specified request only if it
 * is not called again for `delayMillis` ms.
 *
 * Especially useful for typeahead option fetching!
 */
export const debouncedFetch = async (
  key: string,
  delayMillis: number,
  info: RequestInfo,
  init: RequestInit
): Promise<Response | null> => {
  // if the function gets called multiple times, store the latest version of the args
  latestDebouncedFetchArgs[key] = [info, init]
  await sharedWait(key, delayMillis)
  const latestArgs = latestDebouncedFetchArgs[key]
  if (latestArgs[0] !== info) {
    return null
  }
  delete latestDebouncedFetchArgs[key]
  return await fetch(...latestArgs)
}
