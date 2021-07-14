import React, { useCallback, useState } from "react"
import { Form, Formik, Field, FormikHelpers, FormikProps } from "formik"

import SelectField, { Option } from "../widgets/SelectField"
import { WCItemCreateFormFields } from "../../types/forms"
import { Website } from "../../types/websites"
import { useMutation } from "redux-query-react"
import { siteApiListingUrl } from "../../lib/urls"
import { WebsiteListingResponse } from "../../query-configs/websites"
import { WebsiteCollection } from "../../types/website_collections"
import { createWebsiteCollectionItemMutation } from "../../query-configs/website_collections"

interface Props {
  websiteCollection: WebsiteCollection
}

const formatOptions = (websites: Website[]) =>
  websites.map(website => ({ label: website.title, value: website.uuid }))

export default function WebsiteCollectionItemForm(props: Props): JSX.Element {
  const { websiteCollection } = props
  const [options, setOptions] = useState<Option[]>([])

  const loadOptions = useCallback(
    async (inputValue: string, callback: (options: Option[]) => void) => {
      const url = siteApiListingUrl
        .query({ offset: 0 })
        .param({ search: inputValue })
        .toString()

      // using plain fetch rather than redux-query here because this
      // use-case doesn't exactly jibe with redux-query: we need to issue
      // a request programmatically on user input.
      const response = await fetch(url)
      const json: WebsiteListingResponse = await response.json()
      const { results } = json
      const options = formatOptions(results)
      setOptions(current => [...current, ...options])
      callback(options)
    },
    [setOptions]
  )

  const [
    { isPending: itemCreatePending },
    createWCItem
  ] = useMutation((values: WCItemCreateFormFields) =>
    createWebsiteCollectionItemMutation(values, websiteCollection.id)
  )

  const onSubmit = useCallback(
    (
      values: WCItemCreateFormFields,
      formikHelpers: FormikHelpers<WCItemCreateFormFields>
    ) => {
      const { resetForm } = formikHelpers
      createWCItem(values)
      resetForm()
    },
    [createWCItem]
  )

  // we pass `{ website: undefined }` to Formik via `initialValues` because
  // although `""` is a more correct 'empty' value for our field the react-select
  // component does not consider `""` to be an empty value. So if we pass
  // `{ website: "" }` react-select won't consider itself to be 'empty' and then
  // won't display our placeholder.
  return (
    <Formik onSubmit={onSubmit} initialValues={{ website: undefined } as any}>
      {({ values }: FormikProps<{ website: string | undefined }>) => (
        <Form>
          <div className="d-flex">
            <Field
              name="website"
              options={options}
              className="w-100"
              as={SelectField}
              loadOptions={loadOptions}
              placeholder="Find a course to add to this collection"
            />
            <button
              type="submit"
              disabled={itemCreatePending || values.website === undefined}
              className="px-4 ml-3 btn blue-button"
            >
              Add
            </button>
          </div>
        </Form>
      )}
    </Formik>
  )
}
