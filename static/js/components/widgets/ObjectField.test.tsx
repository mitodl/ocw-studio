import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Formik, Form } from "formik"

import * as siteContent from "../../lib/site_content"
import ObjectField from "./ObjectField"
import {
  makeWebsiteConfigField,
  makeWebsiteContentDetail,
} from "../../util/factories/websites"

import {
  ObjectConfigField,
  WebsiteContent,
  WidgetVariant,
} from "../../types/websites"
import { SiteFormValues } from "../../types/forms"

jest.mock("../../lib/site_content", () => ({
  ...jest.requireActual("../../lib/site_content"),
  fieldIsVisible: jest.fn(),
}))

jest.mock("./SelectField", () => ({
  __esModule: true,
  default: () => <div>mock select</div>,
}))

const mockSiteContent = siteContent as jest.Mocked<typeof siteContent>

describe("ObjectField", () => {
  let field: ObjectConfigField,
    contentContext: WebsiteContent[],
    values: SiteFormValues,
    onChangeStub: jest.Mock

  beforeEach(() => {
    field = makeWebsiteConfigField({
      widget: WidgetVariant.Object,
    }) as ObjectConfigField

    mockSiteContent.fieldIsVisible.mockReturnValue(true)

    const otherContent = makeWebsiteContentDetail()
    contentContext = [otherContent]
    values = { some: "values" }
    onChangeStub = jest.fn()
  })

  const renderObjectField = (props = {}) =>
    render(
      <Formik initialValues={values} onSubmit={jest.fn()}>
        <Form>
          <ObjectField
            field={field}
            contentContext={contentContext}
            values={values}
            onChange={onChangeStub}
            {...props}
          />
        </Form>
      </Formik>,
    )

  it("should render an Object field, by passing sub-fields to SiteContentField", () => {
    renderObjectField()
    field.fields.forEach((innerField) => {
      expect(screen.getByText(innerField.label)).toBeInTheDocument()
    })
  })

  it("should collapse if it's a collapsed widget", () => {
    field.collapsed = true
    renderObjectField()
    field.fields.forEach((innerField) => {
      expect(screen.queryByText(innerField.label)).not.toBeInTheDocument()
    })
  })

  it("should allow expanding / collapsing", async () => {
    const user = userEvent.setup()
    renderObjectField()
    field.fields.forEach((innerField) => {
      expect(screen.getByText(innerField.label)).toBeInTheDocument()
    })
    await user.click(screen.getByText(field.label))
    field.fields.forEach((innerField) => {
      expect(screen.queryByText(innerField.label)).not.toBeInTheDocument()
    })
    await user.click(screen.getByText(field.label))
    field.fields.forEach((innerField) => {
      expect(screen.getByText(innerField.label)).toBeInTheDocument()
    })
  })

  //
  ;[true, false].forEach((isVisible) => {
    it(`should hide fields which are ${isVisible ? "" : "not "}visible`, () => {
      mockSiteContent.fieldIsVisible.mockReturnValue(isVisible)
      renderObjectField()
      field.fields.forEach((innerField) => {
        if (isVisible) {
          expect(screen.getByText(innerField.label)).toBeInTheDocument()
        } else {
          expect(screen.queryByText(innerField.label)).not.toBeInTheDocument()
        }
      })
      for (const innerField of field.fields) {
        expect(mockSiteContent.fieldIsVisible).toHaveBeenCalledWith(
          innerField,
          values,
        )
      }
    })
  })
})
