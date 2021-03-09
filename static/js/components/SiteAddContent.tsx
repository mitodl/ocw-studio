import React from "react"
import { useRouteMatch, RouteComponentProps } from "react-router-dom"
import { useSelector } from "react-redux"
import { FormikHelpers } from "formik"
import { useMutation } from "redux-query-react"

import SiteAddForm from "./forms/SiteAddForm"

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
type Props = RouteComponentProps<Record<string, never>>
export default function SiteAddContent({ history }: Props): JSX.Element | null {
  const match = useRouteMatch<MatchParams>()
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
    const payload = {
      type: contenttype,
      ...contentFormValuesToPayload(values, configItem.fields)
    }

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
    history.push(siteContentListingUrl(name, contenttype))
  }

  return (
    <div>
      <h3>New {configItem.label}</h3>
      <div>
        <SiteAddForm onSubmit={onSubmitForm} configItem={configItem} />
      </div>
    </div>
  )
}
