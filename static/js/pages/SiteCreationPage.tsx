import * as React from "react"
import { useSelector } from "react-redux"
import { useMutation, useRequest } from "redux-query-react"
import { RouteComponentProps } from "react-router-dom"
import { FormikHelpers } from "formik"

import { SiteForm, SiteFormValues } from "../components/forms/SiteForm"
import Card from "../components/Card"

import {
  getTransformedWebsiteName,
  websiteMutation,
  websiteStartersRequest
} from "../query-configs/websites"
import { startersSelector } from "../selectors/websites"
import { getResponseBodyError, isErrorResponse } from "../lib/util"
import { siteDetailUrl } from "../lib/urls"
import { NewWebsitePayload } from "../types/websites"

type Props = RouteComponentProps<Record<string, never>>

export default function SiteCreationPage({
  history
}: Props): JSX.Element | null {
  const [starterQueryState] = useRequest(websiteStartersRequest())
  const [
    createWebsiteQueryState,
    createWebsite
  ] = useMutation((payload: NewWebsitePayload) => websiteMutation(payload))

  const onSubmitForm = async (
    values: SiteFormValues,
    { setErrors, setSubmitting, setStatus }: FormikHelpers<SiteFormValues>
  ) => {
    if (!values.starter || createWebsiteQueryState.isPending) {
      return
    }
    const response = await createWebsite({
      title:   values.title,
      starter: values.starter
    })
    if (!response) {
      return
    }
    // Display errors if any were returned
    if (isErrorResponse(response)) {
      const errors = getResponseBodyError(response)
      if (!errors) {
        return
      } else if (typeof errors === "string") {
        // Non-field error
        setStatus(errors)
      } else {
        setErrors({
          // Name is autogenerated, so if any errors come back for the "name" property, attach them to the title field
          title:   errors.title || errors.name,
          starter: errors.starter
        })
      }
      return
    }
    // Redirect to the new site if it was successfully created
    setSubmitting(false)
    const newWebsiteName = getTransformedWebsiteName(response)
    if (!newWebsiteName) {
      return
    }
    history.push(siteDetailUrl.param({ name: newWebsiteName }).toString())
  }

  const websiteStarters = useSelector(startersSelector)

  if (starterQueryState.isPending) {
    return (
      <div className="new-site narrow-page-body container mt-3">Loading...</div>
    )
  }

  return (
    <div className="new-site narrow-page-body container mt-5">
      <h4 className="font-weight-light">Add Course</h4>
      <Card>
        <div className="p-5">
          <SiteForm onSubmit={onSubmitForm} websiteStarters={websiteStarters} />
        </div>
      </Card>
    </div>
  )
}
