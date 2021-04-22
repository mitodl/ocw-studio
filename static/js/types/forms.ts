export enum ContentFormType {
  Add = "add",
  Edit = "edit"
}

export type SiteFormPrimitive = string | File | string[] | null | boolean

export type SiteFormValue =
  | SiteFormPrimitive
  | Record<string, SiteFormPrimitive>

export type SiteFormValues = Record<string, SiteFormValue>
