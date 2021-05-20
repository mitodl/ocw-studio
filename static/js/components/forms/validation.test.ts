import * as yup from "yup"
import { getContentSchema } from "./validation"

import { makeWebsiteConfigField } from "../../util/factories/websites"

import {
  ConfigItem,
  FileConfigField,
  MarkdownConfigField,
  StringConfigField,
  TextConfigField,
  WidgetVariant
} from "../../types/websites"

describe("form validation util", () => {
  const yupFileFieldSchema = yup.mixed()
  const partialConfigItem = {
    folder:   "content",
    label:    "Page",
    name:     "page",
    category: "Content"
  }
  const partialField = {
    name:  "myfield",
    label: "My Field"
  }
  let configItem: ConfigItem

  it("produces a validation schema for fields regardless of whether they're required or not", () => {
    configItem = {
      ...partialConfigItem,
      fields: [
        {
          ...partialField,
          widget: WidgetVariant.String
        }
      ]
    }
    const schema = getContentSchema(configItem)
    expect(schema.toString()).toStrictEqual(
      yup
        .object()
        .shape({
          [partialField.name]: yup
            .string()
            .label(partialField.label)
            .required()
        })
        .toString()
    )
  })

  //
  ;[
    [WidgetVariant.String, yup.string()],
    [WidgetVariant.Text, yup.string()],
    [WidgetVariant.Markdown, yup.string()],
    [WidgetVariant.File, yupFileFieldSchema]
  ].forEach(([widget, expectedYupField]) => {
    it(`produces the correct validation schema for a required '${widget}' field`, () => {
      configItem = {
        ...partialConfigItem,
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
      const schema = getContentSchema(configItem)
      expect(schema.toString()).toStrictEqual(
        yup
          .object()
          .shape({
            [partialField.name]: expectedYupField
              // @ts-ignore
              .label(partialField.label)
              .required()
          })
          .toString()
      )
    })
  })

  it("produces the correct validation schema for multiple fields", () => {
    configItem = {
      ...partialConfigItem,
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
    const schema = getContentSchema(configItem)
    // @ts-ignore
    expect(schema.fields.myfield.toString()).toStrictEqual(
      yup
        .string()
        .label("My Field")
        .required()
        .toString()
    )
    // @ts-ignore
    expect(schema.fields.myfield2.toString()).toStrictEqual(
      yup
        .string()
        .label("My Second Field")
        .required()
        .toString()
    )
  })

  //
  ;[WidgetVariant.Select, WidgetVariant.Relation].forEach(selectLikeVariant => {
    describe(`${selectLikeVariant} validation`, () => {
      const makeSelectLikeConfigItem = (props = {}): [ConfigItem, string] => {
        const configItem = {
          ...partialConfigItem,
          fields: [
            makeWebsiteConfigField({ widget: selectLikeVariant, ...props })
          ]
        }

        return [configItem, configItem.fields[0].name]
      }

      it(`should validate for a required multiple ${selectLikeVariant} field`, () => {
        const [configItem, name] = makeSelectLikeConfigItem({
          multiple: true,
          required: true
        })
        const schema = getContentSchema(configItem)
        expect(() =>
          schema.validateSync({
            [name]: null
          })
        ).toThrow(new yup.ValidationError(`${name} is a required field.`))
      })

      it(`should pass validation for valid multiple ${selectLikeVariant} values`, async () => {
        const [configItem, name] = makeSelectLikeConfigItem({ multiple: true })
        const schema = getContentSchema(configItem)
        await Promise.all(
          [[], ["some value"], ["some value", "another value"]].map(
            async value => {
              await expect(
                schema.isValid({
                  [name]: value
                })
              ).resolves.toBeTruthy()
            }
          )
        )
      })

      it(`should validate a multiple ${selectLikeVariant} field with max and min set`, async () => {
        const [configItem, name] = makeSelectLikeConfigItem({
          multiple: true,
          min:      1,
          max:      2
        })
        const schema = getContentSchema(configItem)

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
                  [name]: value
                })
              ).resolves.toBeTruthy()
            } else {
              await expect(
                schema.validate({
                  [name]: value
                })
              ).rejects.toThrow(new yup.ValidationError(message as string))
            }
          })
        )
      })

      it(`should validate a required non-multiple ${selectLikeVariant} field`, async () => {
        const [configItem, name] = makeSelectLikeConfigItem({ required: true })
        const schema = getContentSchema(configItem)

        expect(() =>
          schema.validateSync({
            [name]: ""
          })
        ).toThrow(new yup.ValidationError(`${name} is a required field`))
        await expect(
          schema.isValid({ [name]: "selected value" })
        ).resolves.toBeTruthy()
      })
    })
  })

  describe("Object validation", () => {
    const makeObjectConfigItem = (props = {}): [ConfigItem, string] => {
      const configItem = {
        ...partialConfigItem,
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
      const schema = getContentSchema(configItem)

      await schema
        .validate({ [name]: {} }, { abortEarly: false })
        .catch(err => {
          expect(err.errors).toEqual([
            "mystring is a required field",
            "myboolean is a required field"
          ])
        })
      await expect(
        schema.isValid({
          [name]: {
            mystring:  "hey!",
            myboolean: false
          }
        })
      ).resolves.toBeTruthy()
    })
  })
})
