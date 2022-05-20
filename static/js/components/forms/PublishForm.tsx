import React from "react"
import { Formik, Form, ErrorMessage, Field, FormikHelpers } from "formik"
import * as yup from "yup"

import { FormError } from "./FormError"

import { Website } from "../../types/websites"
import { PUBLISH_OPTION_STAGING } from "../../constants"

export interface SiteFormValues {
  url_path: string // eslint-disable-line camelcase
}

type Props = {
  onSubmit: (
    values: SiteFormValues,
    formikHelpers: FormikHelpers<SiteFormValues>
  ) => void
  website: Website
  option: string
  disabled: boolean
}

export const websiteUrlValidation = yup.object().shape({
  url_path: yup
    .string()
    .label("URL Path")
    .trim()
    .required()
    .matches(
      /^[a-zA-Z0-9\-._]*$/,
      "Only alphanumeric characters, periods, dashes, or underscores allowed"
    )
})

export const PublishForm: React.FC<Props> = ({
  onSubmit,
  website,
  disabled,
  option
}) => {
  const initialValues: SiteFormValues = {
    // @ts-expect-error
    url_path: website.url_path ?
      website.url_path.split("/").pop() :
      website.url_suggestion
  }

  const fullUrl =
    option === PUBLISH_OPTION_STAGING ? website.draft_url : website.live_url
  const partialUrl = website.url_path ?
    fullUrl.slice(0, fullUrl.lastIndexOf("/")) :
    fullUrl

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={website.publish_date ? null : websiteUrlValidation}
      initialValues={initialValues}
    >
      {({ isSubmitting, status }) => (
        <Form>
          {!website.publish_date ? (
            <div className="form-group">
              <label htmlFor="url_path">URL: </label>{" "}
              {website.draft_publish_date ? (
                <a href={website.draft_url}>{website.draft_url}</a>
              ) : (
                <span>{`${partialUrl}`}</span>
              )}
              <Field type="text" name="url_path" className="form-control" />
              <ErrorMessage name="url_path" component={FormError} />
            </div>
          ) : (
            <div>
              <a href={fullUrl} target="_blank" rel="noreferrer">
                {fullUrl}
              </a>
              <br />
            </div>
          )}
          <div className="form-group d-flex justify-content-end">
            <button
              type="submit"
              className="btn btn-publish cyan-button-outline d-flex flex-direction-row align-items-center"
              disabled={isSubmitting || disabled}
            >
              Publish
            </button>
          </div>
          {status && (
            // Status is being used to store non-field errors
            <div className="form-error">{status}</div>
          )}
        </Form>
      )}
    </Formik>
  )
}
