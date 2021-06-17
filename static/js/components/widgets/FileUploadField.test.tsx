import React from "react"
import { shallow } from "enzyme"
import sinon, { SinonSandbox, SinonStub } from "sinon"

import FileUploadField from "./FileUploadField"

describe("FileUploadField", () => {
  let sandbox: SinonSandbox, setFieldValueStub: SinonStub
  const mockFile = new File([new ArrayBuffer(1)], "fake.txt")

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    setFieldValueStub = sinon.stub()
  })

  afterEach(() => {
    sandbox.restore()
  })
  ;["file", "name"].forEach(fileFieldName => {
    it(`renders a file upload field w/name=${fileFieldName}, no pre-existing file, with working button`, () => {
      const wrapper = shallow(
        <FileUploadField
          name={fileFieldName}
          setFieldValue={setFieldValueStub}
        />
      )
      expect(
        wrapper
          .find("input")
          .at(0)
          .prop("type")
      ).toBe("file")
      expect(
        wrapper
          .find("input")
          .at(0)
          .prop("name")
      ).toBe(fileFieldName)
      expect(
        wrapper
          .find("input")
          .at(1)
          .prop("value")
      ).toBe(fileFieldName)
      expect(wrapper.find(".current-file")).toHaveLength(0)
      wrapper
        .find("input")
        .at(0)
        .simulate("change", { target: { files: [mockFile] } })
      expect(setFieldValueStub.calledWith(fileFieldName, mockFile)).toBeTruthy()
    })
  })
  ;["file", "name"].forEach(fileFieldName => {
    it(`renders a file upload field w/name=${fileFieldName}, with pre-existing file`, () => {
      const currentFile = "oldfile.txt"
      const wrapper = shallow(
        <FileUploadField
          name={fileFieldName}
          setFieldValue={setFieldValueStub}
          value={`https://aws.com/uuid_${currentFile}`}
        />
      )
      expect(
        wrapper
          .find(".current-file")
          .find("a")
          .text()
      ).toBe(currentFile)
    })
  })
})
