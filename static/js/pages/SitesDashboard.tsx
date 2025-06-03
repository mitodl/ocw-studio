import React, { useState } from "react"
import { useSelector } from "react-redux"
import { useRequest } from "redux-query-react"
import { Link } from "react-router-dom"

import PaginationControls from "../components/PaginationControls"
import { publishStatusMessage } from "../components/PublishStatusIndicator"

import {
  WebsiteListingParams,
  websiteListingRequest,
  WebsiteListingResponse,
} from "../query-configs/websites"
import { getWebsiteListingCursor } from "../selectors/websites"
import { newSiteUrl, siteDetailUrl } from "../lib/urls"
import { Website, WebsiteDropdown, WebsiteInitials } from "../types/websites"
import { MaterialIcons } from "../types/common"
import DocumentTitle, { formatTitle } from "../components/DocumentTitle"
import { StudioList, StudioListItem } from "../components/StudioList"
import Dropdown from "../components/Dropdown"
import UnpublishDialog from "../components/UnpublishDialog"
import { useURLParamFilter, usePagination } from "../hooks/search"
import { usePermission } from "../hooks/permissions"
import { Permission, PublishStatus } from "../constants"

function getListingParams(search: string): WebsiteListingParams {
  const qsParams = new URLSearchParams(search)
  const offset = Number(qsParams.get("offset") ?? 0)
  const searchString = qsParams.get("q")

  return searchString ? { offset, search: searchString } : { offset }
}

export const publishStatusIndicatorClass = (
  status: PublishStatus | null,
): string => {
  switch (status) {
    case PublishStatus.NotStarted:
      return "text-secondary"
    case PublishStatus.Pending:
    case PublishStatus.Started:
      return "text-warning"
    case PublishStatus.Aborted:
    case PublishStatus.Errored:
      return "text-danger"
    case PublishStatus.Success:
      return "text-success"
    default:
      return ""
  }
}

export const formatDateTime = (dateTimeString: string): string => {
  const date = new Date(dateTimeString)
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })
}

export const StatusWithDateHover = ({
  statusText,
  dateTime,
  className,
}: {
  statusText: string
  dateTime: string
  className: string
}) => {
  const [showDate, setShowDate] = useState(false)

  return (
    <div
      className={className}
      onMouseEnter={() => setShowDate(true)}
      onMouseLeave={() => setShowDate(false)}
    >
      {showDate ? `${statusText} at (${formatDateTime(dateTime)})` : statusText}
    </div>
  )
}

export default function SitesDashboard(): JSX.Element {
  const [websiteToUnpublish, setWebsiteToUnpublish] =
    useState<WebsiteInitials | null>(null)

  const { listingParams, searchInput, setSearchInput } =
    useURLParamFilter(getListingParams)
  const [, fetchWebsiteContentListing] = useRequest(
    websiteListingRequest(listingParams),
  )

  const listing: WebsiteListingResponse = useSelector(getWebsiteListingCursor)(
    listingParams.offset,
  )
  const pages = usePagination(listing.count ?? 0)

  const canAddSites = usePermission(Permission.CanAddWebsite)

  const websiteDropdownMenuList: WebsiteDropdown[] = [
    {
      id: "1",
      label: "Unpublish",
      clickHandler: (website: WebsiteInitials) => {
        setWebsiteToUnpublish(website)
      },
    },
  ]

  const unpublishSuccessCallback = () => {
    fetchWebsiteContentListing()
  }

  return (
    <div className="px-4 dashboard">
      <DocumentTitle title={formatTitle("Sites")} />
      <div className="content">
        <div className="d-flex flex-direction-row align-items-center justify-content-between pb-3">
          <div>
            <h2 className="my-2 p-0">Sites</h2>
          </div>
          <div className="d-flex align-items-center">
            <input
              placeholder="Search for a site"
              className="site-search-input mr-5 form-control"
              value={searchInput}
              onChange={setSearchInput}
            />
            {canAddSites ? (
              <Link
                className="btn cyan-button larger add-new"
                to={newSiteUrl.toString()}
              >
                Add Site
              </Link>
            ) : null}
          </div>
        </div>
        <StudioList>
          {listing.results.map((site: Website) => (
            <StudioListItem
              title={site.title}
              subtitle={site.short_id}
              to={siteDetailUrl.param({ name: site.name }).toString()}
              key={site.uuid}
            >
              <div className="d-flex flex-row">
                {!site.publish_date && !site.live_publish_status ? (
                  <div className="text-danger">Never Published</div>
                ) : site.unpublished ? (
                  <StatusWithDateHover
                    statusText="Unpublished from Production"
                    dateTime={site.updated_on}
                    className="text-dark"
                  />
                ) : site.draft_publish_date && !site.publish_date ? (
                  <div className="text-secondary">Draft</div>
                ) : PublishStatus.Success === site.live_publish_status ? (
                  <StatusWithDateHover
                    statusText="Published"
                    dateTime={site.updated_on}
                    className="text-success"
                  />
                ) : (
                  <StatusWithDateHover
                    statusText={publishStatusMessage(site.live_publish_status)}
                    dateTime={site.updated_on}
                    className={publishStatusIndicatorClass(
                      site.live_publish_status,
                    )}
                  />
                )}
                <Dropdown
                  website={{
                    name: site.name,
                    title: site.title,
                    short_id: site.short_id,
                  }}
                  dropdownBtnID={`${site.uuid}_DropdownMenuButton`}
                  materialIcon={MaterialIcons.MoreVert}
                  dropdownMenu={
                    site.publish_date &&
                    !site.unpublished &&
                    site.live_publish_status !== null &&
                    [
                      PublishStatus.Errored,
                      PublishStatus.Aborted,
                      PublishStatus.Success,
                    ].includes(site.live_publish_status)
                      ? websiteDropdownMenuList
                      : websiteDropdownMenuList.filter(
                          (item) => item.id !== "1",
                        )
                  }
                />
              </div>
            </StudioListItem>
          ))}
        </StudioList>
        <PaginationControls previous={pages.previous} next={pages.next} />
      </div>

      {websiteToUnpublish ? (
        <UnpublishDialog
          website={websiteToUnpublish}
          successCallback={unpublishSuccessCallback}
          closeDialog={() => {
            setWebsiteToUnpublish(null)
          }}
        />
      ) : null}
    </div>
  )
}
