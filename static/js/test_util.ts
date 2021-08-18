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
