import { SchemaOf } from "yup"
import { FormikHelpers } from "formik"

export type FormSchema = SchemaOf<any>

/**
 * These are the primitive types which can be present in our site content
 * forms.
 */
export type SiteFormPrimitive = string | File | string[] | null | boolean

export type SiteFormValue =
  | SiteFormPrimitive
  | Record<string, SiteFormPrimitive>

export type SiteFormValues = Record<string, SiteFormValue>

export interface SubmitFunc {
  (values: any, formikHelpers: FormikHelpers<any>): void | Promise<any>
}
