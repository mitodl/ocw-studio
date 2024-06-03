import React from "react"
import { shallow } from "enzyme"
import { Formik, FormikProps } from "formik"

import MenuItemForm from "./MenuItemForm"
import { defaultFormikChildProps } from "../../test_util"

import { WebsiteContent } from "../../types/websites"
import { makeWebsiteContentDetail } from "../../util/factories/websites"

describe("MenuItemForm", () => {
  let onSubmitStub: any, contentContext: WebsiteContent[]

  beforeEach(() => {
    onSubmitStub = jest.fn()
    contentContext = [makeWebsiteContentDetail(), makeWebsiteContentDetail()]
  })

  const renderForm = (props = {}) =>
    shallow(
      <MenuItemForm
        activeItem={null}
        onSubmit={onSubmitStub}
        contentContext={contentContext}
        {...props}
      />,
    )

  const renderInnerForm = (
    formProps: { [key: string]: any },
    formikChildProps: Partial<FormikProps<any>>,
  ) => {
    const wrapper = renderForm(formProps || {})
    return wrapper.find(Formik).renderProp("children")({
      ...defaultFormikChildProps,
      ...formikChildProps,
    })
  }

  it("calls the onSubmit method", () => {
    const wrapper = renderForm()

    wrapper.prop("onSubmit")()
    expect(onSubmitStub).toHaveBeenCalledTimes(1)
    const innerWrapper = renderInnerForm({}, {})
    const submitBtn = innerWrapper.find("button.cyan-button")
    expect(submitBtn.prop("type")).toEqual("submit")
  })

  it("renders with the correct initial values if given a null active item", () => {
    const wrapper = renderForm({
      activeItem: null,
    })
    expect(wrapper.prop("initialValues")).toEqual({
      menuItemTitle: "",
      contentLink: "",
    })
  })

  it("renders with the correct initial values if given an active item with internal link", () => {
    const activeItem = {
      text: "text",
      targetContentId: "content-id",
    }
    const wrapper = renderForm({
      activeItem,
    })
    expect(wrapper.prop("initialValues")).toEqual({
      menuItemTitle: activeItem.text,
      contentLink: activeItem.targetContentId,
    })
  })

  it("renders an internal link dropdown", () => {
    const wrapper = renderInnerForm(
      {},
      {
        values: {
          menuItemTitle: "",
          contentLink: "",
        },
      },
    )
    const relationField = wrapper.find('RelationField[name="contentLink"]')
    expect(relationField.exists()).toBe(true)
  })

  it("renders a RelationField and passes down the right props", () => {
    const existingMenuIds = ["abc", "def"]
    const value = "def"
    const collections = ["page"]
    const setFieldValueStub = jest.fn()
    const wrapper = renderInnerForm(
      {
        existingMenuIds: existingMenuIds,
        collections: collections,
      },
      {
        values: {
          menuItemTitle: "",
          contentLink: value,
        },
        setFieldValue: setFieldValueStub,
      },
    )
    const relationField = wrapper.find('RelationField[name="contentLink"]')
    expect(relationField.exists()).toBe(true)
    expect(relationField.prop("value")).toEqual(value)
    expect(relationField.prop("valuesToOmit")).toEqual(existingMenuIds)
    expect(relationField.prop("contentContext")).toBe(contentContext)
    expect(relationField.prop("collection")).toEqual(collections)
    const fakeEvent = {
      target: { value: { content: "abc", website: "ignored" } },
    }
    // @ts-expect-error Not using a full event
    relationField.prop("onChange")(fakeEvent)
    expect(setFieldValueStub).toHaveBeenCalledWith("contentLink", "abc")
  })
})
