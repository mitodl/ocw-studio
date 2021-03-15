import React from "react"
import { useRouteMatch, useHistory } from "react-router-dom"
import { useSelector } from "react-redux"
import { FormikHelpers } from "formik"
import { useMutation } from "redux-query-react"

import SiteAddContentForm from "./forms/SiteAddContentForm"
import Card from "./Card"

import { contentFormValuesToPayload } from "../lib/site_content"
import { siteContentListingUrl } from "../lib/urls"
import { getResponseBodyError, isErrorResponse } from "../lib/util"
import {
  createWebsiteContentMutation,
  NewWebsiteContentPayload
} from "../query-configs/websites"
import { getWebsiteDetailCursor } from "../selectors/websites"

import { ConfigItem } from "../types/websites"

interface MatchParams {
  contenttype: string
  name: string
}

export default function SiteAddContent(): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
  const history = useHistory()
  const { contenttype, name } = match.params

  const website = useSelector(getWebsiteDetailCursor)(name)
  const [
    { isPending },
    addWebsiteContent
  ] = useMutation((payload: NewWebsiteContentPayload) =>
    createWebsiteContentMutation(name, payload)
  )

  const configItem: ConfigItem | null = website?.starter?.config?.collections.find(
    (config: ConfigItem) => config.name === contenttype
  )
  if (!configItem) {
    return null
  }

  const onSubmitForm = async (
    values: { [key: string]: string },
    {
      setErrors,
      setSubmitting,
      setStatus
    }: FormikHelpers<NewWebsiteContentPayload>
  ) => {
    if (isPending) {
      return
    }

    values = { type: contenttype, ...values }
    const payload = contentFormValuesToPayload(values, configItem.fields)
    const response = await addWebsiteContent(payload as any)
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
        setErrors(errors)
      }
      return
    }
    setSubmitting(false)

    // Redirect to the site listing if it was successfully created
    history.push(
      siteContentListingUrl.param({ name, contentType: contenttype }).toString()
    )
  }

  return (
    <Card>
      <h3>New {configItem.label}</h3>
      <div>
        <SiteAddContentForm onSubmit={onSubmitForm} configItem={configItem} />
      </div>
    </Card>
  )
}
