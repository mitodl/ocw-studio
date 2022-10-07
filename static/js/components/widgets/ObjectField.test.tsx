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
const mockSiteContent = siteContent as jest.Mocked<typeof siteContent>

describe("ObjectField", () => {
  let render: any,
    field: ObjectConfigField,
    contentContext: WebsiteContent[],
    values: SiteFormValues,
    onChangeStub: any

  beforeEach(() => {
    field = makeWebsiteConfigField({
      widget: WidgetVariant.Object
    }) as ObjectConfigField

    mockSiteContent.fieldIsVisible.mockReturnValue(true)

    const otherContent = makeWebsiteContentDetail()
    contentContext = [otherContent]
    values = { some: "values" }
    onChangeStub = jest.fn()

    render = (props = {}) =>
      shallow(
        <ObjectField
          field={field}
          contentContext={contentContext}
          values={values}
          onChange={onChangeStub}
          {...props}
        />
      )
  })

  it("should render an Object field, by passing sub-fields to SiteContentField", () => {
    const wrapper = render()
    wrapper.find("SiteContentField").forEach((field: any) => {
      expect(field.prop("contentContext")).toStrictEqual(contentContext)
      expect(field.prop("onChange")).toStrictEqual(onChangeStub)
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
      mockSiteContent.fieldIsVisible.mockReturnValue(isVisible)
      const wrapper = render()
      expect(wrapper.find("SiteContentField")).toHaveLength(
        isVisible ? field.fields.length : 0
      )
      for (const innerField of field.fields) {
        expect(mockSiteContent.fieldIsVisible).toBeCalledWith(
          innerField,
          values
        )
      }
    })
  })
})
