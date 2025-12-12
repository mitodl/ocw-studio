import { times } from "ramda"
import React from "react"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import SiteContentForm from "./SiteContentForm"
import {
  makeEditableConfigItem,
  makeWebsiteConfigField,
  makeWebsiteContentDetail,
  makeWebsiteDetail,
} from "../../util/factories/websites"
import { WebsiteContentModalState, WidgetVariant } from "../../types/websites"
import { createModalState } from "../../types/modal_state"

import IntegrationTestHelper from "../../testing_utils/IntegrationTestHelper"
import { resourceFields } from "../../util/factories/websites"
import * as domUtil from "../../util/dom"

// ckeditor is not working properly in tests, but we don't need to test it here so just mock it away
function mocko() {
  return <div>mock</div>
}

jest.mock("../widgets/MarkdownEditor", () => ({
  __esModule: true,
  default: mocko,
}))

jest.mock("../widgets/SelectField", () => ({
  __esModule: true,
  default: mocko,
}))

jest.mock("../../util/dom")

const { scrollToElement } = domUtil as jest.Mocked<typeof domUtil>

function setupData() {
  const content = makeWebsiteContentDetail()
  content.content_context = times(() => makeWebsiteContentDetail(), 3)
  const configItem = makeEditableConfigItem(content.type)
  const website = makeWebsiteDetail()
  const onSubmit = jest.fn()
  const setDirty = jest.fn()
  const editorState: WebsiteContentModalState = createModalState("adding")

  return {
    content,
    configItem,
    onSubmit,
    setDirty,
    editorState,
    website,
  }
}

const EDITOR_STATES: WebsiteContentModalState[] = [
  createModalState("adding"),
  createModalState("editing", "id"),
]

type ESBoolMatrix = [WebsiteContentModalState, boolean][]

const EDITOR_STATE_BOOLEAN_MATRIX = EDITOR_STATES.map((editorState) => [
  [editorState, true],
  [editorState, false],
]).flat() as ESBoolMatrix

describe("SiteContentForm", () => {
  let helper: IntegrationTestHelper

  beforeEach(() => {
    helper = new IntegrationTestHelper()
  })

  test.each(EDITOR_STATE_BOOLEAN_MATRIX)(
    "the SiteContentField should set the dirty flag when touched when %p and isObjectField is %p",
    async (editorState, isObjectField) => {
      const user = userEvent.setup()
      const data = setupData()
      const configItem = makeEditableConfigItem()
      const configField = makeWebsiteConfigField({
        widget: isObjectField ? WidgetVariant.Object : WidgetVariant.String,
      })
      configItem.fields = [configField]

      helper.renderWithWebsite(
        <SiteContentForm
          {...data}
          configItem={configItem}
          editorState={editorState}
        />,
        data.website,
      )

      const fieldName =
        configField.widget === WidgetVariant.Object
          ? configField.fields[0].name
          : configItem.fields[0].name

      const input = screen.getByRole("textbox", {
        name: new RegExp(fieldName, "i"),
      })
      await user.type(input, "test")

      await waitFor(() => {
        expect(data.setDirty).toHaveBeenCalledWith(true)
      })
    },
  )

  test.each(EDITOR_STATES)(
    "Video metadata source only added on creation",
    async (editorState) => {
      const user = userEvent.setup()
      const data = setupData()
      data.content.type = "resource"
      data.content.metadata = { resourcetype: "Video" }
      const configItem = makeEditableConfigItem("resource")
      configItem.fields = resourceFields

      helper.renderWithWebsite(
        <SiteContentForm
          {...data}
          content={data.content}
          configItem={configItem}
          editorState={editorState}
        />,
        data.website,
      )

      const youtubeInput = screen.getByRole("textbox", { name: /youtube id/i })
      await user.type(youtubeInput, "abcdefghij")

      await user.click(screen.getByRole("button", { name: /save/i }))

      await waitFor(() => {
        expect(data.onSubmit).toHaveBeenCalledTimes(1)
      })

      const expectedVideoMetadata: any = {
        youtube_id: "abcdefghij",
      }

      if (editorState.adding()) {
        expectedVideoMetadata.source = "youtube"
      }

      expect(data.onSubmit.mock.calls[0][0].video_metadata).toEqual(
        expectedVideoMetadata,
      )
    },
  )

  test.each(EDITOR_STATES)("SiteContentForm renders", (editorState) => {
    const data = setupData()

    helper.renderWithWebsite(
      <SiteContentForm {...data} editorState={editorState} />,
      data.website,
    )

    data.configItem.fields.forEach((field) => {
      expect(screen.getByText(field.label)).toBeInTheDocument()
    })
  })

  test("SiteContentForm displays a status", async () => {
    const user = userEvent.setup()
    const data = setupData()
    data.onSubmit.mockImplementation((_values, { setStatus }) => {
      setStatus("testing status")
    })

    helper.renderWithWebsite(<SiteContentForm {...data} />, data.website)

    const titleInput = screen.getByRole("textbox", { name: /title/i })
    await user.type(titleInput, "Test Title")

    await user.click(screen.getByRole("button", { name: /save/i }))

    await waitFor(() => {
      expect(screen.getByText("testing status")).toBeInTheDocument()
    })
  })

  test.each([true, false])(
    "SiteContentForm shows a button with disabled=%p",
    async (isSubmitting) => {
      const data = setupData()
      if (isSubmitting) {
        data.onSubmit.mockImplementation(
          () =>
            new Promise(() => {
              // Never resolves to keep form in submitting state
            }),
        )
      }

      helper.renderWithWebsite(<SiteContentForm {...data} />, data.website)

      const button = screen.getByRole("button", { name: /save/i })

      if (isSubmitting) {
        const user = userEvent.setup()
        const titleInput = screen.getByRole("textbox", { name: /title/i })
        await user.type(titleInput, "Test")
        await user.click(button)

        await waitFor(() => {
          expect(button).toBeDisabled()
        })
      } else {
        expect(button).not.toBeDisabled()
      }
    },
  )

  test("should use an ObjectField when dealing with an Object", () => {
    const data = setupData()
    const configItem = makeEditableConfigItem()
    const configField = makeWebsiteConfigField({
      widget: WidgetVariant.Object,
    })
    configItem.fields = [configField]

    helper.renderWithWebsite(
      <SiteContentForm {...data} configItem={configItem} />,
      data.website,
    )
    ;(configField as { fields: Array<{ label: string }> }).fields.forEach(
      (nestedField) => {
        expect(screen.getByText(nestedField.label)).toBeInTheDocument()
      },
    )
  })

  test.each`
    isGdriveEnabled | isResource | willRenderAsFileInput
    ${true}         | ${true}    | ${false}
    ${false}        | ${true}    | ${true}
    ${true}         | ${false}   | ${true}
    ${false}        | ${false}   | ${true}
  `(
    "file field render:$willRenderAsFileInput when gdrive:$isGdriveEnabled and resource:$isResource",
    ({ isGdriveEnabled, isResource, willRenderAsFileInput }) => {
      const data = setupData()
      SETTINGS.gdrive_enabled = isGdriveEnabled
      data.content.type = isResource ? "resource" : "page"
      const configItem = makeEditableConfigItem(data.content.type)
      const field = makeWebsiteConfigField({ widget: WidgetVariant.File })
      configItem.fields = [field]

      helper.renderWithWebsite(
        <SiteContentForm
          {...data}
          configItem={configItem}
          editorState={createModalState("editing", "id")}
        />,
        data.website,
      )

      if (willRenderAsFileInput) {
        expect(screen.getByText(field.label)).toBeInTheDocument()
        expect(document.querySelector('input[type="file"]')).toBeInTheDocument()
      } else {
        expect(screen.getByText(field.label)).toBeInTheDocument()
        expect(
          document.querySelector('input[type="file"]'),
        ).not.toBeInTheDocument()
      }
    },
  )

  test.each`
    isGdriveEnabled | isResource | willRenderAsLabel
    ${true}         | ${true}    | ${true}
    ${false}        | ${true}    | ${false}
    ${true}         | ${false}   | ${false}
    ${false}        | ${false}   | ${false}
  `(
    "filename label field render:$willRenderAsLabel when gdrive:$isGdriveEnabled and resource:$isResource",
    ({ isGdriveEnabled, isResource, willRenderAsLabel }) => {
      const data = setupData()
      SETTINGS.gdrive_enabled = isGdriveEnabled
      data.content.type = isResource ? "resource" : "page"
      const configItem = makeEditableConfigItem(data.content.type)
      const field = makeWebsiteConfigField({
        widget: WidgetVariant.File,
        name: "file",
        label: "File",
      })
      configItem.fields = [field]
      data.content.file = "courses/file.pdf"

      helper.renderWithWebsite(
        <SiteContentForm
          {...data}
          configItem={configItem}
          editorState={createModalState("editing", "id")}
        />,
        data.website,
      )

      if (willRenderAsLabel) {
        expect(
          document.querySelector('input[type="file"]'),
        ).not.toBeInTheDocument()
        const readonlyInput = document.querySelector(
          "input[readonly]",
        ) as HTMLInputElement
        expect(readonlyInput).toBeInTheDocument()
        expect(readonlyInput.value).toBe("file.pdf")
      } else {
        expect(
          document.querySelector("input[readonly]"),
        ).not.toBeInTheDocument()
      }
    },
  )

  test("SiteContentField creates new values", () => {
    const data = setupData()
    data.configItem.fields = [
      makeWebsiteConfigField({
        widget: WidgetVariant.String,
        name: "test-name",
        label: "Test Name",
        default: "test-default",
      }),
    ]

    helper.renderWithWebsite(<SiteContentForm {...data} />, data.website)

    expect(screen.getByRole("textbox", { name: /test name/i })).toHaveValue(
      "test-default",
    )
  })

  test("SiteContentField uses existing values when editing", () => {
    const data = setupData()
    data.content.metadata = { title: "Existing Title" }
    data.content.title = "Existing Title"
    data.configItem.fields = [
      makeWebsiteConfigField({
        widget: WidgetVariant.String,
        name: "title",
        label: "Title",
      }),
    ]

    helper.renderWithWebsite(
      <SiteContentForm
        {...data}
        editorState={createModalState("editing", "id")}
      />,
      data.website,
    )

    expect(screen.getByRole("textbox", { name: /title/i })).toHaveValue(
      "Existing Title",
    )
  })

  test("renders Page URL field for page content", () => {
    const data = setupData()
    data.content.type = "page"
    data.content.filename = "test-page"
    const configItem = makeEditableConfigItem("page")
    configItem.fields = [
      makeWebsiteConfigField({
        name: "title",
        label: "Title",
        widget: WidgetVariant.String,
      }),
    ]

    helper.renderWithWebsite(
      <SiteContentForm
        {...data}
        configItem={configItem}
        editorState={createModalState("editing", "id")}
      />,
      data.website,
    )

    expect(screen.getByDisplayValue("/pages/test-page")).toBeInTheDocument()
  })

  test("scrolls to .form-error field on validation error", async () => {
    const user = userEvent.setup()
    const data = setupData()
    data.configItem.fields = [
      makeWebsiteConfigField({
        widget: WidgetVariant.String,
        name: "title",
        label: "Title",
        required: true,
      }),
    ]

    helper.renderWithWebsite(<SiteContentForm {...data} />, data.website)

    await user.click(screen.getByRole("button", { name: /save/i }))

    await waitFor(() => {
      expect(scrollToElement).toHaveBeenCalledTimes(1)
    })
    expect(scrollToElement).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      ".form-error",
    )
  })
})
