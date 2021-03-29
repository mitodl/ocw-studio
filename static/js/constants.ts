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

export const WEBSITES_PAGE_SIZE = 10
export const WEBSITE_CONTENT_PAGE_SIZE = 10

/*
 * This represents the "reserved" name for the field that captures the markdown content for the body of a page.
 * In Hugo terms, this is everything below the front matter in a ".md" file.
 */
export const MAIN_PAGE_CONTENT_FIELD = "content"
export const MAIN_PAGE_CONTENT_DB_FIELD = "markdown"

/* eslint-disable quote-props, key-spacing */
export const exampleSiteConfig: WebsiteStarterConfig = {
  collections: [
    {
      fields: [
        {
          label: "Title",
          name: "title",
          widget: "string",
          required: true
        },
        {
          label: "Content",
          name: "content",
          widget: "markdown",
          required: true
        }
      ],
      folder: "content",
      label: "Page",
      name: "page",
      category: "Content"
    },
    {
      fields: [
        {
          label: "Title",
          name: "title",
          widget: "string",
          required: true
        },
        {
          label: "Description",
          name: "description",
          widget: "markdown",
          minimal: true,
          required: true
        },
        {
          label: "File",
          name: "file",
          widget: "file",
          required: true
        }
      ],
      folder: "content",
      label: "Resource",
      name: "resource",
      category: "Content"
    },
    {
      fields: [
        {
          label: "Course Title",
          name: "title",
          widget: "text",
          required: true
        },
        {
          label: "Course Description",
          name: "description",
          widget: "markdown",
          help:
            "A description of the course that will be shown on the course site home page."
        }
      ],
      file: "data/metadata.json",
      label: "Site Metadata",
      name: "metadata",
      category: "Settings"
    }
  ]
}
