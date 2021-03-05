import { WebsiteStarterConfig } from "./types/websites"

export const ROLE_ADMIN = "admin"
export const ROLE_EDITOR = "editor"
export const ROLE_GLOBAL = "global_admin"
export const ROLE_OWNER = "owner"

export const ROLE_LABELS = {
  [ROLE_GLOBAL]: "Administrator",
  [ROLE_ADMIN]:  "Administrator",
  [ROLE_EDITOR]: "Editor",
  [ROLE_OWNER]:  "Owner"
}

export const EDITABLE_ROLES = [ROLE_ADMIN, ROLE_EDITOR]

export const exampleSiteConfig: WebsiteStarterConfig = {
  collections: [
    {
      name:   "page",
      label:  "Page",
      fields: [
        {
          name:   "title",
          label:  "Title",
          widget: "string"
        },
        {
          name:   "content",
          label:  "Content",
          widget: "markdown"
        }
      ]
    },
    {
      name:   "resource",
      label:  "Resource",
      fields: [
        {
          name:   "title",
          label:  "Title",
          widget: "string"
        },
        {
          name:   "description",
          label:  "Description",
          widget: "text"
        }
      ]
    }
  ]
}
