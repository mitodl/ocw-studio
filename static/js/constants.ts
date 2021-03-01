import { WebsiteStarterConfig } from "./types/websites"

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
          widget: "string"
        }
      ]
    }
  ]
}
