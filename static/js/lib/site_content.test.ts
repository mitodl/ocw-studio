import { cloneDeep } from "lodash"

import MarkdownEditor from "../components/widgets/MarkdownEditor"
import FileUploadField from "../components/widgets/FileUploadField"
import SelectField from "../components/widgets/SelectField"
import BooleanField from "../components/widgets/BooleanField"

import {
  makeConfigField,
  makeWebsiteConfigField,
  makeWebsiteContentDetail,
  makeFileConfigItem
} from "../util/factories/websites"
import {
  componentFromWidget,
  contentFormValuesToPayload,
  contentInitialValues,
  fieldHasData,
  fieldIsVisible,
  newInitialValues,
  widgetExtraProps
} from "./site_content"
import { exampleSiteConfigFields, MAIN_PAGE_CONTENT_FIELD } from "../constants"
import { isIf, shouldIf } from "../test_util"

import {
  ConfigField,
  FieldValueCondition,
  WidgetVariant
} from "../types/websites"

describe("site_content", () => {
  describe("contentFormValuesToPayload", () => {
    it("changes the name of a 'content' field if it uses the markdown widget", () => {
      const values = {
        title: "a title",
        body:  "some content"
      }
      const fields: ConfigField[] = [
        {
          label:  "Title",
          name:   "title",
          widget: WidgetVariant.String
        },
        {
          label:  "Body",
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

    it("passes through 'title' and 'type'; namespaces other fields under 'metadata'", () => {
      const values = {
        title:       "a title",
        type:        "metadata",
        description: "a description here"
      }
      const fields = [
        {
          label:  "Title",
          name:   "title",
          widget: "string"
        },
        {
          label:  "Description",
          name:   "description",
          widget: "text"
        }
      ]
      // @ts-ignore
      const payload = contentFormValuesToPayload(values, fields)
      expect(payload).toStrictEqual({
        title:    "a title",
        type:     "metadata",
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
      const fields = makeFileConfigItem().fields
      // @ts-ignore
      const payload = contentFormValuesToPayload(values, fields)
      expect(payload instanceof FormData).toBe(true)
    })

    it("stores a value in metadata as is if it's not a special field", () => {
      const descriptionField: ConfigField = {
        label:    "Tags",
        default:  ["Design"],
        max:      3,
        min:      1,
        multiple: true,
        name:     "tags",
        options:  ["Design", "UX", "Dev"],
        widget:   WidgetVariant.Select
      }
      const payload = contentFormValuesToPayload(
        {
          tags: []
        },
        // @ts-ignore
        [descriptionField]
      )
      expect(payload).toStrictEqual({ metadata: { tags: [] } })
    })

    //
    ;[
      [null, true],
      ["", true],
      [undefined, false]
    ].forEach(([value, isPartOfPayload]) => {
      it(`${shouldIf(
        Boolean(isPartOfPayload)
      )} add the value to payload if the field value is ${String(
        value
      )}`, () => {
        const field: ConfigField = {
          name:   "description",
          label:  "Description",
          widget: WidgetVariant.String
        }
        const payload = contentFormValuesToPayload(
          {
            // @ts-ignore
            description: value
          },
          [field]
        )
        expect(Object.values(payload).length).toBe(isPartOfPayload ? 1 : 0)
      })
    })
  })

  describe("contentInitialValues", () => {
    it("from a content object", () => {
      const content = makeWebsiteContentDetail()
      // combine all possible fields so we can test all code paths
      const fields = cloneDeep(exampleSiteConfigFields)
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
      // find a field with a default value and one without
      const fieldWithDefault = exampleSiteConfigFields.find(
        (field: ConfigField) => field.default
      )
      const fieldWithoutDefault = exampleSiteConfigFields.find(
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
        [WidgetVariant.Markdown, ""],
        [WidgetVariant.File, ""],
        [WidgetVariant.Boolean, false],
        [WidgetVariant.Text, ""],
        [WidgetVariant.String, ""],
        [WidgetVariant.Select, ""]
      ].forEach(([widget, expectation]) => {
        const field = makeWebsiteConfigField({
          widget,
          label: "Widget"
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
        [WidgetVariant.Text, "textarea"],
        [WidgetVariant.Hidden, null]
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

  describe("fieldIsVisible and fieldHasData", () => {
    [
      [true, "input", { conditionField: "matching value" }, true, true],
      [true, "input", { conditionField: "non-matching value" }, false, false],
      [false, "input", { conditionField: "matching value" }, true, true],
      [false, "input", { conditionField: "non-matching value" }, true, true],
      [true, "hidden", { conditionField: "matching value" }, false, true],
      [true, "hidden", { conditionField: "non-matching value" }, false, false],
      [false, "hidden", { conditionField: "matching value" }, false, true],
      [false, "hidden", { conditionField: "non-matching value" }, false, true]
    ].forEach(
      ([hasCondition, widget, values, expectedVisible, expectedHasData]) => {
        // @ts-ignore
        it(`${isIf(expectedVisible)} visible if the condition ${isIf(
          // @ts-ignore
          hasCondition
          // @ts-ignore
        )} existing and value is a ${values.conditionField}`, () => {
          const condition: FieldValueCondition = {
            field:  "conditionField",
            equals: "matching value"
          }
          const field = makeConfigField()
          // @ts-ignore
          field.widget = widget
          if (hasCondition) {
            field.condition = condition
          }
          // @ts-ignore
          expect(fieldIsVisible(field, values)).toBe(expectedVisible)
          // @ts-ignore
          expect(fieldHasData(field, values)).toBe(expectedHasData)
        })
      }
    )
  })
})
