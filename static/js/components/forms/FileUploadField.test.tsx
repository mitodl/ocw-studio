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

  it("renders a file upload field, no pre-existing file, with working button", () => {
    const wrapper = shallow(
      <FileUploadField name="file" setFieldValue={setFieldValueStub} />
    )
    expect(wrapper.find("input").prop("type")).toBe("file")
    expect(wrapper.find("input").prop("name")).toBe("file")
    expect(wrapper.find(".current-file")).toHaveLength(0)
    wrapper.find("input").simulate("change", { target: { files: [mockFile] } })
    expect(setFieldValueStub.calledWith("file", mockFile)).toBeTruthy()
  })

  it("renders a file upload field, with pre-existing file", () => {
    const currentFile = "oldfile.txt"
    const wrapper = shallow(
      <FileUploadField
        name="file"
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
