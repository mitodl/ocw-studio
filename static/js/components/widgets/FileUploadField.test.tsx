import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"

import FileUploadField from "./FileUploadField"

describe("FileUploadField", () => {
  const mockFile = new File([new ArrayBuffer(1)], "fake.txt")

  it.each(["file", "name"])(
    "renders a file upload field w/name=%s, no pre-existing file, with working button",
    (fileFieldName) => {
      const onChangeStub = jest.fn()
      const { container } = render(
        <FileUploadField name={fileFieldName} onChange={onChangeStub} />,
      )

      const inputs = container.querySelectorAll("input")
      const fileInput = inputs[0]
      const hiddenInput = inputs[1]

      expect(fileInput).toHaveAttribute("type", "file")
      expect(fileInput).toHaveAttribute("name", fileFieldName)
      expect(hiddenInput).toHaveAttribute("value", fileFieldName)
      expect(container.querySelector(".current-file")).toBeNull()

      fireEvent.change(fileInput, {
        target: { name: fileFieldName, files: [mockFile] },
      })

      expect(onChangeStub).toHaveBeenCalledWith({
        target: {
          name: fileFieldName,
          value: mockFile,
        },
      })
    },
  )

  it.each(["file", "name"])(
    "renders a file upload field w/name=%s, with pre-existing file",
    (fileFieldName) => {
      const currentFile = "oldfile.txt"
      render(
        <FileUploadField
          name={fileFieldName}
          onChange={jest.fn()}
          value={`https://aws.com/32629a023dc541288e430392b51e7b61_${currentFile}`}
        />,
      )

      expect(
        screen.getByRole("link", { name: currentFile }),
      ).toBeInTheDocument()
    },
  )
})
