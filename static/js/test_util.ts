import { FormikState } from "formik"
import * as R from "ramda"

export const defaultFormikChildProps: FormikState<any> = {
  values:       {},
  errors:       {},
  touched:      {},
  isSubmitting: false,
  isValidating: false,
  status:       null,
  submitCount:  0
}

export const isIf = (
  tf: any // eslint-disable-line
): string => (tf ? "is" : "is not")

export const shouldIf = (
  tf: any // eslint-disable-line
): string => (tf ? "should" : "should not")

/**
 * Promisified version of setTimeout
 */
export const wait = async (ms: number): Promise<undefined> => {
  return new Promise(resolve => {
    setTimeout(() => {
      resolve(undefined)
    }, ms)
  })
}

/**
 * Wait for stuff currently in the event queue to finish.
 */
export const flushEventQueue = (fakeTimers = false) => {
  if (fakeTimers) {
    Promise.resolve().then(() => {
      /**
       * Unfortunately, jest does not provide a way to tell if fake timers are in
       * use. Related: https://github.com/facebook/jest/issues/10555
       */
      jest.advanceTimersByTime(0)
    })
  }
  return wait(0)
}

export const mockMatchMedia = () => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value:    jest.fn().mockImplementation(query => ({
      matches:             false,
      media:               query,
      onchange:            null,
      addEventListener:    jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent:       jest.fn()
    }))
  })

  return window.matchMedia as jest.Mock<any, [string]>
}

export const twoBooleanTestMatrix = [
  [true, true],
  [true, false],
  [false, true],
  [false, false]
]

export const getMockEditor = () => ({
  editing: {
    view: {
      focus: jest.fn()
    }
  }
})

/**
 * Type assertion that asserts value is not null or undefined.
 *
 * Unlike jest assertions, this will refine the type.
 * See https://github.com/DefinitelyTyped/DefinitelyTyped/issues/41179
 */
export const assertNotNil: <T>(
  value: T
) => asserts value is NonNullable<T> = value => {
  if (value !== undefined && value !== null) return
  throw new Error("Expected value not to be undefined and not to be null.")
}

/**
 * Type assertion that asserts value is not null or undefined.
 *
 * Unlike jest assertions, this will refine the type.
 * See https://github.com/DefinitelyTyped/DefinitelyTyped/issues/41179
 */
export const assertInstanceOf: <C extends { new (...args: any): any }>(
  value: unknown,
  Class: C
) => asserts value is InstanceType<C> = (value, Class) => {
  if (value instanceof Class) return
  throw new Error(`Expected value to be instanceof ${Class}`)
}

/**
 * Return an absolute url from a relative url
 */
export const absoluteUrl = (relative: string): string => {
  return window.location.origin + relative
}

/**
 * Returns an array that is the cartesian product of arrays `a` and `b`, with
 * items from `a` and items from `b` (shallowly) merged.
 *
 * The resulting shallow objects are convenient for setting up jest test cases.
 * (Shallow objects work better with jest's formatting on `each` commands.)
 * @example
 * ```ts
 * const a = [{ x: 1 }, { x: 2 }]
 * const b = [{ y: 10 }, { y: 20 }, { y: 30 }]
 * const ab = mergeXprod(a, b)
 * expect(ab).toStrictEqual([
 *  { x: 1, y: 10 },
 *  { x: 1, y: 20 },
 *  { x: 1, y: 30 },
 *  { x: 2, y: 10 },
 *  { x: 2, y: 20 },
 *  { x: 2, y: 30 },
 * ])
 * ```
 */
export const mergeXProd = <
  A extends Record<string, any>,
  B extends Record<string, any>
>(
    a: A[],
    b: B[]
  ): (A & B)[] => {
  return R.xprod(a, b).map(([x, y]) => ({ ...x, ...y }))
}

/**
 * Runs `cb` with a fake `window.location` object, then restores the original
 * `window.location` and returns the fake object for assertions.
 *
 * Why? Because:
 *  - JSDOM does not support navigation, so *some* things with window.location,
 *  like assigning to `href`, won't work.
 *  - and standard mocking techniques, like `jest.spyOn(window.location, 'href', 'set')
 *    don't work because `window.location` is not configurable.
 */
export const withFakeLocation = async (
  cb: () => Promise<void> | void
): Promise<void> => {
  const originalLocation = window.location
  try {
    window.location = { ...originalLocation }
  } catch (err) {
    await cb()
  } finally {
    window.location = originalLocation
  }
}
