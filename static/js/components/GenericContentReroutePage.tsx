import { useParams, useHistory } from "react-router"
import { useWebsiteContent } from "../hooks/websites"
import { useEffect } from "react"
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
  const [resource] = useWebsiteContent(uuid)
  useEffect(() => {
    if (!resource?.type) return
    history.replace({
      pathname: `/type/${resource.type}/${uuid}`,
    })
  }, [uuid, history, resource?.type])

  return null
}

export default GenericContentReroutePage
