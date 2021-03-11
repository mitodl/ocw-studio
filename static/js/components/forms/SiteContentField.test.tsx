import React from "react"
import { shallow } from "enzyme"
import { flatten } from "ramda"
import sinon, { SinonSandbox, SinonStub } from "sinon"

import SiteContentField from "./SiteContentField"

import { componentFromWidget } from "../../lib/site_content"
import { makeWebsiteStarterConfig } from "../../util/factories/websites"

describe("SiteContentField", () => {
  let sandbox: SinonSandbox, setFieldValueStub: SinonStub

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    setFieldValueStub = sinon.stub()
  })

  afterEach(() => {
    sandbox.restore()
  })

  it("renders a form group for a config field", () => {
    const allFields = flatten(
      makeWebsiteStarterConfig().collections.map(item => item.fields)
    )

    for (const field of allFields) {
      const wrapper = shallow(
        <SiteContentField field={field} setFieldValue={setFieldValueStub} />
      )

      expect(wrapper.find("label").text()).toBe(field.label)
      expect(wrapper.find("Field").prop("as")).toBe(componentFromWidget(field))
      expect(wrapper.find("Field").prop("name")).toBe(field.name)
      expect(wrapper.find("Field").prop("setFieldValue")).toBe(
        field.widget === "file" ? setFieldValueStub : undefined
      )
    }
  })
})
