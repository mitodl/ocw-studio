import * as yup from "yup"
import { getContentSchema } from "./validation"

import { makeWebsiteConfigField } from "../../util/factories/websites"

import { ConfigItem, WidgetVariant } from "../../types/websites"

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
          }
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

  describe("select validation", () => {
    const makeSelectConfigItem = (props = {}): [ConfigItem, string] => {
      const configItem = {
        ...partialConfigItem,
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
      const schema = getContentSchema(configItem)
      expect(() =>
        schema.validateSync({
          [name]: null
        })
      ).toThrow(new yup.ValidationError(`${name} is a required field.`))
    })

    it("should pass validation for valid multiple select values", async () => {
      const [configItem, name] = makeSelectConfigItem({ multiple: true })
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

    it("should validate a multiple select field with max and min set", async () => {
      const [configItem, name] = makeSelectConfigItem({
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

    it("should validate a required non-multiple select field", async () => {
      const [configItem, name] = makeSelectConfigItem({ required: true })
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
