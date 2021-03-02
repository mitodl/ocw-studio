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
