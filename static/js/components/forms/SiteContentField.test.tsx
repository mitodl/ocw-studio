import React from "react"
import { shallow } from "enzyme"
import { flatten } from "ramda"
import sinon, { SinonSandbox, SinonStub } from "sinon"

import SiteContentField from "./SiteContentField"

import { componentFromWidget } from "../../lib/site_content"
import { makeWebsiteStarterConfig } from "../../util/factories/websites"
import { WidgetVariant } from "../../types/websites"

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
      const props = wrapper.find("Field").props()
      expect(props["as"]).toBe(componentFromWidget(field))
      expect(props["name"]).toBe(field.name)
      if (
        field.widget === WidgetVariant.File ||
        field.widget === WidgetVariant.Boolean
      ) {
        expect(props["setFieldValue"]).toBe(setFieldValueStub)
      }
      if (field.widget === WidgetVariant.Select) {
        expect(props["min"]).toBe(field.min)
        expect(props["max"]).toBe(field.max)
        expect(props["multiple"]).toBe(field.multiple)
        expect(props["options"]).toBe(field.options)
      }
    }
  })
})
