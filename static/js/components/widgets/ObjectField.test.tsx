import React from "react"
import { shallow } from "enzyme"

import ObjectField from "./ObjectField"
import {
  makeWebsiteConfigField,
  makeWebsiteContentDetail
} from "../../util/factories/websites"

import {
  ObjectConfigField,
  WebsiteContent,
  WidgetVariant
} from "../../types/websites"

describe("ObjectField", () => {
  let render: any, field: ObjectConfigField, contentContext: WebsiteContent[]

  beforeEach(() => {
    field = makeWebsiteConfigField({
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
    }) as ObjectConfigField

    const otherContent = makeWebsiteContentDetail()
    contentContext = [otherContent]

    render = (props = {}) =>
      shallow(
        <ObjectField field={field} contentContext={contentContext} {...props} />
      )
  })

  it("should render an Object field, by passing sub-fields to SiteContentField", () => {
    const wrapper = render()
    wrapper.find("SiteContentField").forEach((field: any) => {
      expect(field.prop("contentContext")).toStrictEqual(contentContext)
    })
    expect(
      wrapper.find("SiteContentField").map((field: any) => field.prop("field"))
    ).toEqual(field.fields)
  })

  it("should collapse if it's a collapsed widget", () => {
    field.collapsed = true
    const wrapper = render()
    expect(wrapper.find("SiteContentField").exists()).toBeFalsy()
  })

  it("should allow expanding / collapsing", () => {
    const wrapper = render()
    expect(wrapper.find("SiteContentField").exists()).toBeTruthy()
    wrapper.find(".object-field-label").simulate("click", new Event("click"))
    expect(wrapper.find("SiteContentField").exists()).toBeFalsy()
    wrapper.find(".object-field-label").simulate("click", new Event("click"))
    expect(wrapper.find("SiteContentField").exists()).toBeTruthy()
  })
})
