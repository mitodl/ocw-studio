import { useParams, useHistory } from "react-router"
import { useWebsiteContent } from "../hooks/websites"
import { useEffect } from "react"
import { siteContentDetailUrl } from "../lib/urls"
import { useWebsite } from "../context/Website"
/**
 * A page to be served at /content/:uuid that fetches the resource and reroutes
 * the user to the appropriate page, i.e.,
 *  /type/pages/:uuid
 *  /type/resources/:uuid
 *  /type/video-galleries/:uuid
 * etc.
 **/
const GenericContentReroutePage = () => {
  const { uuid } = useParams<{ uuid: string }>()
  const history = useHistory()
  const website = useWebsite()
  const [resource] = useWebsiteContent(uuid)
  useEffect(() => {
    if (!resource?.type) return
    history.replace({
      pathname: siteContentDetailUrl.param({
        contentType: resource.type,
        name: website.name,
        uuid: resource.text_id,
      }).pathname,
    })
  }, [uuid, history, resource?.type, resource?.text_id, website.name])

  return null
}

export default GenericContentReroutePage
