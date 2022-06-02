import { useAppSelector } from "../hooks/redux"
import { Permissions } from "../constants"

// The main idea of this hook is to be able to define multiple validators which
// grant access based on user permissions
export function usePermission(permission: Permissions): boolean {
  const { user } = useAppSelector(state => state.user)
  const validators = { canCreateSites: _canCreateSites }

  function _canCreateSites(): boolean {
    return user?.isSuperuser || false
  }

  return validators[permission]()
}
