import * as yup from "yup"
import { getContentSchema, WebsiteCollectionFormSchema } from "./validation"
import * as siteContentFuncs from "../../lib/site_content"
import sinon, { SinonSandbox } from "sinon"

import {
  makeRepeatableConfigItem,
  makeSingletonConfigItem,
  makeWebsiteConfigField
} from "../../util/factories/websites"
import { isIf } from "../../test_util"

import {
  ConfigItem,
  FileConfigField,
  MarkdownConfigField,
  StringConfigField,
  TextConfigField,
  WidgetVariant
} from "../../types/websites"

describe("form validation utils", () => {
  describe("website content validation", () => {
    const repeatableConfigItem = makeRepeatableConfigItem()
    const singletonConfigItem = makeSingletonConfigItem()
    const partialField = {
      name:  "myfield",
      label: "My Field"
    }
    const defaultFormValues = {
      title: "My Title"
    }
    let configItem: ConfigItem, sandbox: SinonSandbox

    beforeEach(() => {
      sandbox = sinon.createSandbox()
    })

    afterEach(() => {
      sandbox.restore()
    })

    describe("for 'title' field", () => {
      const titleField: StringConfigField = {
        name:     "title",
        label:    "Title",
        required: true,
        widget:   WidgetVariant.String
      }

      //
      ;[
        [null, true, false, true],
        [titleField, true, true, true],
        [null, false, false, false]
      ].forEach(([field, isRepeatable, fieldIncluded, expAddedTitleField]) => {
        it(`validates correctly if 'title' field ${isIf(
          fieldIncluded
        )} included, config item ${isIf(
          isRepeatable
        )} repeatable`, async () => {
          configItem = {
            ...(isRepeatable ? repeatableConfigItem : singletonConfigItem),
            // @ts-ignore
            fields: field ? [field] : []
          }
          const schema = getContentSchema(configItem, {})
          if (expAddedTitleField) {
            expect(() => schema.validateSync({})).toThrow(
              new yup.ValidationError("Title is a required field")
            )
            await expect(
              schema.isValid({ title: "My Title" })
            ).resolves.toBeTruthy()
          } else {
            expect(() => schema.validateSync({})).not.toThrow(
              new yup.ValidationError("Title is a required field")
            )
          }
        })
      })
    })

    it("should skip validation for fields which aren't visible", () => {
      configItem = {
        ...repeatableConfigItem,
        fields: [
          {
            ...partialField,
            widget:   WidgetVariant.String,
            required: true
          }
        ]
      }
      const values = { val: "ues" }
      let schema = getContentSchema(configItem, values)
      expect(() =>
        schema.validateSync({
          ...defaultFormValues,
          [partialField.name]: null
        })
      ).toThrow(`${partialField.label} is a required field`)

      const fieldIsVisibleStub = sandbox
        .stub(siteContentFuncs, "fieldIsVisible")
        .returns(false)
      schema = getContentSchema(configItem, values)
      // no exception thrown
      schema.validateSync({
        ...defaultFormValues,
        [partialField.name]: null
      })
      sinon.assert.calledWith(fieldIsVisibleStub, configItem.fields[0], values)
    })

    it("should skip validation for a title field which isn't visible", () => {
      configItem = {
        ...repeatableConfigItem,
        fields: [
          {
            ...partialField,
            name:     "title",
            widget:   WidgetVariant.String,
            required: true
          }
        ]
      }
      let schema = getContentSchema(configItem, {})
      expect(() =>
        schema.validateSync({
          ...defaultFormValues,
          ["title"]: null
        })
      ).toThrow(`${partialField.label} is a required field`)

      sandbox.stub(siteContentFuncs, "fieldIsVisible").returns(false)
      schema = getContentSchema(configItem, {})
      // no exception thrown
      schema.validateSync({
        ...defaultFormValues,
        ["title"]: null
      })
    })

    //
    ;[
      WidgetVariant.String,
      WidgetVariant.Text,
      WidgetVariant.Markdown,
      WidgetVariant.File
    ].forEach(widget => {
      it(`produces the correct validation schema for a required '${widget}' field`, () => {
        configItem = {
          ...repeatableConfigItem,
          fields: [
            {
              ...partialField,
              widget:   widget as WidgetVariant,
              required: true
            } as
              | StringConfigField
              | TextConfigField
              | MarkdownConfigField
              | FileConfigField
          ]
        }
        const schema = getContentSchema(configItem, {})
        expect(() =>
          schema.validateSync({
            ...defaultFormValues,
            [partialField.name]: null
          })
        ).toThrow(`${partialField.label} is a required field`)
      })
    })

    it("produces the correct validation schema for multiple fields", () => {
      configItem = {
        ...repeatableConfigItem,
        fields: [
          {
            name:     "myfield",
            label:    "My Field",
            widget:   WidgetVariant.String,
            required: true
          },
          {
            name:     "myfield2",
            label:    "My Second Field",
            widget:   WidgetVariant.String,
            required: true
          }
        ]
      }
      const schema = getContentSchema(configItem, {})
      for (const field of configItem.fields) {
        expect(() =>
          schema.validateSync({
            ...defaultFormValues,
            myfield:      "text",
            myfield2:     "text",
            [field.name]: null
          })
        ).toThrow(`${field.label} is a required field`)
      }
    })

    describe("select validation", () => {
      const makeSelectConfigItem = (props = {}): [ConfigItem, string] => {
        const configItem = {
          ...repeatableConfigItem,
          fields: [
            makeWebsiteConfigField({ widget: WidgetVariant.Select, ...props })
          ]
        }

        return [configItem, configItem.fields[0].name]
      }

      it("should validate for a required multiple select field", () => {
        const [configItem, name] = makeSelectConfigItem({
          multiple: true,
          required: true
        })
        const schema = getContentSchema(configItem, {})
        expect(() =>
          schema.validateSync({
            ...defaultFormValues,
            [name]: null
          })
        ).toThrow(new yup.ValidationError(`${name} is a required field.`))
      })

      it("should pass validation for valid multiple select values", async () => {
        const [configItem, name] = makeSelectConfigItem({ multiple: true })
        const schema = getContentSchema(configItem, {})
        await Promise.all(
          [[], ["some value"], ["some value", "another value"]].map(
            async value => {
              await expect(
                schema.isValid({
                  ...defaultFormValues,
                  [name]: value
                })
              ).resolves.toBeTruthy()
            }
          )
        )
      })

      it("should validate a multiple select field with max and min set", async () => {
        const [configItem, name] = makeSelectConfigItem({
          multiple: true,
          min:      1,
          max:      2
        })
        const schema = getContentSchema(configItem, {})

        await Promise.all(
          [
            [[], false, `${name} must have at least 1 entry.`],
            [["some value"], true, ""],
            [["some value", "another value"], true, ""],
            [
              ["some value", "another value", "yet another value"],
              false,
              `${name} may have at most 2 entries.`
            ]
          ].map(async ([value, shouldValidate, message]) => {
            if (shouldValidate) {
              await expect(
                schema.isValid({
                  ...defaultFormValues,
                  [name]: value
                })
              ).resolves.toBeTruthy()
            } else {
              await expect(
                schema.validate({
                  ...defaultFormValues,
                  [name]: value
                })
              ).rejects.toThrow(new yup.ValidationError(message as string))
            }
          })
        )
      })

      it("should validate a required non-multiple select field", async () => {
        const [configItem, name] = makeSelectConfigItem({ required: true })
        const schema = getContentSchema(configItem, {})

        expect(() =>
          schema.validateSync({
            ...defaultFormValues,
            [name]: ""
          })
        ).toThrow(new yup.ValidationError(`${name} is a required field`))
        await expect(
          schema.isValid({ ...defaultFormValues, [name]: "selected value" })
        ).resolves.toBeTruthy()
      })
    })

    describe("hierarchical select validation", () => {
      it("validates for a hierarchical select field", async () => {
        const configItem = {
          ...repeatableConfigItem,
          fields: [
            makeWebsiteConfigField({ widget: WidgetVariant.HierarchicalSelect })
          ]
        }
        const name = configItem.fields[0].name

        const schema = getContentSchema(configItem, {})
        expect(() =>
          schema.validateSync({
            ...defaultFormValues,
            [name]: "not-an-array"
          })
        ).toThrow(new yup.ValidationError(`${name} is a required field.`))
        await expect(
          schema.isValid({ ...defaultFormValues, [name]: ["selected value"] })
        ).resolves.toBeTruthy()
      })

      it("should validate a multiple select field with max and min set", async () => {
        const configItem = {
          ...repeatableConfigItem,
          fields: [
            makeWebsiteConfigField({
              widget:   WidgetVariant.HierarchicalSelect,
              multiple: true,
              min:      1,
              max:      2
            })
          ]
        }
        const name = configItem.fields[0].name
        const schema = getContentSchema(configItem, {})

        await Promise.all(
          [
            [[], false, `${name} must have at least 1 entry.`],
            [["some value"], true, ""],
            [["some value", "another value"], true, ""],
            [
              ["some value", "another value", "yet another value"],
              false,
              `${name} may have at most 2 entries.`
            ]
          ].map(async ([value, shouldValidate, message]) => {
            if (shouldValidate) {
              await expect(
                schema.isValid({
                  ...defaultFormValues,
                  [name]: value
                })
              ).resolves.toBeTruthy()
            } else {
              await expect(
                schema.validate({
                  ...defaultFormValues,
                  [name]: value
                })
              ).rejects.toThrow(new yup.ValidationError(message as string))
            }
          })
        )
      })
    })

    describe("relation validation", () => {
      const makeRelationConfigItem = (props = {}): [ConfigItem, string] => {
        const configItem = {
          ...repeatableConfigItem,
          fields: [
            makeWebsiteConfigField({ widget: WidgetVariant.Relation, ...props })
          ]
        }

        return [configItem, configItem.fields[0].name]
      }

      it("should validate for a required multiple relation field", () => {
        const [configItem, name] = makeRelationConfigItem({
          multiple: true,
          required: true
        })
        const schema = getContentSchema(configItem, {})
        expect(() =>
          schema.validateSync({
            ...defaultFormValues,
            [name]: {
              website: "UUUIIIIIIDIDIDIDID",
              content: null
            }
          })
        ).toThrow(
          new yup.ValidationError(`${name}.content is a required field.`)
        )
      })

      it("should validate for a required cross_site relation field", () => {
        const [configItem, name] = makeRelationConfigItem({
          cross_site: true,
          required:   true
        })
        const schema = getContentSchema(configItem, {})
        expect(() =>
          schema.validateSync({
            ...defaultFormValues,
            [name]: {
              website: "UUUIIIIIIDIDIDIDID",
              content: []
            }
          })
        ).toThrow(
          new yup.ValidationError(`${name}.content is a required field.`)
        )
      })

      it("should pass validation for valid multiple relation values", async () => {
        const [configItem, name] = makeRelationConfigItem({ multiple: true })
        const schema = getContentSchema(configItem, {})
        await Promise.all(
          [[], ["some value"], ["some value", "another value"]].map(
            async value => {
              await expect(
                schema.isValid({
                  ...defaultFormValues,
                  [name]: {
                    website: "ASDFASDF",
                    content: value
                  }
                })
              ).resolves.toBeTruthy()
            }
          )
        )
      })

      it("should validate a multiple relation field with max and min set", async () => {
        const [configItem, name] = makeRelationConfigItem({
          multiple: true,
          min:      1,
          max:      2
        })
        const schema = getContentSchema(configItem, {})

        await Promise.all(
          [
            [[], false, `${name} must have at least 1 entry.`],
            [["some value"], true, ""],
            [["some value", "another value"], true, ""],
            [
              ["some value", "another value", "yet another value"],
              false,
              `${name} may have at most 2 entries.`
            ]
          ].map(async ([value, shouldValidate, message]) => {
            if (shouldValidate) {
              await expect(
                schema.isValid({
                  ...defaultFormValues,
                  [name]: {
                    website: "UUID",
                    content: value
                  }
                })
              ).resolves.toBeTruthy()
            } else {
              await expect(
                schema.validate({
                  ...defaultFormValues,
                  [name]: {
                    website: "UUID",
                    content: value
                  }
                })
              ).rejects.toThrow(new yup.ValidationError(message as string))
            }
          })
        )
      })

      it("should validate a required non-multiple field", async () => {
        const [configItem, name] = makeRelationConfigItem({ required: true })
        const schema = getContentSchema(configItem, {})

        expect(() =>
          schema.validateSync({
            ...defaultFormValues,
            [name]: {
              website: "UUID",
              content: null
            }
          })
        ).toThrow(
          new yup.ValidationError(`${name}.content is a required field.`)
        )
        await expect(
          schema.isValid({
            ...defaultFormValues,
            [name]: {
              content: "selected value"
            }
          })
        ).resolves.toBeTruthy()
      })
    })

    describe("Object validation", () => {
      const makeObjectConfigItem = (props = {}): [ConfigItem, string] => {
        const configItem = {
          ...repeatableConfigItem,
          fields: [
            makeWebsiteConfigField({
              widget: WidgetVariant.Object,
              ...props,
              fields: [
                makeWebsiteConfigField({
                  widget:   WidgetVariant.String,
                  label:    "mystring",
                  required: true
                }),
                makeWebsiteConfigField({
                  widget:   WidgetVariant.Boolean,
                  label:    "myboolean",
                  required: true
                })
              ]
            })
          ]
        }

        return [configItem, configItem.fields[0].name]
      }

      it("should validate the sub-fields", async () => {
        const [configItem, name] = makeObjectConfigItem({ required: true })
        const schema = getContentSchema(configItem, {})

        await schema
          .validate({ ...defaultFormValues, [name]: {} }, { abortEarly: false })
          .catch(err => {
            expect(err.errors).toEqual([
              "mystring is a required field",
              "myboolean is a required field"
            ])
          })
        await expect(
          schema.isValid({
            ...defaultFormValues,
            [name]: {
              mystring:  "hey!",
              myboolean: false
            }
          })
        ).resolves.toBeTruthy()
      })

      it("should skip validation on sub-fields which don't have data to send", async () => {
        const [configItem, name] = makeObjectConfigItem({ required: true })
        const fieldIsVisibleStub = sandbox
          .stub(siteContentFuncs, "fieldIsVisible")
          .returns(false)
        const values = {}
        const schema = getContentSchema(configItem, values)

        await expect(
          schema.isValid({
            ...defaultFormValues,
            [name]: {
              mystring: null
            }
          })
        ).resolves.toBeTruthy()
        sinon.assert.calledWith(
          fieldIsVisibleStub,
          configItem.fields[0],
          values
        )
      })
    })
  })

  describe("Website collection validation", () => {
    it("should require a title", async () => {
      for (const titleVal of [undefined, null, ""]) {
        await WebsiteCollectionFormSchema.validate({ title: titleVal }).catch(
          err => {
            expect(err.errors[0]).toMatch("Title is a required field")
          }
        )
      }
      expect(
        WebsiteCollectionFormSchema.isValid({ title: "My Title" })
      ).toBeTruthy()
    })
  })
})
