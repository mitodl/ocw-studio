import React from "react"
import { shallow } from "enzyme"

import ObjectField from "./ObjectField"
import { makeWebsiteConfigField } from "../../util/factories/websites"

import { ObjectConfigField, WidgetVariant } from "../../types/websites"

describe("ObjectField", () => {
  let setFieldValueStub: any, render: any, field: ObjectConfigField

  beforeEach(() => {
    setFieldValueStub = jest.fn()

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

    render = (props = {}) =>
      shallow(
        <ObjectField
          setFieldValue={setFieldValueStub}
          field={field}
          {...props}
        />
      )
  })

  it("should should render an Object field, by passing sub-fields to SiteContentField", () => {
    const wrapper = render()
    wrapper.find("SiteContentField").map((field: any) => {
      expect(field.prop("setFieldValue")).toEqual(setFieldValueStub)
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
