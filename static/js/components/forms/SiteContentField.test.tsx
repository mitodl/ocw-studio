import React from "react"
import { shallow } from "enzyme"
import { flatten } from "ramda"

import SiteContentField from "./SiteContentField"

import { componentFromWidget } from "../../lib/site_content"
import { makeWebsiteStarterConfig } from "../../util/factories/websites"

describe("SiteContentField", () => {
  it("renders a form group for a config field", () => {
    const allFields = flatten(
      makeWebsiteStarterConfig().collections.map(item => item.fields)
    )

    for (const field of allFields) {
      const wrapper = shallow(<SiteContentField field={field} />)

      expect(wrapper.find("label").text()).toBe(field.label)
      expect(wrapper.find("Field").prop("as")).toBe(componentFromWidget(field))
      expect(wrapper.find("Field").prop("name")).toBe(field.name)
    }
  })
})
