import { flatten } from "ramda"

import MarkdownEditor from "../components/widgets/MarkdownEditor"
import FileUploadField from "../components/widgets/FileUploadField"
import SelectField from "../components/widgets/SelectField"
import BooleanField from "../components/widgets/BooleanField"

import {
  makeWebsiteContentDetail,
  makeWebsiteStarterConfig,
  makeWebsiteConfigField
} from "../util/factories/websites"
import {
  contentFormValuesToPayload,
  contentInitialValues,
  newInitialValues,
  componentFromWidget,
  widgetExtraProps
} from "./site_content"
import { MAIN_PAGE_CONTENT_FIELD } from "../constants"
import { ConfigField, WidgetVariant } from "../types/websites"

describe("site_content", () => {
  describe("contentFormValuesToPayload", () => {
    it("changes the name of a 'content' field if it uses the markdown widget", () => {
      const values = {
        title:   "a title",
        content: "some content"
      }
      const fields: ConfigField[] = [
        {
          label:  "Title",
          name:   "title",
          widget: WidgetVariant.String
        },
        {
          label:  "Content",
          name:   MAIN_PAGE_CONTENT_FIELD,
          widget: WidgetVariant.Markdown
        }
      ]
      const payload = contentFormValuesToPayload(values, fields)
      expect(payload).toStrictEqual({
        markdown: "some content",
        title:    "a title"
      })
    })

    it("passes through title and type, and namespaces other fields under 'metadata'", () => {
      const values = {
        title:       "a title",
        type:        "resource",
        description: "a description here"
      }
      const fields = makeWebsiteStarterConfig().collections.find(
        item => item.name === "resource"
      )?.fields
      // @ts-ignore
      const payload = contentFormValuesToPayload(values, fields)
      expect(payload).toStrictEqual({
        title:    "a title",
        type:     "resource",
        metadata: {
          description: "a description here"
        }
      })
    })

    it("converts a payload to a FormData object if a file is included", () => {
      const mockFile = new File([new ArrayBuffer(1)], "file.jpg")
      const values = {
        title:       "a title",
        type:        "resource",
        description: "a description here",
        file:        mockFile
      }
      const fields = makeWebsiteStarterConfig().collections.find(
        item => item.name === "resource"
      )?.fields
      // @ts-ignore
      const payload = contentFormValuesToPayload(values, fields)
      expect(payload instanceof FormData).toBe(true)
    })

    it("stores a value in metadata as is if it's not a special field", () => {
      const descriptionField = makeWebsiteStarterConfig()
        .collections.find(item => item.name === "metadata")
        ?.fields.find(field => field.name === "tags")
      const payload = contentFormValuesToPayload(
        {
          tags: []
        },
        // @ts-ignore
        [descriptionField]
      )
      expect(payload).toStrictEqual({ metadata: { tags: [] } })
    })
  })

  describe("contentInitialValues", () => {
    it("from a content object", () => {
      const content = makeWebsiteContentDetail()
      // combine all possible fields so we can test all code paths
      const fields = flatten(
        makeWebsiteStarterConfig().collections.map(item => item.fields)
      )
      // @ts-ignore
      const payload = contentInitialValues(content, fields)
      expect(payload).toStrictEqual({
        tags:                      "",
        align:                     "",
        featured:                  false,
        file:                      null,
        title:                     content.title,
        description:               content.metadata?.description,
        [MAIN_PAGE_CONTENT_FIELD]: content.markdown
      })
    })
  })

  describe("newInitialValues", () => {
    it("creates initial values for each field, optionally with a default value", () => {
      const allFields = flatten(
        makeWebsiteStarterConfig().collections.map(item => item.fields)
      )
      // find a field with a default value and one without
      const fieldWithDefault = allFields.find(
        (field: ConfigField) => field.default
      )
      const fieldWithoutDefault = allFields.find(
        (field: ConfigField) => !field.default
      )
      const fields = [fieldWithDefault, fieldWithoutDefault]
      // @ts-ignore
      const values = newInitialValues(fields)
      // @ts-ignore
      expect(values[fieldWithDefault.name]).toBe(fieldWithDefault.default)
      // @ts-ignore
      expect(values[fieldWithoutDefault.name]).toBe("")
    })

    it("should use appropriate defaults for different widgets", () => {
      [
        ["markdown", ""],
        ["file", ""],
        ["boolean", false],
        ["text", ""],
        ["string", ""],
        ["select", ""]
      ].forEach(([widget, expectation]) => {
        const field = makeWebsiteConfigField({
          widget: widget as WidgetVariant,
          label:  "Widget"
        })
        const initialValues = newInitialValues([field])
        expect(initialValues).toStrictEqual({ widget: expectation })
      })
    })
  })

  describe("componentFromWidget", () => {
    it("returns the right thing", () => {
      [
        [WidgetVariant.Select, SelectField],
        [WidgetVariant.File, FileUploadField],
        [WidgetVariant.String, "input"],
        [WidgetVariant.Boolean, BooleanField],
        [WidgetVariant.Markdown, MarkdownEditor],
        [WidgetVariant.Text, "input"]
      ].forEach(([widget, expected]) => {
        const field = makeWebsiteConfigField({
          widget: widget as WidgetVariant
        })
        expect(componentFromWidget(field)).toBe(expected)
      })
    })
  })

  describe("widgetExtraProps", () => {
    it("should grab the minimal prop for a markdown widget", () => {
      const field = makeWebsiteConfigField({
        widget:  WidgetVariant.Markdown,
        minimal: true
      })
      expect(widgetExtraProps(field)).toStrictEqual({
        minimal: true
      })
    })

    it("should grab select props for a select widget", () => {
      const field = makeWebsiteConfigField({
        widget:   WidgetVariant.Select,
        options:  [],
        multiple: true,
        max:      30,
        min:      22
      })
      expect(widgetExtraProps(field)).toStrictEqual({
        options:  [],
        multiple: true,
        max:      30,
        min:      22
      })
    })

    it("should return no props for other WidgetVariants", () => {
      [
        WidgetVariant.File,
        WidgetVariant.String,
        WidgetVariant.Boolean,
        WidgetVariant.Text
      ].forEach((widget: WidgetVariant) => {
        expect(
          widgetExtraProps(makeWebsiteConfigField({ widget }))
        ).toStrictEqual({})
      })
    })
  })
})
