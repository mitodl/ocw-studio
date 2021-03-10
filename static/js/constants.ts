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

export const CONTENT_TYPE_PAGE = "page"
export const CONTENT_TYPE_RESOURCE = "resource"
export const CONTENT_TYPES = [CONTENT_TYPE_PAGE, CONTENT_TYPE_RESOURCE]

export const exampleSiteConfig: WebsiteStarterConfig = {
  collections: [
    {
      name:   CONTENT_TYPE_PAGE,
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
      name:   CONTENT_TYPE_RESOURCE,
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
