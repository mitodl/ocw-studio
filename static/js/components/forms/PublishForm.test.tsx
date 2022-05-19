import React from "react"
import sinon, { SinonStub } from "sinon"
import { shallow } from "enzyme"
import { ValidationError } from "yup"

import PublishForm, { websiteUrlValidation } from "./PublishForm"
import { PublishingEnv } from "../../constants"
import { assertInstanceOf, defaultFormikChildProps } from "../../test_util"
import { makeWebsiteDetail } from "../../util/factories/websites"

describe("PublishForm", () => {
  let sandbox, onSubmitStub: SinonStub
  const website = makeWebsiteDetail()

  const renderForm = (props = {}) =>
    shallow(
      <PublishForm
        onSubmit={onSubmitStub}
        disabled={false}
        website={website}
        option={PublishingEnv.Staging}
        {...props}
      />
    )

  const renderInnerForm = (
    formikChildProps: { [key: string]: any },
    wrapperProps: { [key: string]: any }
  ) => {
    const wrapper = renderForm(wrapperProps)
    return (
      wrapper
        .find("Formik")
        // @ts-ignore
        .renderProp("children")({
          ...defaultFormikChildProps,
          ...formikChildProps
        })
    )
  }

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    onSubmitStub = sandbox.stub()
  })

  it("passes onSubmit to Formik", () => {
    const wrapper = renderForm()

    const props = wrapper.find("Formik").props()
    expect(props.onSubmit).toBe(onSubmitStub)
  })

  it.each([
    { urlPath: null, basedOn: "url_suggestion" },
    { urlPath: "courses/5.2-my-course", basedOn: "url_path" }
  ])(
    "initialValue for url_path should be based on website $basedOn",
    ({ urlPath }) => {
      website.publish_date = null
      website.url_path = urlPath
      const wrapper = renderForm()
      expect(wrapper.prop("initialValues")).toEqual({
        url_path: website.url_path ? "5.2-my-course" : website.url_suggestion
      })
    }
  )

  it("shows a field for URL Path if website is not published", () => {
    website.publish_date = null
    const form = renderInnerForm(
      { isSubmitting: false, status: "whatever" },
      {}
    )
    expect(
      form
        .find("Field")
        .filterWhere(node => node.prop("name") === "url_path")
        .exists()
    ).toBeTruthy()
  })

  it.each([PublishingEnv.Staging, PublishingEnv.Production])(
    "shows a URL link instead of a field if website is published",
    option => {
      website.publish_date = "2020-01-01"
      website.url_path = "courses/my-url-fall-2028"
      const form = renderInnerForm(
        { isSubmitting: false, status: "whatever" },
        { option: option }
      )
      expect(
        form
          .find("Field")
          .filterWhere(node => node.prop("name") === "url_path")
          .exists()
      ).toBeFalsy()
      expect(form.find("a").prop("href")).toEqual(
        option === PublishingEnv.Staging ? website.draft_url : website.live_url
      )
    }
  )

  it("shows a text-only live url for unpublished site", () => {
    website.publish_date = null
    website.url_path = "courses/my-url-fall-2028"
    const form = renderInnerForm(
      { isSubmitting: false, status: "whatever" },
      { option: PublishingEnv.Production }
    )
    //expect(form.find("a").exists()).toBeFalsy()
    expect(form.find("span").text()).toEqual(`${website.live_url}`)
  })

  describe("validation", () => {
    it("rejects an empty url", async () => {
      try {
        await expect(
          await websiteUrlValidation.validateAt("url_path", { url_path: "" })
        ).rejects.toThrow()
      } catch (error) {
        assertInstanceOf(error, ValidationError)
        expect(error.errors).toStrictEqual(["URL Path is a required field"])
      }
    })
    it("rejects a URL Path with invalid characters", async () => {
      try {
        await expect(
          await websiteUrlValidation.validateAt("url_path", {
            url_path: "courses/bad-url-fall-2024"
          })
        ).rejects.toThrow()
      } catch (error) {
        assertInstanceOf(error, ValidationError)
        expect(error.errors).toStrictEqual([
          "Only alphanumeric characters, periods, dashes, or underscores allowed"
        ])
      }
    })
  })
})
