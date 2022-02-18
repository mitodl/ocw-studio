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

export const wait = async (ms: number): Promise<undefined> => {
  return new Promise(resolve => {
    setTimeout(() => {
      resolve(undefined)
    }, ms)
  })
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
