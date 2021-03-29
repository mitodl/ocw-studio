import * as yup from "yup"
import { getContentSchema } from "./validation"

import { ConfigItem } from "../../types/websites"

describe("form validation util", () => {
  const yupFileFieldSchema = yup.object().shape({
    name: yup.string().required()
  })
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
          widget: "string"
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
    ["string", yup.string()],
    ["text", yup.string()],
    ["markdown", yup.string()],
    ["file", yupFileFieldSchema]
  ].forEach(([widget, expectedYupField]) => {
    it(`produces the correct validation schema for a required '${widget}' field`, () => {
      configItem = {
        ...partialConfigItem,
        fields: [
          {
            ...partialField,
            widget:   widget.toString(),
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
          widget:   "string",
          required: true
        },
        {
          name:     "myfield2",
          label:    "My Second Field",
          widget:   "string",
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
})
