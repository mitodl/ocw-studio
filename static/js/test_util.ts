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

export const isIf = (tf: boolean | string): string => (tf ? "is" : "is not")

export const shouldIf = (tf: boolean | string): string =>
  tf ? "should" : "should not"
