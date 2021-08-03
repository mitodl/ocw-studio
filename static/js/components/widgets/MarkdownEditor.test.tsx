import React from "react"
import { shallow } from "enzyme"
import ClassicEditor from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"
import sinon, { SinonSandbox } from "sinon"

import MarkdownEditor from "./MarkdownEditor"
import {
  FullEditorConfig,
  MinimalEditorConfig
} from "../../lib/ckeditor/CKEditor"

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
          value
        })
        const ckWrapper = wrapper.find("CKEditor")
        expect(ckWrapper.prop("editor")).toBe(ClassicEditor)
        expect(ckWrapper.prop("config")).toBe(expectedComponent)
        expect(ckWrapper.prop("data")).toBe(expectedPropValue)
      })
    })
  })

  it("should pass attach down ato a ResourceEmbedField", () => {
    const wrapper = render({ attach: "resource" })
    expect(wrapper.find("ResourceEmbedField").prop("attach")).toBe("resource")
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
