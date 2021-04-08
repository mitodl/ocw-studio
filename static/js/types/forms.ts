export enum ContentFormType {
  Add = "add",
  Edit = "edit"
}

export type ValueType = string | File | string[] | null

export type SiteFormValues = Record<string, ValueType>
