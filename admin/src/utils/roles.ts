import type { AdminRole } from "@/types";

/** Roles the current admin may assign: all of the role's permissions must already be theirs. */
export function assignableRoles(roles: AdminRole[] | undefined, isSuper: boolean, can: (p: string) => boolean): AdminRole[] {
  return (roles ?? []).filter((r) => (r.is_wildcard ? isSuper : r.permissions.every(can)));
}
