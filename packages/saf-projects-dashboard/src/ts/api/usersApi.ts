/**
 * User directory client for the Dash UI server.
 *
 * The routes are served by the Dash server itself (not by GLOW):
 * - `GET  /_saf/users/resolve?q=` -> `{ user_id }` (404 when nobody matches)
 * - `POST /_saf/users/names`      -> `{ names: { user_id: display_name } }`
 *
 * `usersBaseUrl` is relative to the Dash server and defaults to `""` (same origin).
 */
import { buildUrl, handleResponse } from "./projectsApi";

export interface UsersApiClient {
  /** Resolve an e-mail address or username to a user id, `null` when nobody matches. */
  resolve: (text: string, usersBaseUrl?: string) => Promise<string | null>;
  /** Display names of the given user ids. Ids the directory does not know are absent. */
  names: (
    ids: string[],
    usersBaseUrl?: string,
  ) => Promise<Record<string, string>>;
}

export const usersApi: UsersApiClient = {
  resolve: async (text: string, usersBaseUrl?: string) => {
    const query = new URLSearchParams({ q: text }).toString();
    const response = await fetch(
      buildUrl(`/_saf/users/resolve?${query}`, usersBaseUrl),
      { method: "GET", headers: { "Content-Type": "application/json" } },
    );
    if (response.status === 404) return null;
    const body = await handleResponse<{ user_id?: string; error?: string }>(
      response,
    );
    return body.user_id ?? null;
  },

  names: async (ids: string[], usersBaseUrl?: string) => {
    if (ids.length === 0) return {};
    const response = await fetch(buildUrl("/_saf/users/names", usersBaseUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_ids: ids }),
    });
    const body = await handleResponse<{ names?: Record<string, string> }>(
      response,
    );
    return body.names ?? {};
  },
};

export default usersApi;
