import { times } from "ramda"
import React from "react"
import { Formik } from "formik"
import { mount } from "enzyme"
import { act } from "react-dom/test-utils"

import SiteContentForm, {
  FormFields,
  InnerFormProps,
  FormProps
} from "./SiteContentForm"
import {
  makeEditableConfigItem,
  makeWebsiteConfigField,
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../../util/factories/websites"
import * as siteContent from "../../lib/site_content"
import { WebsiteContentModalState, WidgetVariant } from "../../types/websites"
import { createModalState } from "../../types/modal_state"
import * as domUtil from "../../util/dom"
import ObjectField from "../widgets/ObjectField"

import * as Website from "../../context/Website"
import Label from "../widgets/Label"
const { useWebsite: mockUseWebsite } = Website as jest.Mocked<typeof Website>

// ckeditor is not working properly in tests, but we don't need to test it here so just mock it away
function mocko() {
  return <div>mock</div>
}

jest.mock("../widgets/MarkdownEditor", () => ({
  __esModule: true,
  default:    mocko
}))

jest.mock("../widgets/SelectField", () => ({
  __esModule: true,
  default:    mocko
}))

jest.mock("../../context/Website")
jest.mock("../../util/dom")

const { contentInitialValues, renameNestedFields } = siteContent as jest.Mocked<
  typeof siteContent
>

const { scrollToElement } = domUtil as jest.Mocked<typeof domUtil>

function setupData() {
  const content = makeWebsiteContentDetail()
  content.content_context = times(() => makeWebsiteContentDetail(), 3)
  const configItem = makeEditableConfigItem(content.type)
  const website = makeWebsiteDetail()
  mockUseWebsite.mockReturnValue(website)
  const onSubmit = jest.fn()
  const setDirty = jest.fn()
  const editorState: WebsiteContentModalState = createModalState("adding")

  return {
    content,
    configItem,
    onSubmit,
    setDirty,
    editorState,
    website
  }
}

function setup(props: Partial<FormProps> = {}) {
  const data = setupData()

  const form = mount(<SiteContentForm {...data} {...props} />)

  return {
    form,
    ...data
  }
}

/**
 * A separate setup function for inserting specific test values
 * into the inner form component
 */
function setupInnerForm(props: Partial<InnerFormProps> = {}) {
  const data = setupData()
  const validate = jest.fn()

  const form = mount(
    <Formik
      onSubmit={data.onSubmit}
      validate={validate}
      initialValues={props.values ?? {}}
      enableReinitialize={true}
    >
      {formikProps => (
        <FormFields validate={validate} {...formikProps} {...data} {...props} />
      )}
    </Formik>
  )

  return { form, ...data }
}

const EDITOR_STATES: WebsiteContentModalState[] = [
  createModalState("adding"),
  createModalState("editing", "id")
]

type ESBoolMatrix = [WebsiteContentModalState, boolean][]

const EDITOR_STATE_BOOLEAN_MATRIX = EDITOR_STATES.map(editorState => [
  [editorState, true],
  [editorState, false]
]).flat() as ESBoolMatrix

test.each(EDITOR_STATE_BOOLEAN_MATRIX)(
  "the SiteContentField should set the dirty flag when touched when %p and isObjectField is %p",
  async (editorState, isObjectField) => {
    const configItem = makeEditableConfigItem()
    const configField = makeWebsiteConfigField({
      widget: isObjectField ? WidgetVariant.Object : WidgetVariant.String
    })
    configItem.fields = [configField]
    const { form, setDirty } = setup({
      configItem,
      editorState
    })

    const fieldName =
      configField.widget === WidgetVariant.Object ?
        configField.fields[0].name :
        configItem.fields[0].name

    await act(async () => {
      form
        .find("Field")
        .at(0)
        .simulate("change", {
          target: {
            name:  fieldName,
            value: "test"
          }
        })
      form.update()
    })
    expect(setDirty).toHaveBeenCalledWith(true)
  }
)

test.each(EDITOR_STATES)("SiteContentForm renders", editorState => {
  const { form, configItem, content } = setup({ editorState })

  configItem.fields.forEach((field, idx) => {
    const fieldWrapper = form.find("SiteContentField").at(idx)
    expect(fieldWrapper.prop("field")).toBe(field)
    expect(fieldWrapper.prop("contentContext")).toBe(content.content_context)
  })
})

test("SiteContentForm displays a status", () => {
  const status = "testing status"
  const { form } = setupInnerForm({ status })
  expect(form.find(".form-error").text()).toBe(status)
})

test.each([true, false])(
  "SiteContentForm shows a button with disabled=%p",
  isSubmitting => {
    const { form } = setupInnerForm({ isSubmitting })
    expect(form.find("button[type='submit']").prop("disabled")).toBe(
      isSubmitting
    )
  }
)

test("it should use an ObjectField when dealing with an Object", () => {
  const configItem = makeEditableConfigItem()
  const configField = makeWebsiteConfigField({
    widget: WidgetVariant.Object
  })
  configItem.fields = [configField]
  const { form } = setup({
    configItem
  })
  const objectField = form.find(ObjectField)
  expect(objectField.exists()).toBeTruthy()
  const renamedField = renameNestedFields([configField])[0]
  expect(objectField.prop("field")).toEqual(renamedField)
})

test("it scrolls to .form-error field", async () => {
  const data = setupData()
  data.configItem = makeEditableConfigItem(data.content.type)
  data.configItem.fields.forEach(field => {
    field.required = true
  })

  expect(data.configItem.fields.map(f => f.name)).toEqual([
    "title",
    "description",
    "body"
  ])

  const { form } = setupInnerForm({
    values:   { title: "meow" },
    validate: jest.fn().mockResolvedValue({
      title: "NO"
    })
  })

  await act(async () => {
    await form.find("form").simulate("submit")
  })

  const formElement = form.find("form").getDOMNode()
  expect(scrollToElement).toHaveBeenCalledTimes(1)
  expect(scrollToElement).toHaveBeenCalledWith(formElement, ".form-error")
})

test.each`
  isGdriveEnabled | isResource | willRender
  ${true}         | ${true}    | ${false}
  ${false}        | ${true}    | ${true}
  ${true}         | ${false}   | ${true}
  ${false}        | ${false}   | ${true}
`(
  "file field render:$willRender when gdrive:$isGdriveEnabled and resource:$isResource",
  ({ isGdriveEnabled, isResource, willRender }) => {
    const data = setupData()
    SETTINGS.gdrive_enabled = isGdriveEnabled
    data.content.type = isResource ? "resource" : "page"
    const configItem = makeEditableConfigItem(data.content.type)
    const field = makeWebsiteConfigField({ widget: WidgetVariant.File })
    configItem.fields = [field]
    const values = { [field.name]: "courses/file.pdf" }
    const { form } = setupInnerForm({
      ...data,
      configItem,
      values
    })
    expect(form.find("SiteContentField").exists()).toBe(willRender)
  }
)

test.each`
  isGdriveEnabled | isResource | willRender | filename
  ${true}         | ${true}    | ${true}    | ${"courses/file.pdf"}
  ${false}        | ${true}    | ${false}   | ${null}
  ${true}         | ${false}   | ${false}   | ${null}
  ${false}        | ${false}   | ${false}   | ${null}
`(
  "filename label field render:$willRender with filename:$filename when gdrive:$isGdriveEnabled and resource:$isResource",
  ({ isGdriveEnabled, isResource, willRender, filename }) => {
    const data = setupData()
    SETTINGS.gdrive_enabled = isGdriveEnabled
    data.content.type = isResource ? "resource" : "page"
    const configItem = makeEditableConfigItem(data.content.type)
    const field = makeWebsiteConfigField({ widget: WidgetVariant.File })
    configItem.fields = [field]
    const values = { [field.name]: "courses/file.pdf" }
    const { form } = setupInnerForm({
      ...data,
      configItem,
      values
    })
    expect(form.find(Label).exists()).toBe(willRender)
    if (willRender) {
      expect(form.find(Label).prop("value")).toBe(filename)
    }
  }
)

test("SiteContentField creates new values", () => {
  const data = setupData()
  data.configItem.fields = [
    makeWebsiteConfigField({
      widget:  WidgetVariant.String,
      name:    "test-name",
      default: "test-default"
    })
  ]
  const { form } = setup(data)
  expect(form.find(FormFields).prop("values")).toEqual({
    "test-name": "test-default"
  })
})

test("SiteContentField uses existing values when editing", () => {
  const data = setupData()
  const { form } = setup({
    ...data,
    editorState: createModalState("editing", "id")
  })
  expect(form.find(FormFields).prop("values")).toEqual(
    contentInitialValues(data.content, data.configItem.fields, data.website)
  )
})
