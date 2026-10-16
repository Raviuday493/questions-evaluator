"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export function useCurrentUser() {
  return useQuery({ queryKey: ["me"], queryFn: api.me, staleTime: 5 * 60_000 });
}

export function useLogout() {
  const router = useRouter();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.logout,
    onSettled: () => {
      // Navigate away first so mounted queries don't refetch (and 401) after the cache is cleared.
      router.replace("/login");
      router.refresh();
      queryClient.clear();
    },
  });
}
