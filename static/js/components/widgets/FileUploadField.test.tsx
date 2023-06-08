import React from "react"
import { shallow } from "enzyme"
import sinon, { SinonSandbox } from "sinon"

import FileUploadField from "./FileUploadField"

describe("FileUploadField", () => {
  let sandbox: SinonSandbox
  const mockFile = new File([new ArrayBuffer(1)], "fake.txt")

  beforeEach(() => {
    sandbox = sinon.createSandbox()
  })

  afterEach(() => {
    sandbox.restore()
  })
  ;["file", "name"].forEach(fileFieldName => {
    it(`renders a file upload field w/name=${fileFieldName}, no pre-existing file, with working button`, () => {
      const onChangeStub = jest.fn()
      const wrapper = shallow(
        <FileUploadField name={fileFieldName} onChange={onChangeStub} />
      )
      expect(wrapper.find("input").at(0).prop("type")).toBe("file")
      expect(wrapper.find("input").at(0).prop("name")).toBe(fileFieldName)
      expect(wrapper.find("input").at(1).prop("value")).toBe(fileFieldName)
      expect(wrapper.find(".current-file")).toHaveLength(0)
      wrapper
        .find("input")
        .at(0)
        .simulate("change", {
          target: { name: fileFieldName, files: [mockFile] }
        })
      expect(onChangeStub).toHaveBeenCalledWith({
        target: {
          name:  fileFieldName,
          value: mockFile
        }
      })
    })
  })

  //
  ;["file", "name"].forEach(fileFieldName => {
    it(`renders a file upload field w/name=${fileFieldName}, with pre-existing file`, () => {
      const currentFile = "oldfile.txt"
      const wrapper = shallow(
        <FileUploadField
          name={fileFieldName}
          onChange={jest.fn()}
          value={`https://aws.com/32629a023dc541288e430392b51e7b61_${currentFile}`}
        />
      )
      expect(wrapper.find(".current-file").find("a").text()).toBe(currentFile)
    })
  })
})
