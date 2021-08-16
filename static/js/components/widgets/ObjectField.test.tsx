import React from "react"
import { shallow } from "enzyme"

import * as siteContent from "../../lib/site_content"
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
import { SiteFormValues } from "../../types/forms"

jest.mock("../../lib/site_content")

describe("ObjectField", () => {
  let render: any,
    field: ObjectConfigField,
    contentContext: WebsiteContent[],
    values: SiteFormValues

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

    // @ts-ignore
    siteContent.fieldIsVisible.mockReturnValue(true)

    const otherContent = makeWebsiteContentDetail()
    contentContext = [otherContent]
    values = { some: "values" }

    render = (props = {}) =>
      shallow(
        <ObjectField
          field={field}
          contentContext={contentContext}
          values={values}
          {...props}
        />
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

  //
  ;[true, false].forEach(isVisible => {
    it(`should hide fields which are ${isVisible ? "" : "not "}visible`, () => {
      // @ts-ignore
      siteContent.fieldIsVisible.mockReturnValue(isVisible)
      const wrapper = render()
      expect(wrapper.find("SiteContentField")).toHaveLength(
        isVisible ? field.fields.length : 0
      )
      for (const innerField of field.fields) {
        expect(siteContent.fieldIsVisible).toBeCalledWith(innerField, values)
      }
    })
  })
})
