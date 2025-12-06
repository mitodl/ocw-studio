import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Formik, Form } from "formik"
import sinon, { SinonSandbox, SinonStub } from "sinon"

import SiteContentField from "./SiteContentField"
import { exampleSiteConfigFields } from "../../constants"
import WebsiteContext from "../../context/Website"

import { WebsiteContent, WidgetVariant } from "../../types/websites"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail,
} from "../../util/factories/websites"

jest.mock("../widgets/MarkdownEditor", () => {
  return function MockMarkdownEditor(props: { name: string }) {
    return <textarea data-testid="markdown-editor" name={props.name} />
  }
})

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
    const website = makeWebsiteDetail()

    const fieldsToTest = exampleSiteConfigFields.filter(
      (field) => field.widget !== WidgetVariant.Markdown,
    )

    for (const field of fieldsToTest) {
      const { unmount, container } = render(
        <WebsiteContext.Provider value={website}>
          <Formik initialValues={{ [field.name]: "" }} onSubmit={jest.fn()}>
            <Form>
              <SiteContentField
                field={field}
                contentContext={contentContext}
                onChange={onChangeStub}
              />
            </Form>
          </Formik>
        </WebsiteContext.Provider>,
      )

      expect(screen.getByText(field.label)).toBeInTheDocument()

      const formGroup = container.querySelector(".form-group")
      expect(formGroup).toBeInTheDocument()

      unmount()
    }
  })

  it("renders a Select widget with options", async () => {
    const website = makeWebsiteDetail()
    const user = userEvent.setup()

    const selectField = exampleSiteConfigFields.find(
      (field) => field.widget === WidgetVariant.Select && field.options,
    )

    if (!selectField) {
      return
    }

    render(
      <WebsiteContext.Provider value={website}>
        <Formik initialValues={{ [selectField.name]: "" }} onSubmit={jest.fn()}>
          <Form>
            <SiteContentField
              field={selectField}
              contentContext={contentContext}
              onChange={onChangeStub}
            />
          </Form>
        </Formik>
      </WebsiteContext.Provider>,
    )

    expect(screen.getByText(selectField.label)).toBeInTheDocument()

    const selectInput = screen.getByRole("textbox")
    await user.click(selectInput)

    if ("options" in selectField && selectField.options) {
      for (const option of selectField.options) {
        const optionLabel =
          typeof option === "string"
            ? option
            : (option as { label: string }).label
        expect(screen.getAllByText(optionLabel).length).toBeGreaterThanOrEqual(
          1,
        )
      }
    }
  })

  it("renders a Boolean widget with radio buttons", () => {
    const website = makeWebsiteDetail()

    const booleanField = exampleSiteConfigFields.find(
      (field) => field.widget === WidgetVariant.Boolean,
    )

    if (!booleanField) {
      return
    }

    render(
      <WebsiteContext.Provider value={website}>
        <Formik
          initialValues={{ [booleanField.name]: false }}
          onSubmit={jest.fn()}
        >
          <Form>
            <SiteContentField
              field={booleanField}
              contentContext={contentContext}
              onChange={onChangeStub}
            />
          </Form>
        </Formik>
      </WebsiteContext.Provider>,
    )

    expect(screen.getByText(booleanField.label)).toBeInTheDocument()
    expect(screen.getByRole("radio", { name: "True" })).toBeInTheDocument()
    expect(screen.getByRole("radio", { name: "False" })).toBeInTheDocument()
  })

  it("renders a String widget with text input", () => {
    const website = makeWebsiteDetail()

    const stringField = exampleSiteConfigFields.find(
      (field) => field.widget === WidgetVariant.String,
    )

    if (!stringField) {
      return
    }

    render(
      <WebsiteContext.Provider value={website}>
        <Formik initialValues={{ [stringField.name]: "" }} onSubmit={jest.fn()}>
          <Form>
            <SiteContentField
              field={stringField}
              contentContext={contentContext}
              onChange={onChangeStub}
            />
          </Form>
        </Formik>
      </WebsiteContext.Provider>,
    )

    expect(screen.getByText(stringField.label)).toBeInTheDocument()
    expect(screen.getByRole("textbox")).toBeInTheDocument()
  })

  it("calls onChange when user types in a String field", async () => {
    const website = makeWebsiteDetail()
    const user = userEvent.setup()

    const stringField = exampleSiteConfigFields.find(
      (field) => field.widget === WidgetVariant.String,
    )

    if (!stringField) {
      return
    }

    render(
      <WebsiteContext.Provider value={website}>
        <Formik initialValues={{ [stringField.name]: "" }} onSubmit={jest.fn()}>
          <Form>
            <SiteContentField
              field={stringField}
              contentContext={contentContext}
              onChange={onChangeStub}
            />
          </Form>
        </Formik>
      </WebsiteContext.Provider>,
    )

    const input = screen.getByRole("textbox")
    await user.type(input, "test")

    expect(onChangeStub.called).toBe(true)
  })

  it("renders a Markdown widget", () => {
    const website = makeWebsiteDetail()

    const markdownField = exampleSiteConfigFields.find(
      (field) => field.widget === WidgetVariant.Markdown,
    )

    if (!markdownField) {
      return
    }

    render(
      <WebsiteContext.Provider value={website}>
        <Formik
          initialValues={{ [markdownField.name]: "" }}
          onSubmit={jest.fn()}
        >
          <Form>
            <SiteContentField
              field={markdownField}
              contentContext={contentContext}
              onChange={onChangeStub}
            />
          </Form>
        </Formik>
      </WebsiteContext.Provider>,
    )

    expect(screen.getByText(markdownField.label)).toBeInTheDocument()
    expect(screen.getByTestId("markdown-editor")).toBeInTheDocument()
  })

  it("renders help text when provided", () => {
    const website = makeWebsiteDetail()

    const fieldWithHelp = exampleSiteConfigFields.find(
      (field) => field.help && field.widget !== WidgetVariant.Markdown,
    )

    if (!fieldWithHelp) {
      return
    }

    render(
      <WebsiteContext.Provider value={website}>
        <Formik
          initialValues={{ [fieldWithHelp.name]: "" }}
          onSubmit={jest.fn()}
        >
          <Form>
            <SiteContentField
              field={fieldWithHelp}
              contentContext={contentContext}
              onChange={onChangeStub}
            />
          </Form>
        </Formik>
      </WebsiteContext.Provider>,
    )

    expect(screen.getByText(fieldWithHelp.help!)).toBeInTheDocument()
  })
})
