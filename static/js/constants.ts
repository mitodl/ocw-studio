import { WebsiteStarterConfig } from "./types/websites"
import { WidgetVariant } from "./types/websites"

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
export const MAIN_PAGE_CONTENT_FIELD = "body"
export const MAIN_PAGE_CONTENT_DB_FIELD = "markdown"

/* eslint-disable quote-props, key-spacing */
export const exampleSiteConfig: WebsiteStarterConfig = {
  collections: [
    {
      fields: [
        {
          label: "Title",
          name: "title",
          widget: WidgetVariant.String,
          required: true
        },
        {
          label: "Body",
          name: "body",
          widget: WidgetVariant.Markdown,
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
          widget: WidgetVariant.String,
          required: true
        },
        {
          label: "Description",
          name: "description",
          widget: WidgetVariant.Markdown,
          minimal: true,
          required: true
        },
        {
          label: "File",
          name: "file",
          widget: WidgetVariant.File,
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
          widget: WidgetVariant.Text,
          required: true
        },
        {
          label: "Course Description",
          name: "description",
          widget: WidgetVariant.Markdown,
          help:
            "A description of the course that will be shown on the course site home page."
        },
        {
          label: "Tags",
          default: ["Design"],
          max: 3,
          min: 1,
          multiple: true,
          name: "tags",
          options: ["Design", "UX", "Dev"],
          widget: WidgetVariant.Select
        },
        {
          label: "Align Content",
          name: "align",
          widget: WidgetVariant.Select,
          options: ["left", "center", "right"]
        },
        {
          label: "Featured course",
          name: "featured",
          widget: WidgetVariant.Boolean,
          default: false
        }
      ],
      file: "data/metadata.json",
      label: "Site Metadata",
      name: "metadata",
      category: "Settings"
    }
  ]
}
