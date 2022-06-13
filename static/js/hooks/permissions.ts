import { useAppSelector } from "../hooks/redux"
import { Permission } from "../constants"

// The main idea of this hook is to be able to define multiple validators which
// grant access based on user permissions
export function usePermission(permission: Permission): boolean {
  const { user } = useAppSelector(state => state.user)
  const validators = { canAddWebsite: _canAddWebsite }

  function _canAddWebsite(): boolean {
    return user?.canAddWebsite ?? false
  }

  return validators[permission]()
}
