import { cloneDeep } from "lodash"

import MarkdownEditor from "../components/widgets/MarkdownEditor"
import FileUploadField from "../components/widgets/FileUploadField"
import SelectField from "../components/widgets/SelectField"
import BooleanField from "../components/widgets/BooleanField"
import RelationField from "../components/widgets/RelationField"

import {
  makeWebsiteConfigField,
  makeWebsiteContentDetail,
  makeFileConfigItem,
  makeRepeatableConfigItem,
  makeSingletonConfigItem
} from "../util/factories/websites"
import {
  componentFromWidget,
  contentFormValuesToPayload,
  contentInitialValues,
  fieldHasData,
  fieldIsVisible,
  newInitialValues,
  widgetExtraProps,
  isMainContentField,
  splitFieldsIntoColumns,
  renameNestedFields,
  addDefaultFields,
  DEFAULT_TITLE_FIELD
} from "./site_content"
import { exampleSiteConfigFields, MAIN_PAGE_CONTENT_FIELD } from "../constants"
import { isIf, shouldIf } from "../test_util"

import {
  ConfigField,
  FieldValueCondition,
  ObjectConfigField,
  StringConfigField,
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
        tags:                      [],
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
        [WidgetVariant.File, null],
        [WidgetVariant.Boolean, false],
        [WidgetVariant.Text, ""],
        [WidgetVariant.String, ""],
        [WidgetVariant.Select, ""],
        [WidgetVariant.Relation, ""]
      ].forEach(([widget, expectation]) => {
        const field = makeWebsiteConfigField({
          widget,
          label: "Widget"
        })
        const initialValues = newInitialValues([field])
        expect(initialValues).toStrictEqual({ widget: expectation })
      })
    })

    it("should use appropriate default for multiple select widget", () => {
      const field = makeWebsiteConfigField({
        widget:   WidgetVariant.Select,
        multiple: true,
        label:    "Widget"
      })
      expect(newInitialValues([field])).toStrictEqual({ widget: [] })
    })

    it("should use appropriate default for multiple relation", () => {
      const field = makeWebsiteConfigField({
        widget:   WidgetVariant.Relation,
        multiple: true,
        label:    "Widget"
      })
      expect(newInitialValues([field])).toStrictEqual({ widget: [] })
    })

    it("should use appropriate default for Object widget", () => {
      const field = makeWebsiteConfigField({
        widget: WidgetVariant.Object,
        label:  "myobject",
        fields: [
          makeWebsiteConfigField({
            widget: WidgetVariant.String,
            label:  "mystring"
          }),
          makeWebsiteConfigField({
            widget:   WidgetVariant.Select,
            multiple: true,
            label:    "myselect"
          })
        ]
      })
      expect(newInitialValues([field])).toStrictEqual({
        myobject: {
          myselect: [],
          mystring: ""
        }
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
        [WidgetVariant.Hidden, null],
        [WidgetVariant.Relation, RelationField]
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

    it("should grab relation props for the relation widget", () => {
      const field = makeWebsiteConfigField({
        widget:        WidgetVariant.Relation,
        collection:    "greatcollection",
        display_field: "the field to display!",
        max:           30,
        min:           22,
        multiple:      true
      })
      expect(widgetExtraProps(field)).toStrictEqual({
        collection:    "greatcollection",
        display_field: "the field to display!",
        max:           30,
        min:           22,
        multiple:      true
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

  describe("main content and column UI", () => {
    it("isMainContentField should return true when appropriate", () => {
      Object.values(WidgetVariant).forEach(widget => {
        const configField = makeWebsiteConfigField({ widget })
        if (widget === WidgetVariant.Markdown) {
          configField.name = MAIN_PAGE_CONTENT_FIELD
          expect(isMainContentField(configField)).toBeTruthy()
        } else {
          expect(isMainContentField(configField)).toBeFalsy()
        }
      })
    })

    it("splitFieldsIntoColumns should split the main content field out from others", () => {
      const fields: ConfigField[] = [
        makeWebsiteConfigField({ widget: WidgetVariant.Text }),
        makeWebsiteConfigField({ widget: WidgetVariant.Select }),
        {
          label:  "Body",
          name:   MAIN_PAGE_CONTENT_FIELD,
          widget: WidgetVariant.Markdown
        },
        makeWebsiteConfigField({ widget: WidgetVariant.Boolean })
      ]
      expect(splitFieldsIntoColumns(fields)).toEqual([
        [fields[2]],
        [fields[0], fields[1], fields[3]]
      ])
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
          const field = makeWebsiteConfigField()
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

  describe("renameNestedFields", () => {
    it("should rename fields nested within an Object field", () => {
      const field = makeWebsiteConfigField({
        widget: WidgetVariant.Object,
        label:  "myobject",
        fields: [
          makeWebsiteConfigField({
            widget: WidgetVariant.String,
            label:  "mystring"
          }),
          makeWebsiteConfigField({
            widget:   WidgetVariant.Select,
            multiple: true,
            label:    "myselect"
          })
        ]
      })

      expect(
        (renameNestedFields([field])[0] as ObjectConfigField).fields.map(
          field => field.name
        )
      ).toEqual(["myobject.mystring", "myobject.myselect"])
    })

    it("should leave others alone", () => {
      const fields = Object.values(WidgetVariant)
        .filter(widget => widget !== WidgetVariant.Object)
        .map(widget => makeWebsiteConfigField({ widget }))
      expect(renameNestedFields(fields)).toEqual(fields)
    })
  })

  describe("addDefaultFields", () => {
    const exampleTitleField: StringConfigField = {
      name:     "title",
      label:    "Title!!!",
      widget:   WidgetVariant.String,
      required: true
    }
    const randomField = makeWebsiteConfigField({
      widget: WidgetVariant.String,
      label:  "My Label",
      name:   "myfield"
    })

    //
    ;[
      [true, false, true, "repeatable config item without 'title' field"],
      [true, true, false, "repeatable config item with 'title' field"],
      [false, false, false, "singleton config item without 'title' field"]
    ].forEach(([isRepeatable, inclTitleField, expAddField, desc]) => {
      it(`${shouldIf(
        expAddField
      )} add a 'title' field for ${desc.toString()}`, () => {
        const fields = inclTitleField ?
          [exampleTitleField, randomField] :
          [randomField]
        const configItem = {
          ...(isRepeatable ?
            makeRepeatableConfigItem() :
            makeSingletonConfigItem()),
          fields: fields
        }
        const expectedResult = expAddField ?
          [DEFAULT_TITLE_FIELD, randomField] :
          fields
        expect(addDefaultFields(configItem)).toEqual(expectedResult)
      })
    })
  })
})
