import React from "react"
import sinon, { SinonStub } from "sinon"
import { shallow } from "enzyme"
import { ValidationError } from "yup"

import { PublishForm, websiteUrlValidation } from "./PublishForm"
import {
  PUBLISH_OPTION_PRODUCTION,
  PUBLISH_OPTION_STAGING
} from "../../constants"
import { defaultFormikChildProps } from "../../test_util"
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
        option={PUBLISH_OPTION_STAGING}
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
  }) //
  ;[null, "courses/5.2-my-course"].forEach(urlPath => {
    it(`initialValue for url_path should be based on website ${
      urlPath ? "url_path" : "url_suggestion"
    }`, () => {
      website.publish_date = null
      website.url_path = urlPath
      const wrapper = renderForm()
      expect(wrapper.prop("initialValues")).toEqual({
        url_path: website.url_path ? "5.2-my-course" : website.url_suggestion
      })
    })
  })

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
  }) //
  ;[PUBLISH_OPTION_STAGING, PUBLISH_OPTION_PRODUCTION].forEach(option => {
    it("shows a URL link instead of a field if website is published", () => {
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
        option === PUBLISH_OPTION_STAGING ? website.draft_url : website.live_url
      )
    })
  })

  describe("validation", () => {
    it("rejects an empty url", async () => {
      try {
        await expect(
          await websiteUrlValidation.validateAt("url_path", { url_path: "" })
        ).rejects.toThrow()
      } catch (error) {
        expect(error).toBeInstanceOf(ValidationError)
        // @ts-ignore
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
        expect(error).toBeInstanceOf(ValidationError)
        // @ts-ignore
        expect(error.errors).toStrictEqual([
          "Only alphanumeric characters, periods, dashes, or underscores allowed"
        ])
      }
    })
  })
})
