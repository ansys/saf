/**
 * Tests for the ShareDialog component
 */
import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import ShareDialog from "../components/ShareDialog";
import { ProjectAccess } from "../types/project";

const mockFetch = global.fetch as jest.Mock;

const OWNER = "owner-0000-1111";
const VIEWER = "viewer-2222-3333";
const NEW_USER = "newuser-4444-5555";

const makeAccess = (extra: Partial<ProjectAccess> = {}): ProjectAccess => ({
  project_id: "p1",
  owner_id: OWNER,
  members: [
    { user_id: OWNER, role: "owner" },
    { user_id: VIEWER, role: "viewer" },
  ],
  holder_id: null,
  lock_acquired_at: null,
  last_write_at: null,
  version: 1,
  pending_requests: [],
  my_role: "owner",
  can_write: false,
  is_orphan: false,
  ...extra,
});

const json = (body: unknown, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  statusText: status === 200 ? "OK" : "Error",
  headers: { get: () => "application/json" },
  json: async () => body,
});

type Route = (url: string, init?: RequestInit) => unknown | undefined;

/** Route fetch calls by URL, in order of registration. */
const route = (...routes: Route[]) => {
  mockFetch.mockImplementation(async (url: string, init?: RequestInit) => {
    for (const r of routes) {
      const response = r(url, init);
      if (response !== undefined) return response;
    }
    throw new Error(`unexpected fetch ${init?.method ?? "GET"} ${url}`);
  });
};

const calls = () =>
  mockFetch.mock.calls.map(
    ([url, init]) => `${(init as RequestInit)?.method ?? "GET"} ${url}`,
  );

describe("ShareDialog", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  const baseRoutes = (access: ProjectAccess): Route[] => [
    (url, init) =>
      url === "/projects/p1/access" && (init?.method ?? "GET") === "GET"
        ? json(access)
        : undefined,
    (url) =>
      url === "/_saf/users/names"
        ? json({
            names: { [OWNER]: "Olivia Owner", [VIEWER]: "Victor Viewer" },
          })
        : undefined,
  ];

  it("lists the members with their names and roles", async () => {
    route(...baseRoutes(makeAccess()));
    render(<ShareDialog projectId="projects/p1" onClose={jest.fn()} />);

    expect(await screen.findByText("Olivia Owner")).toBeInTheDocument();
    expect(screen.getByText("Victor Viewer")).toBeInTheDocument();
    // only non-owners can be removed or promoted
    expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Make owner" })).toHaveLength(
      1,
    );
  });

  it("shows unknown user (first 8 chars…) for members the directory does not know", async () => {
    route(
      (url, init) =>
        url === "/projects/p1/access" && (init?.method ?? "GET") === "GET"
          ? json(makeAccess())
          : undefined,
      (url) => (url === "/_saf/users/names" ? json({ names: {} }) : undefined),
    );
    render(<ShareDialog projectId="projects/p1" onClose={jest.fn()} />);

    expect(
      await screen.findByText("unknown user (viewer-2…)"),
    ).toBeInTheDocument();
  });

  it("resolves the typed text, then shares with the resolved user id", async () => {
    let access = makeAccess();
    route(
      (url, init) => {
        if (url === "/projects/p1/access/members" && init?.method === "POST") {
          access = makeAccess({
            members: [...access.members, { user_id: NEW_USER, role: "viewer" }],
          });
          return json(access);
        }
      },
      (url) =>
        url.startsWith("/_saf/users/resolve?q=")
          ? json({ user_id: NEW_USER })
          : undefined,
      (url) =>
        url === "/_saf/users/names"
          ? json({
              names: {
                [OWNER]: "Olivia Owner",
                [VIEWER]: "Victor Viewer",
                [NEW_USER]: "Nina New",
              },
            })
          : undefined,
      (url, init) =>
        url === "/projects/p1/access" && (init?.method ?? "GET") === "GET"
          ? json(access)
          : undefined,
    );
    const onChanged = jest.fn();
    render(
      <ShareDialog
        projectId="projects/p1"
        onClose={jest.fn()}
        onChanged={onChanged}
      />,
    );
    await screen.findByText("Olivia Owner");

    fireEvent.change(screen.getByLabelText("E-mail or username"), {
      target: { value: "nina@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(await screen.findByText("Nina New")).toBeInTheDocument();
    const list = calls();
    const resolveAt = list.indexOf(
      "GET /_saf/users/resolve?q=nina%40example.com",
    );
    const shareAt = list.indexOf("POST /projects/p1/access/members");
    expect(resolveAt).toBeGreaterThan(-1);
    expect(shareAt).toBeGreaterThan(resolveAt);
    const shareCall = mockFetch.mock.calls[shareAt];
    expect(JSON.parse(shareCall[1].body)).toEqual({ user_id: NEW_USER });
    expect(onChanged).toHaveBeenCalled();
    expect(screen.getByLabelText("E-mail or username")).toHaveValue("");
  });

  it('shows No user found for "{text}" and does not share when the user is unknown', async () => {
    route(
      (url) =>
        url.startsWith("/_saf/users/resolve?q=")
          ? json({ error: "User not found" }, 404)
          : undefined,
      ...baseRoutes(makeAccess()),
    );
    render(<ShareDialog projectId="projects/p1" onClose={jest.fn()} />);
    await screen.findByText("Olivia Owner");

    fireEvent.change(screen.getByLabelText("E-mail or username"), {
      target: { value: "ghost" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(
      await screen.findByText('No user found for "ghost"'),
    ).toBeInTheDocument();
    expect(
      calls().some((c) => c.startsWith("POST /projects/p1/access/members")),
    ).toBe(false);
  });

  it("shows the server message when sharing fails", async () => {
    route(
      (url, init) =>
        url === "/projects/p1/access/members" && init?.method === "POST"
          ? json({ detail: "The project owner is already a member." }, 409)
          : undefined,
      (url) =>
        url.startsWith("/_saf/users/resolve?q=")
          ? json({ user_id: OWNER })
          : undefined,
      ...baseRoutes(makeAccess()),
    );
    render(<ShareDialog projectId="projects/p1" onClose={jest.fn()} />);
    await screen.findByText("Olivia Owner");

    fireEvent.change(screen.getByLabelText("E-mail or username"), {
      target: { value: "olivia" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(
      await screen.findByText("The project owner is already a member."),
    ).toBeInTheDocument();
  });

  it("Add is disabled while the input is empty", async () => {
    route(...baseRoutes(makeAccess()));
    render(<ShareDialog projectId="projects/p1" onClose={jest.fn()} />);
    await screen.findByText("Olivia Owner");
    expect(screen.getByRole("button", { name: "Add" })).toBeDisabled();
  });

  it("Remove unshares the member", async () => {
    let access = makeAccess();
    route(
      (url, init) => {
        if (
          url === `/projects/p1/access/members/${VIEWER}` &&
          init?.method === "DELETE"
        ) {
          access = makeAccess({ members: [access.members[0]] });
          return json(access);
        }
      },
      ...baseRoutes(access),
    );
    render(<ShareDialog projectId="projects/p1" onClose={jest.fn()} />);
    const row = (await screen.findByText("Victor Viewer")).closest("li")!;
    fireEvent.click(within(row).getByRole("button", { name: "Remove" }));

    await waitFor(() =>
      expect(calls()).toContain(`DELETE /projects/p1/access/members/${VIEWER}`),
    );
    await waitFor(() =>
      expect(screen.queryByText("Victor Viewer")).not.toBeInTheDocument(),
    );
  });

  it("Make owner transfers the ownership and closes the dialog", async () => {
    const onClose = jest.fn();
    const onChanged = jest.fn();
    route(
      (url, init) =>
        url === "/projects/p1/access:transfer-ownership" &&
        init?.method === "POST"
          ? json(makeAccess({ owner_id: VIEWER, my_role: "viewer" }))
          : undefined,
      ...baseRoutes(makeAccess()),
    );
    render(
      <ShareDialog
        projectId="projects/p1"
        onClose={onClose}
        onChanged={onChanged}
      />,
    );
    const row = (await screen.findByText("Victor Viewer")).closest("li")!;
    fireEvent.click(within(row).getByRole("button", { name: "Make owner" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(onChanged).toHaveBeenCalled();
    const call = mockFetch.mock.calls.find(
      ([url]) => url === "/projects/p1/access:transfer-ownership",
    )!;
    expect(JSON.parse(call[1].body)).toEqual({ user_id: VIEWER });
  });

  it("uses the users base URL for the directory and the API base URL for access", async () => {
    route(
      (url) =>
        url === "http://dash:8050/_saf/users/names"
          ? json({ names: { [OWNER]: "Olivia Owner" } })
          : undefined,
      (url) =>
        url === "http://glow:5678/projects/p1/access"
          ? json(makeAccess())
          : undefined,
    );
    render(
      <ShareDialog
        projectId="projects/p1"
        apiBaseUrl="http://glow:5678"
        usersApiBaseUrl="http://dash:8050"
        onClose={jest.fn()}
      />,
    );
    expect(await screen.findByText("Olivia Owner")).toBeInTheDocument();
  });

  describe("assign owner mode (super admin)", () => {
    it("resolves the user then assigns them as owner", async () => {
      const onChanged = jest.fn();
      const onClose = jest.fn();
      route(
        (url, init) =>
          url === "/projects/p1/access:assign-owner" && init?.method === "POST"
            ? json(makeAccess({ owner_id: NEW_USER, my_role: null }))
            : undefined,
        (url) =>
          url.startsWith("/_saf/users/resolve?q=")
            ? json({ user_id: NEW_USER })
            : undefined,
      );
      render(
        <ShareDialog
          projectId="projects/p1"
          mode="assignOwner"
          onClose={onClose}
          onChanged={onChanged}
        />,
      );
      fireEvent.change(screen.getByLabelText("E-mail or username"), {
        target: { value: "nina" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Assign owner" }));

      await waitFor(() => expect(onClose).toHaveBeenCalled());
      expect(onChanged).toHaveBeenCalled();
      const call = mockFetch.mock.calls.find(
        ([url]) => url === "/projects/p1/access:assign-owner",
      )!;
      expect(JSON.parse(call[1].body)).toEqual({ user_id: NEW_USER });
      // the admin is not a member: nothing else is fetched
      expect(calls().some((c) => c.endsWith("/projects/p1/access"))).toBe(
        false,
      );
    });
  });
});
