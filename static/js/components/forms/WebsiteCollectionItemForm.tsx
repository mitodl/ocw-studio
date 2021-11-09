import React, { useCallback } from "react"
import { Form, Formik, Field, FormikHelpers, FormikProps } from "formik"

import SelectField from "../widgets/SelectField"
import { WCItemCreateFormFields } from "../../types/forms"
import { useMutation } from "redux-query-react"
import { WebsiteCollection } from "../../types/website_collections"
import { createWebsiteCollectionItemMutation } from "../../query-configs/website_collections"
import { useWebsiteSelectOptions } from "../../hooks/websites"

interface Props {
  websiteCollection: WebsiteCollection
}

export default function WebsiteCollectionItemForm(props: Props): JSX.Element {
  const { websiteCollection } = props

  const { options, loadOptions } = useWebsiteSelectOptions()

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
              defaultOptions={options}
            />
            <button
              type="submit"
              disabled={itemCreatePending || values.website === undefined}
              className="px-4 ml-3 btn cyan-button"
            >
              Add
            </button>
          </div>
        </Form>
      )}
    </Formik>
  )
}
