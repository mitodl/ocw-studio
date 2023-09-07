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
    contentContext: WebsiteContent[],
    onChangeStub: SinonStub

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    const content = makeWebsiteContentDetail()
    contentContext = [content]
    onChangeStub = sandbox.stub()
  })

  afterEach(() => {
    sandbox.restore()
  })

  it("renders a form group for a config field", () => {
    for (const field of exampleSiteConfigFields) {
      const wrapper = shallow(
        <SiteContentField
          field={field}
          contentContext={contentContext}
          onChange={onChangeStub}
        />,
      )

      expect(wrapper.find("label").text()).toBe(field.label)
      const props = wrapper.find("Field").props()
      expect(props["as"]).toBe(componentFromWidget(field))
      expect(props["name"]).toBe(field.name)
      expect(props["onChange"]).toBe(onChangeStub)
      if (
        field.widget === WidgetVariant.Menu ||
        field.widget === WidgetVariant.Relation
      ) {
        expect(props["contentContext"]).toBe(contentContext)
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
