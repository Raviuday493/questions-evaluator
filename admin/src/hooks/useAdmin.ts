"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "@/api/endpoints";

export function useAdmin() {
  const query = useQuery({ queryKey: ["admin", "me"], queryFn: adminApi.auth.me, staleTime: 60_000, refetchInterval: 5 * 60_000 });
  const permissions = new Set(query.data?.permissions ?? []);
  return {
    ...query,
    admin: query.data,
    can: (permission: string) => permissions.has(permission),
  };
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: adminApi.auth.logout,
    onSettled: () => {
      client.clear();
      window.location.assign("/login");
    },
  });
}
