import { SchemaOf } from "yup"
import { FormikHelpers } from "formik"

export enum ContentFormType {
  Add = "add",
  Edit = "edit"
}

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

/**
 * WebsiteCollectionFormFields
 **/
export interface WebsiteCollectionFormFields {
  title: string
  description: string
}

/**
 * WebsiteCollectionItem form fields
 *
 * We pass the WebsiteCollection id in the API URL param
 * (/api/collections/:collectionId/items) so we don't need
 * to include it in the form.
 */
export interface WCItemCreateFormFields {
  website: string
}

export interface WCItemMoveFormFields {
  position: number
}

export interface SubmitFunc {
  (values: any, formikHelpers: FormikHelpers<any>): void | Promise<any>
}
