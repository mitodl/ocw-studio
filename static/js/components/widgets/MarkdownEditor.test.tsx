import React from "react"
import { shallow } from "enzyme"
import ClassicEditor from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"
import { CKEditor } from "@ckeditor/ckeditor5-react"
import sinon, { SinonSandbox } from "sinon"
import { omit } from "ramda"

import MarkdownEditor from "./MarkdownEditor"
import {
  FullEditorConfig,
  MinimalEditorConfig,
  insertResourceLink
} from "../../lib/ckeditor/CKEditor"
import {
  ADD_RESOURCE_EMBED,
  ADD_RESOURCE_LINK,
  CKEDITOR_RESOURCE_UTILS,
  RESOURCE_EMBED,
  RESOURCE_LINK
} from "../../lib/ckeditor/plugins/constants"
import ResourcePickerDialog from "../../components/widgets/ResourcePickerDialog"
import { getMockEditor } from "../../test_util"

jest.mock("../../lib/ckeditor/CKEditor", () => {
  const originalModule = jest.requireActual("../../lib/ckeditor/CKEditor")

  return {
    __esModule:         true,
    ...originalModule,
    insertResourceLink: jest.fn()
  }
})

jest.mock("@ckeditor/ckeditor5-inspector")

jest.mock("@ckeditor/ckeditor5-react", () => ({
  CKEditor: () => <div />
}))

const render = (props = {}) =>
  shallow(<MarkdownEditor link={[]} embed={[]} {...props} />)

describe("MarkdownEditor", () => {
  let sandbox: SinonSandbox

  beforeEach(() => {
    sandbox = sinon.createSandbox()
  })

  afterEach(() => {
    sandbox.restore()
  })

  //
  ;[
    [true, MinimalEditorConfig],
    [false, FullEditorConfig]
  ].forEach(([minimal, expectedComponent]) => {
    [
      ["value", "value"],
      [null, ""]
    ].forEach(([value, expectedPropValue]) => {
      it(`renders the ${
        minimal ? "minimal " : "full"
      } MarkdownEditor with value=${String(value)}`, () => {
        const wrapper = render({
          minimal,
          value,
          embed: ["resource"],
          link:  ["page"]
        })
        const ckWrapper = wrapper.find("CKEditor")
        expect(ckWrapper.prop("editor")).toBe(ClassicEditor)
        expect(
          omit([CKEDITOR_RESOURCE_UTILS], ckWrapper.prop("config"))
        ).toEqual(expectedComponent)
        expect(ckWrapper.prop("data")).toBe(expectedPropValue)
      })
    })
  })

  it("should delegate to addResourceLink when inserting a link", async () => {
    const wrapper = render({ link: ["page"] })
    const editorComponent = wrapper.find<{ onReady:(e: unknown) => void }>(
      CKEditor
    )
    const editor = getMockEditor()
    editorComponent.prop("onReady")(editor)
    const picker = wrapper.find(ResourcePickerDialog)
    picker.prop("insertEmbed")("best-uuid-ever", "some title", "resourceLink")
    expect(insertResourceLink).toHaveBeenCalledWith(
      editor,
      "best-uuid-ever",
      "some title"
    )
  })

  it.each([
    { link: [], embed: [], shouldExist: false },
    { link: ["page"], embed: [], shouldExist: true },
    { link: [], embed: ["resource"], shouldExist: true },
    { link: ["page"], embed: ["resource"], shouldExist: true }
  ])(
    "should render ResourcePickerDialog iff link or embed are nonempty",
    ({ link, embed, shouldExist }) => {
      const wrapper = render({ link, embed })
      const resourcePicker = wrapper.find("ResourcePickerDialog")
      expect(resourcePicker.exists()).toBe(shouldExist)
    }
  )

  it("should render resources with using EmbeddedResource", () => {
    const wrapper = render()
    const editor = wrapper.find("CKEditor").prop("config")
    const el = document.createElement("div")
    // @ts-expect-error CKEditor types are a work in progress
    editor[CKEDITOR_RESOURCE_UTILS].renderResource("resource-uuid", el)
    wrapper.update()
    expect(
      wrapper
        .find("EmbeddedResource")
        .at(0)
        .prop("uuid")
    ).toEqual("resource-uuid")
  })

  it.each([
    { embed: [], hasTool: false },
    { embed: ["resource"], hasTool: true }
  ])(
    'should show "add resource" iff embed is nonempty. Case: $embed',
    ({ embed, hasTool }) => {
      const wrapper = render({ embed })
      const editorConfig = wrapper.find("CKEditor").prop("config")
      // @ts-expect-error CKEditor types are a work in progress
      expect(editorConfig.toolbar.items.includes(ADD_RESOURCE_EMBED)).toBe(
        hasTool
      )
    }
  )

  it.each([
    { link: [], hasTool: false },
    { link: ["page"], hasTool: true }
  ])(
    'should show "add link" iff link is nonempty. Case: $link',
    ({ link, hasTool }) => {
      const wrapper = render({ link })
      const editorConfig = wrapper.find("CKEditor").prop("config")
      // @ts-expect-error CKEditor types are a work in progress
      expect(editorConfig.toolbar.items.includes(ADD_RESOURCE_LINK)).toBe(
        hasTool
      )
    }
  )

  //
  ;[RESOURCE_EMBED, RESOURCE_LINK].forEach(resourceNodeType => {
    it(`should open the resource picker for ${resourceNodeType}`, () => {
      const wrapper = render({
        embed: ["resource"],
        link:  ["resource", "page"]
      })
      const editor = wrapper.find("CKEditor").prop("config")
      // @ts-expect-error CKEditor types are a work in progress
      editor[CKEDITOR_RESOURCE_UTILS].openResourcePicker(resourceNodeType)
      wrapper.update()
      expect(
        wrapper
          .find("ResourcePickerDialog")
          .at(0)
          .prop("mode")
      ).toBe(resourceNodeType)
    })
  })

  //
  ;[
    ["name", "name"],
    [null, ""]
  ].forEach(([name, expectedPropName]) => {
    [true, false].forEach(hasOnChange => {
      it(`triggers ${
        hasOnChange ? "with" : "without"
      } an onChange when name=${String(name)}`, () => {
        const onChangeStub = sandbox.stub()
        const wrapper = render({
          name,
          onChange: hasOnChange ? onChangeStub : null
        })
        const ckWrapper = wrapper.find("CKEditor")

        const data = "some data"
        const editor = { getData: sandbox.stub().returns(data) }
        // @ts-expect-error CKEditor types are a work in progress
        ckWrapper.prop("onChange")(null, editor)
        if (hasOnChange) {
          sinon.assert.calledOnceWithExactly(onChangeStub, {
            target: { value: data, name: expectedPropName }
          })
        } else {
          expect(onChangeStub.called).toBe(false)
        }
      })
    })
  })
})
