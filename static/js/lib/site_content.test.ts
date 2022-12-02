import { cloneDeep } from "lodash"

import MarkdownEditor from "../components/widgets/MarkdownEditor"
import FileUploadField from "../components/widgets/FileUploadField"
import SelectField from "../components/widgets/SelectField"
import BooleanField from "../components/widgets/BooleanField"
import RelationField from "../components/widgets/RelationField"
import MenuField from "../components/widgets/MenuField"
import WebsiteCollectionField from "../components/widgets/WebsiteCollectionField"

import {
  makeWebsiteDetail,
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
  hasMainContentField,
  renameNestedFields,
  addDefaultFields,
  DEFAULT_TITLE_FIELD
} from "./site_content"
import { exampleSiteConfigFields, MAIN_PAGE_CONTENT_FIELD } from "../constants"
import { assertNotNil, shouldIf } from "../test_util"

import {
  ConfigField,
  FieldValueCondition,
  ObjectConfigField,
  StringConfigField,
  WidgetVariant
} from "../types/websites"
import HierarchicalSelectField from "../components/widgets/HierarchicalSelectField"

const OUR_WEBSITE = "our-website"
describe("site_content", () => {
  const defaultsMapping = {
    [WidgetVariant.Markdown]: "",
    [WidgetVariant.File]:     null,
    [WidgetVariant.Boolean]:  false,
    [WidgetVariant.Text]:     "",
    [WidgetVariant.String]:   "",
    [WidgetVariant.Select]:   "",
    [WidgetVariant.Relation]: { website: OUR_WEBSITE, content: "" },
    [WidgetVariant.Menu]:     [],
    [WidgetVariant.Hidden]:   "",
    [WidgetVariant.Object]:   {
      ["nested-one"]: "",
      ["nested-two"]: ""
    },
    [WidgetVariant.HierarchicalSelect]: [],
    unexpected_type:                    ""
  }

  describe("contentFormValuesToPayload", () => {
    let fieldHasDataMock: jest.MockedFunction<any>

    afterEach(() => {
      if (fieldHasDataMock) {
        fieldHasDataMock.mockRestore()
      }
    })

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
      const payload = contentFormValuesToPayload(
        values,
        fields,
        makeWebsiteDetail()
      )
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
          widget: WidgetVariant.String as const
        },
        {
          label:  "Description",
          name:   "description",
          widget: WidgetVariant.Text as const
        }
      ]

      const payload = contentFormValuesToPayload(
        values,
        fields,
        makeWebsiteDetail()
      )
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
        upload:      mockFile
      }
      const fields = [
        {
          label:  "Image",
          name:   "upload",
          widget: WidgetVariant.File as const
        },
        ...makeFileConfigItem().fields
      ]

      const payload = contentFormValuesToPayload(
        values,
        fields,
        makeWebsiteDetail()
      )
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
        [descriptionField],
        makeWebsiteDetail()
      )
      expect(payload).toStrictEqual({ metadata: { tags: [] } })
    })

    it.each([
      { value: null, isPartOfPayload: true, should: "Should" },
      { value: "", isPartOfPayload: true, should: "Should" },
      { value: undefined, isPartOfPayload: false, should: "Should NOT" }
    ])(
      "$should add the value to payload if the field value is $value",
      ({ value, isPartOfPayload }) => {
        const field: ConfigField = {
          name:   "description",
          label:  "Description",
          widget: WidgetVariant.String
        }
        const payload = contentFormValuesToPayload(
          {
            // @ts-expect-error Undefined is not one of the permitted types, but this test is being extra cautious.
            description: value
          },
          [field],
          makeWebsiteDetail()
        )
        expect(Object.values(payload).length).toBe(isPartOfPayload ? 1 : 0)
      }
    )

    it("uses a default empty value if the original value shouldn't be sent to the server", () => {
      for (const [widget, expectedDefault] of Object.entries(defaultsMapping)) {
        const field = makeWebsiteConfigField({
          widget,
          name:      "test-field",
          // condition should never match, which will cause fieldHasData to always return false
          condition: { field: "doesn't exist", equals: "none" },
          fields:    [
            makeWebsiteConfigField({ name: "nested-one" }),
            makeWebsiteConfigField({ name: "nested-two" })
          ]
        })
        const payload = contentFormValuesToPayload({}, [field], {
          ...makeWebsiteDetail(),
          name: OUR_WEBSITE
        })
        if (widget === WidgetVariant.File) {
          expect(payload["metadata"]).toBeUndefined()
        } else {
          expect(payload["metadata"]["test-field"]).toStrictEqual(
            expectedDefault
          )
        }
      }
    })

    it("creates a payload using data from each inner field in an object field", () => {
      const field = makeWebsiteConfigField({
        widget: WidgetVariant.Object,
        fields: [
          makeWebsiteConfigField({ widget: WidgetVariant.Boolean }),
          makeWebsiteConfigField({ widget: WidgetVariant.Boolean })
        ]
      }) as ObjectConfigField
      const payload = contentFormValuesToPayload(
        {
          [field.name]: {
            [field.fields[1].name]: true
          }
        },
        [field],
        makeWebsiteDetail()
      )
      expect(payload).toStrictEqual({
        metadata: {
          [field.name]: {
            [field.fields[0].name]: undefined,
            [field.fields[1].name]: true
          }
        }
      })
    })

    it("removes values and uses default data in an field inside an object if the inner field should not send data", () => {
      const field = makeWebsiteConfigField({
        widget:    WidgetVariant.Object,
        name:      "object",
        condition: {
          field:  "object",
          equals: true
        },
        fields: [
          makeWebsiteConfigField({ widget: WidgetVariant.Boolean }),
          makeWebsiteConfigField({ widget: WidgetVariant.Boolean })
        ]
      }) as ObjectConfigField

      const values = {
        [field.name]: {
          [field.fields[1].name]: true
        }
      }
      const payload = contentFormValuesToPayload(
        values,
        [field],
        makeWebsiteDetail()
      )
      expect(payload).toStrictEqual({
        metadata: {
          [field.name]: {
            [field.fields[0].name]: false,
            [field.fields[1].name]: false
          }
        }
      })
    })
  })

  describe("contentInitialValues", () => {
    it("from a content object", () => {
      const content = makeWebsiteContentDetail()
      // combine all possible fields so we can test all code paths
      const fields = cloneDeep(exampleSiteConfigFields)
      const payload = contentInitialValues(content, fields, makeWebsiteDetail())
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
      assertNotNil(fieldWithDefault)
      assertNotNil(fieldWithoutDefault)

      const fields = [fieldWithDefault, fieldWithoutDefault]

      const values = newInitialValues(fields, makeWebsiteDetail())
      expect(values[fieldWithDefault.name]).toBe(fieldWithDefault.default)

      expect(values[fieldWithoutDefault.name]).toBe("")
    })

    it("should use appropriate defaults for different widgets", () => {
      Object.entries(defaultsMapping).forEach(([widget, expectation]) => {
        const field = makeWebsiteConfigField({
          widget,
          label:  "Widget",
          fields: [
            makeWebsiteConfigField({ name: "nested-one" }),
            makeWebsiteConfigField({ name: "nested-two" })
          ]
        })
        const website = { ...makeWebsiteDetail(), name: OUR_WEBSITE }
        const initialValues = newInitialValues([field], website)
        expect(initialValues).toStrictEqual({ widget: expectation })
      })
    })

    it("should use appropriate default for multiple select widget", () => {
      const field = makeWebsiteConfigField({
        widget:   WidgetVariant.Select,
        multiple: true,
        label:    "Widget"
      })
      expect(newInitialValues([field], makeWebsiteDetail())).toStrictEqual({
        widget: []
      })
    })

    it("should use appropriate default for multiple relation", () => {
      const field = makeWebsiteConfigField({
        widget:   WidgetVariant.Relation,
        multiple: true,
        label:    "Widget"
      })
      const website = makeWebsiteDetail()

      expect(newInitialValues([field], website)).toStrictEqual({
        widget: {
          website: website.name,
          content: []
        }
      })
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
      expect(newInitialValues([field], makeWebsiteDetail())).toStrictEqual({
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
        [WidgetVariant.Relation, RelationField],
        [WidgetVariant.Menu, MenuField],
        [WidgetVariant.HierarchicalSelect, HierarchicalSelectField],
        [WidgetVariant.WebsiteCollection, WebsiteCollectionField],
        ["unexpected_type", "input"]
      ].forEach(([widget, expected]) => {
        const field = makeWebsiteConfigField({
          widget: widget as WidgetVariant
        })
        expect(componentFromWidget(field)).toBe(expected)
      })
    })
  })

  describe("widgetExtraProps", () => {
    it("should grab the markdown props for a markdown widget", () => {
      const field = makeWebsiteConfigField({
        widget:  WidgetVariant.Markdown,
        minimal: false,
        link:    ["resource", "page"],
        embed:   ["resource"]
      })
      expect(widgetExtraProps(field)).toStrictEqual({
        minimal: false,
        link:    ["resource", "page"],
        embed:   ["resource"]
      })
    })

    it("sets minimal = true for markdown fields by default", () => {
      const field = makeWebsiteConfigField({ widget: WidgetVariant.Markdown })
      expect(widgetExtraProps(field)).toStrictEqual({
        minimal: true,
        link:    [],
        embed:   []
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

    it("should grab menu props for the menu widget", () => {
      const field = makeWebsiteConfigField({
        widget:      WidgetVariant.Menu,
        collections: ["collection1", "collection2"]
      })
      expect(widgetExtraProps(field)).toStrictEqual({
        collections: ["collection1", "collection2"]
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

    it("should grab extra props for the hierarchical select widget", () => {
      const extras = {
        options_map: "options-map",
        levels:      ["some", "levels"]
      }
      const field = makeWebsiteConfigField({
        widget: WidgetVariant.HierarchicalSelect,
        ...extras
      })
      expect(widgetExtraProps(field)).toStrictEqual(extras)
    })
  })

  describe("main content UI", () => {
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

    it("hasMainContentField should return true when appropriate", () => {
      const configFields = [
        {
          ...makeWebsiteConfigField({ widget: WidgetVariant.Markdown }),
          name: MAIN_PAGE_CONTENT_FIELD
        },
        {
          ...makeWebsiteConfigField({ widget: WidgetVariant.Text }),
          name: "my-text"
        },
        {
          ...makeWebsiteConfigField({ widget: WidgetVariant.Boolean }),
          name: "my-boolean"
        }
      ]
      expect(hasMainContentField(configFields)).toEqual(true)
      expect(hasMainContentField(configFields.slice(1))).toEqual(false)
    })
  })

  describe("fieldIsVisible and fieldHasData", () => {
    const condition: FieldValueCondition = {
      field:  "conditionField",
      equals: "matching value"
    }
    const conditionCases = [
      [true, { conditionField: "matching value" }, true],
      [true, { conditionField: "non-matching value" }, false],
      [false, { conditionField: "matching value" }, true],
      [false, { conditionField: "non-matching value" }, true]
    ] as const
    test.each(conditionCases)(
      "When field has condition, is visible iff condition is met",
      (hasCondition, values, isMet) => {
        const field = makeWebsiteConfigField()
        field.widget = WidgetVariant.Text
        if (hasCondition) {
          field.condition = condition
        }
        // Only visible if condition is met
        expect(fieldIsVisible(field, values)).toBe(isMet)
        // Only has data if condition is met
        expect(fieldHasData(field, values)).toBe(isMet)
      }
    )

    test.each(conditionCases)(
      "Hidden field is never visible, but has data iff condition is met",
      (hasCondition, values, isMet) => {
        const field = makeWebsiteConfigField()
        field.widget = WidgetVariant.Hidden
        if (hasCondition) {
          field.condition = condition
        }
        // Only visible if condition is met
        expect(fieldIsVisible(field, values)).toBe(false)
        // Only has data if condition is met
        expect(fieldHasData(field, values)).toBe(isMet)
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

    it("should rename fields for a Relation field", () => {
      const field = makeWebsiteConfigField({
        widget: WidgetVariant.Relation,
        label:  "myobject"
      })

      expect(renameNestedFields([field])[0].name).toEqual("myobject.content")
    })

    it("should leave others alone", () => {
      const fields = Object.values(WidgetVariant)
        .filter(
          widget =>
            widget !== WidgetVariant.Object && widget !== WidgetVariant.Relation
        )
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
        /**
         * configItem has type Repeatable... | Singleton...
         * And `addDefaultFields` is overloaded with one signature for each.
         * Its implementation (but no declared overload) accepts the union.
         * TS only considers the delcarations, not the implementation.
         * We could add a declaration for the union, but we never need it
         * except in this test.
         */
        // @ts-expect-error See above
        expect(addDefaultFields(configItem).fields).toEqual(expectedResult)
      })
    })
  })
})
