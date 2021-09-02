import React from "react"
import { shallow } from "enzyme"
import ClassicEditor from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"
import sinon, { SinonSandbox } from "sinon"
import { omit } from "ramda"

import MarkdownEditor from "./MarkdownEditor"
import {
  FullEditorConfig,
  MinimalEditorConfig
} from "../../lib/ckeditor/CKEditor"
import {
  ADD_RESOURCE,
  CKEDITOR_RESOURCE_UTILS,
  RESOURCE_EMBED,
  RESOURCE_LINK
} from "../../lib/ckeditor/plugins/constants"

jest.mock("@ckeditor/ckeditor5-react", () => ({
  CKEditor: () => <div />
}))

const render = (props = {}) => shallow(<MarkdownEditor {...props} />)

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
          attach: "attach"
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

  it("should pass attach down to a ResourceEmbedField", () => {
    const wrapper = render({ attach: "resource" })
    expect(wrapper.find("ResourcePickerDialog").prop("attach")).toBe("resource")
  })

  //
  ;[
    [RESOURCE_EMBED, "EmbeddedResource"],
    [RESOURCE_LINK, "ResourceLink"]
  ].forEach(([embedType, componentDisplayName]) => {
    it(`should render resources with ${embedType} using ${componentDisplayName}`, () => {
      const wrapper = render()
      const editor = wrapper.find("CKEditor").prop("config")
      const el = document.createElement("div")
      // @ts-ignore
      editor[CKEDITOR_RESOURCE_UTILS].renderResource(
        "resource-uuid",
        el,
        embedType
      )
      wrapper.update()
      expect(
        wrapper
          .find(componentDisplayName)
          .at(0)
          .prop("uuid")
      ).toEqual("resource-uuid")
    })
  })

  //
  ;[true, false].forEach(hasAttach => {
    it(`${
      hasAttach ? "should" : "shouldn't"
    } have an add resource button since attach ${
      hasAttach ? "was" : "wasn't"
    } set`, () => {
      const wrapper = render(hasAttach ? { attach: "resource" } : {})
      const editorConfig = wrapper.find("CKEditor").prop("config")
      // @ts-ignore
      expect(editorConfig.toolbar.items.includes(ADD_RESOURCE)).toBe(hasAttach)
    })
  })

  it("should open the resource picker", () => {
    const wrapper = render({ attach: "resource" })
    const editor = wrapper.find("CKEditor").prop("config")
    // @ts-ignore
    editor[CKEDITOR_RESOURCE_UTILS].openResourcePicker()
    wrapper.update()
    expect(
      wrapper
        .find("ResourcePickerDialog")
        .at(0)
        .prop("open")
    ).toBeTruthy()
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
        // @ts-ignore
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
