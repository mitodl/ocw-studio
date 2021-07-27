import React from "react"
import { shallow } from "enzyme"
import sinon, { SinonSandbox, SinonStub } from "sinon"

import SiteContentField from "./SiteContentField"
import { componentFromWidget } from "../../lib/site_content"
import { exampleSiteConfigFields } from "../../constants"

import { WebsiteContent, WidgetVariant } from "../../types/websites"
import { makeWebsiteContentDetail } from "../../util/factories/websites"

describe("SiteContentField", () => {
  let sandbox: SinonSandbox,
    setFieldValueStub: SinonStub,
    contentContext: WebsiteContent[]

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    setFieldValueStub = sandbox.stub()
    const content = makeWebsiteContentDetail()
    contentContext = [content]
  })

  afterEach(() => {
    sandbox.restore()
  })

  it("renders a form group for a config field", () => {
    for (const field of exampleSiteConfigFields) {
      const wrapper = shallow(
        <SiteContentField
          field={field}
          setFieldValue={setFieldValueStub}
          contentContext={contentContext}
        />
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
