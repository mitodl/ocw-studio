import React from "react"
import { shallow } from "enzyme"
import { Formik, FormikProps } from "formik"

import MenuItemForm from "./MenuItemForm"
import { defaultFormikChildProps } from "../../test_util"

import { LinkType, WebsiteContent } from "../../types/websites"
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
      menuItemType: LinkType.Internal,
      externalLink: "",
      internalLink: "",
      includeLicenseWarning: true,
    })
  })
  ;[
    ["http://example.com", LinkType.External, true],
    ["http://example.com", LinkType.External, false],
    [null, LinkType.Internal, null],
  ].forEach(([targetUrl, expLinkType, includeWarning]) => {
    it(`renders with the correct initial values if given an active item with ${expLinkType} link`, () => {
      const activeItem = {
        text: "text",
        targetContentId: "content-id",
        targetUrl: targetUrl,
        includeLicenseWarning: includeWarning,
      }
      const wrapper = renderForm({
        activeItem,
      })
      expect(wrapper.prop("initialValues")).toEqual({
        menuItemTitle: activeItem.text,
        menuItemType: expLinkType,
        externalLink: activeItem.targetUrl || "",
        internalLink: activeItem.targetContentId,
        includeLicenseWarning: includeWarning !== false,
      })
    })
  })

  it("has radio buttons to switch between external and internal links", () => {
    const setFieldValueStub = jest.fn()
    const wrapper = renderInnerForm(
      {},
      {
        values: {
          menuItemTitle: "",
          menuItemType: LinkType.Internal,
          externalLink: "",
          internalLink: "",
        },
        setFieldValue: setFieldValueStub,
      },
    )
    const itemTypeBtns = wrapper.find('input[name="menuItemType"]')
    expect(itemTypeBtns).toHaveLength(2)
    const internalBtn = itemTypeBtns.at(0)
    const externalBtn = itemTypeBtns.at(1)
    expect(internalBtn.prop("checked")).toBe(true)
    expect(internalBtn.prop("value")).toEqual(LinkType.Internal)
    expect(externalBtn.prop("checked")).toBe(false)
    expect(externalBtn.prop("value")).toEqual(LinkType.External)
    // @ts-expect-error Not going to simulate the event
    externalBtn.prop("onChange")()
    expect(setFieldValueStub).toHaveBeenCalledWith(
      "menuItemType",
      LinkType.External,
    )
    // @ts-expect-error Not going to simulate the event
    internalBtn.prop("onChange")()
    expect(setFieldValueStub).toHaveBeenCalledWith(
      "menuItemType",
      LinkType.Internal,
    )
  })

  it("renders an internal link dropdown if the 'internal' radio is selected", () => {
    const wrapper = renderInnerForm(
      {},
      {
        values: {
          menuItemTitle: "",
          menuItemType: LinkType.Internal,
          externalLink: "",
          internalLink: "",
        },
      },
    )
    const relationField = wrapper.find('RelationField[name="internalLink"]')
    expect(relationField.exists()).toBe(true)
    expect(wrapper.find('Field[name="externalLink"]').exists()).toBe(false)
  })

  it("renders an external link dropdown if the 'external' radio is selected", () => {
    const wrapper = renderInnerForm(
      {},
      {
        values: {
          menuItemTitle: "",
          menuItemType: LinkType.External,
          externalLink: "",
          internalLink: "",
        },
      },
    )
    const extLinkField = wrapper.find('Field[name="externalLink"]')
    expect(extLinkField.exists()).toBe(true)
    expect(wrapper.find('RelationField[name="internalLink"]').exists()).toBe(
      false,
    )
  })
  ;[LinkType.External, LinkType.Internal].forEach((itemType) =>
    it("renders a BooleanField to include license warning only for external links", () => {
      const wrapper = renderInnerForm(
        {},
        {
          values: {
            menuItemTitle: "",
            menuItemType: itemType,
            externalLink: "",
            internalLink: "",
          },
        },
      )
      const includeWarningField = wrapper.find(
        'BooleanField[name="includeLicenseWarning"]',
      )
      expect(includeWarningField.exists()).toBe(itemType === LinkType.External)
    }),
  )

  it("renders a RelationField and passes down the right props if the internal link option is selected", () => {
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
          menuItemType: LinkType.Internal,
          externalLink: "",
          internalLink: value,
        },
        setFieldValue: setFieldValueStub,
      },
    )
    const relationField = wrapper.find('RelationField[name="internalLink"]')
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
    expect(setFieldValueStub).toHaveBeenCalledWith("internalLink", "abc")
  })
})
