import { FormikState } from "formik"

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
export const nextTick = () => wait(0)

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
export const assertNotNil: <T>(value: T) => asserts value is NonNullable<T> = value => {
  if (value !== undefined && value !== null) return
  throw new Error('Expected value not to be undefined and not to be null.')
}
