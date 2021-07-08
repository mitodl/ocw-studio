import React, {
  MouseEvent as ReactMouseEvent,
  useCallback,
  useState
} from "react"
import { useLocation } from "react-router-dom"
import { useRequest } from "redux-query-react"
import { useSelector } from "react-redux"

import SiteContentEditor from "./SiteContentEditor"
import PaginationControls from "./PaginationControls"
import Card from "./Card"
import BasicModal from "./BasicModal"
import { useWebsite } from "../context/Website"

import { WEBSITE_CONTENT_PAGE_SIZE } from "../constants"
import { siteContentListingUrl } from "../lib/urls"
import { splitFieldsIntoColumns } from "../lib/site_content"
import {
  websiteContentListingRequest,
  WebsiteContentListingResponse
} from "../query-configs/websites"
import { getWebsiteContentListingCursor } from "../selectors/websites"

import {
  ContentListingParams,
  RepeatableConfigItem,
  WebsiteContentListItem
} from "../types/websites"
import { ContentFormType } from "../types/forms"

export default function RepeatableContentListing(props: {
  configItem: RepeatableConfigItem
}): JSX.Element | null {
  const { configItem } = props

  const website = useWebsite()

  const { search } = useLocation()
  const offset = Number(new URLSearchParams(search).get("offset") ?? 0)

  const listingParams: ContentListingParams = {
    name: website.name,
    type: configItem.name,
    offset
  }

  const [
    { isPending: contentListingPending },
    fetchWebsiteContentListing
  ] = useRequest(websiteContentListingRequest(listingParams))
  const listing: WebsiteContentListingResponse = useSelector(
    getWebsiteContentListingCursor
  )(listingParams)

  const [panelState, setPanelState] = useState<{
    textId: string | null
    formType: ContentFormType | null
  }>({ textId: null, formType: null })
  const closeContentPanel = useCallback(() => {
    setPanelState({ textId: null, formType: null })
  }, [setPanelState])

  if (contentListingPending) {
    return <div className="site-page container">Loading...</div>
  }
  if (!listing) {
    return null
  }

  const startAddOrEdit = (textId: string | null) => (
    event: ReactMouseEvent<HTMLLIElement | HTMLAnchorElement, MouseEvent>
  ) => {
    event.preventDefault()
    setPanelState({
      textId,
      formType: textId ? ContentFormType.Edit : ContentFormType.Add
    })
  }

  const labelSingular = configItem.label_singular ?? configItem.label
  const modalTitle =
    panelState.formType &&
    `${
      panelState.formType === ContentFormType.Edit ? "Edit" : "Add"
    } ${labelSingular}`
  const modalClassName = `right ${
    splitFieldsIntoColumns(configItem.fields).length > 1 ? "wide" : ""
  }`

  return (
    <>
      <BasicModal
        isVisible={!!panelState.formType}
        hideModal={closeContentPanel}
        title={modalTitle}
        className={modalClassName}
      >
        {modalProps =>
          panelState.formType && (
            <div className="m-3">
              <SiteContentEditor
                loadContent={true}
                configItem={configItem}
                textId={panelState.textId}
                formType={panelState.formType}
                hideModal={modalProps.hideModal}
                fetchWebsiteContentListing={fetchWebsiteContentListing}
              />
            </div>
          )
        }
      </BasicModal>
      <div>
        <Card>
          <div className="d-flex flex-direction-row align-items-center justify-content-between pb-3">
            <h3>{configItem.label}</h3>
            <a className="btn blue-button add" onClick={startAddOrEdit(null)}>
              Add {labelSingular}
            </a>
          </div>
          <ul className="ruled-list">
            {listing.results.map((item: WebsiteContentListItem) => (
              <li
                key={item.text_id}
                className="py-3 listing-result"
                onClick={startAddOrEdit(item.text_id)}
              >
                <div className="d-flex flex-direction-row align-items-center justify-content-between">
                  <span>{item.title}</span>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      <PaginationControls
        listing={listing}
        previous={siteContentListingUrl
          .param({
            name:        website.name,
            contentType: configItem.name
          })
          .query({ offset: offset - WEBSITE_CONTENT_PAGE_SIZE })
          .toString()}
        next={siteContentListingUrl
          .param({
            name:        website.name,
            contentType: configItem.name
          })
          .query({ offset: offset + WEBSITE_CONTENT_PAGE_SIZE })
          .toString()}
      />
    </>
  )
}
