/**
 * Tests for the access-control behaviour of ProjectsDashboard
 */
import React, { useState } from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import ProjectsDashboard from "../components/ProjectsDashboard";
import { Project } from "../types/project";

const mockFetch = global.fetch as jest.Mock;

const ME = "me-0000-1111-2222";
const OTHER = "other-aaaa-bbbb-cccc";

const json = (body: unknown, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  statusText: status === 200 ? "OK" : "Error",
  headers: { get: () => "application/json" },
  json: async () => body,
});

const page = (projects: Project[]) => ({
  projects,
  current_page: 1,
  total_pages: 1,
  page_size: 10,
  total_projects: projects.length,
});

const plain: Project = { name: "projects/p1", display_name: "Project 1" };
const viewerProject: Project = {
  name: "projects/p1",
  display_name: "Project 1",
  access: {
    owner_id: OTHER,
    holder_id: null,
    my_role: "viewer",
    pending_request_count: 0,
    member_ids: [OTHER, ME],
  },
};

type Handler = (url: string, init?: RequestInit) => unknown | undefined;

const serve = (...handlers: Handler[]) => {
  mockFetch.mockImplementation(async (url: string, init?: RequestInit) => {
    for (const h of handlers) {
      const r = h(url, init);
      if (r !== undefined) return r;
    }
    throw new Error(`unexpected fetch ${init?.method ?? "GET"} ${url}`);
  });
};

const method = (init?: RequestInit) => init?.method ?? "GET";

const meHandler =
  (is_super_admin = false): Handler =>
  (url) =>
    url === "/access/me" ? json({ user_id: ME, is_super_admin }) : undefined;

const namesHandler: Handler = (url) =>
  url === "/_saf/users/names"
    ? json({ names: { [OTHER]: "Olivia Owner", [ME]: "Me Myself" } })
    : undefined;

const listUrls = () =>
  mockFetch.mock.calls
    .map(([url]) => url as string)
    .filter((url) => url.startsWith("/projects?") || url === "/projects");

const Harness: React.FC<{ initialProps?: Record<string, unknown> }> = ({
  initialProps = {},
}) => {
  const [state, setState] = useState<Record<string, unknown>>({
    id: "dashboard",
    pageSize: 10,
    ...initialProps,
  });
  const setProps = (patch: Record<string, unknown>) =>
    setState((prev) => ({ ...prev, ...patch }));
  const Component = ProjectsDashboard as unknown as React.FC<
    Record<string, unknown>
  >;
  return <Component {...state} setProps={setProps} />;
};

describe("ProjectsDashboard access control", () => {
  let openSpy: jest.SpyInstance;

  beforeEach(() => {
    mockFetch.mockReset();
    openSpy = jest.spyOn(globalThis, "open").mockImplementation(() => null);
  });

  afterEach(() => {
    openSpy.mockRestore();
    jest.useRealTimers();
  });

  it("feature off: only the list is fetched and no access UI is shown", async () => {
    serve((url) =>
      url.startsWith("/projects") ? json(page([plain])) : undefined,
    );
    render(<Harness />);

    await screen.findByText("Project 1");
    expect(
      screen.queryByRole("button", { name: /copy my user id/i }),
    ).toBeNull();
    expect(screen.queryByLabelText(/without owner/i)).toBeNull();
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("feature on: shows Copy my user id and copies getMe().user_id", async () => {
    const writeText = jest.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    serve(
      (url) =>
        url.startsWith("/projects?") ? json(page([viewerProject])) : undefined,
      meHandler(),
      namesHandler,
    );
    render(<Harness />);

    const button = await screen.findByRole("button", {
      name: /copy my user id/i,
    });
    fireEvent.click(button);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(ME));
  });

  it("feature on, no projects: still probes /access/me so the user can copy their id", async () => {
    serve(
      (url) => (url.startsWith("/projects?") ? json(page([])) : undefined),
      meHandler(),
    );
    render(<Harness />);
    expect(
      await screen.findByRole("button", { name: /copy my user id/i }),
    ).toBeInTheDocument();
  });

  it("feature off, no projects: a failing /access/me probe is ignored", async () => {
    serve(
      (url) => (url.startsWith("/projects?") ? json(page([])) : undefined),
      (url) =>
        url === "/access/me" ? json({ detail: "Not Found" }, 404) : undefined,
    );
    render(<Harness />);
    await waitFor(() =>
      expect(mockFetch.mock.calls.map(([u]) => u)).toContain("/access/me"),
    );
    expect(
      screen.queryByRole("button", { name: /copy my user id/i }),
    ).toBeNull();
  });

  it("table view shows resolved owner names", async () => {
    serve(
      (url) =>
        url.startsWith("/projects?") ? json(page([viewerProject])) : undefined,
      meHandler(),
      namesHandler,
    );
    render(<Harness />);
    await screen.findByText("Project 1");
    fireEvent.click(screen.getByRole("button", { name: /table view/i }));
    expect(await screen.findByText("Olivia Owner")).toBeInTheDocument();
    const names = mockFetch.mock.calls.find(
      ([url]) => url === "/_saf/users/names",
    )!;
    expect(JSON.parse(names[1].body).user_ids).toEqual([OTHER]);
  });

  describe("old-schema project (HTTP 422 on open)", () => {
    const openUnupgraded = (canWrite: boolean) => {
      serve(
        (url, init) =>
          url === "/projects/p1" && method(init) === "GET"
            ? json({ detail: "needs upgrade" }, 422)
            : undefined,
        (url) =>
          url === "/projects/p1/access"
            ? json({
                project_id: "p1",
                owner_id: OTHER,
                members: [],
                holder_id: canWrite ? ME : null,
                lock_acquired_at: null,
                last_write_at: null,
                version: 1,
                pending_requests: [],
                my_role: "viewer",
                can_write: canWrite,
                is_orphan: false,
              })
            : undefined,
        (url) =>
          url.startsWith("/projects?")
            ? json(page([viewerProject]))
            : undefined,
        meHandler(),
        namesHandler,
      );
    };

    it("explains who can upgrade instead of offering the upgrade to a user without write access", async () => {
      openUnupgraded(false);
      render(<Harness />);
      fireEvent.click(
        await screen.findByRole("article", { name: /open project/i }),
      );

      expect(
        await screen.findByText(
          "This project must be upgraded by the person editing it (or start editing it first).",
        ),
      ).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Upgrade" })).toBeNull();
      expect(mockFetch.mock.calls.some(([url]) => /:upgrade/.test(url))).toBe(
        false,
      );
    });

    it("offers the upgrade to the user who can write", async () => {
      openUnupgraded(true);
      render(<Harness />);
      fireEvent.click(
        await screen.findByRole("article", { name: /open project/i }),
      );

      expect(
        await screen.findByRole("button", { name: "Upgrade" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByText(/must be upgraded by the person editing it/),
      ).toBeNull();
    });
  });

  it("menu action: Start editing acquires the lock then reloads the list", async () => {
    serve(
      (url, init) =>
        url === "/projects/p1/lock:acquire" && method(init) === "POST"
          ? json({ project_id: "p1" })
          : undefined,
      (url) =>
        url.startsWith("/projects?") ? json(page([viewerProject])) : undefined,
      meHandler(),
      namesHandler,
    );
    render(<Harness />);
    await screen.findByText("Project 1");
    await waitFor(() =>
      expect(mockFetch.mock.calls.map(([u]) => u)).toContain("/access/me"),
    );

    fireEvent.click(screen.getByRole("button", { name: /more actions/i }));
    const before = listUrls().length;
    fireEvent.click(screen.getByRole("menuitem", { name: "Start editing" }));

    await waitFor(() =>
      expect(
        mockFetch.mock.calls.some(
          ([url, init]) =>
            url === "/projects/p1/lock:acquire" && method(init) === "POST",
        ),
      ).toBe(true),
    );
    await waitFor(() => expect(listUrls().length).toBeGreaterThan(before));
  });

  it("menu action: a conflict from the server is shown as an error notification", async () => {
    serve(
      (url, init) =>
        url === "/projects/p1/lock:acquire" && method(init) === "POST"
          ? json({ detail: "Another user holds the write lock" }, 409)
          : undefined,
      (url) =>
        url.startsWith("/projects?") ? json(page([viewerProject])) : undefined,
      meHandler(),
      namesHandler,
    );
    render(<Harness />);
    await screen.findByText("Project 1");
    await waitFor(() =>
      expect(mockFetch.mock.calls.map(([u]) => u)).toContain("/access/me"),
    );
    fireEvent.click(screen.getByRole("button", { name: /more actions/i }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Start editing" }));

    expect(
      await screen.findByText(/Another user holds the write lock/),
    ).toBeInTheDocument();
  });

  describe("super admin", () => {
    it("can restrict the list to the projects without owner", async () => {
      serve(
        (url) =>
          url.startsWith("/projects?")
            ? json(page([viewerProject]))
            : undefined,
        meHandler(true),
        namesHandler,
      );
      render(<Harness />);
      const toggle = await screen.findByLabelText(
        "Only projects without owner",
      );
      expect(listUrls().every((u) => !u.includes("orphans_only"))).toBe(true);

      fireEvent.click(toggle);

      await waitFor(() =>
        expect(listUrls().some((u) => u.includes("orphans_only=true"))).toBe(
          true,
        ),
      );
    });

    it("regular users do not get the toggle", async () => {
      serve(
        (url) =>
          url.startsWith("/projects?")
            ? json(page([viewerProject]))
            : undefined,
        meHandler(false),
        namesHandler,
      );
      render(<Harness />);
      await screen.findByRole("button", { name: /copy my user id/i });
      expect(screen.queryByLabelText("Only projects without owner")).toBeNull();
    });
  });

  describe("periodic refresh", () => {
    it("reloads the list every 30 s while visible, when access control is on", async () => {
      jest.useFakeTimers();
      serve(
        (url) =>
          url.startsWith("/projects?")
            ? json(page([viewerProject]))
            : undefined,
        meHandler(),
        namesHandler,
      );
      render(<Harness />);
      await act(async () => {
        await jest.advanceTimersByTimeAsync(0);
      });
      await screen.findByText("Project 1");
      const initial = listUrls().length;

      await act(async () => {
        await jest.advanceTimersByTimeAsync(30_000);
      });
      expect(listUrls().length).toBe(initial + 1);

      // the list stays on screen during a background refresh
      expect(screen.queryByText("Loading projects...")).toBeNull();
    });

    it("does not poll when access control is off", async () => {
      jest.useFakeTimers();
      serve((url) =>
        url.startsWith("/projects?") ? json(page([plain])) : undefined,
      );
      render(<Harness />);
      await act(async () => {
        await jest.advanceTimersByTimeAsync(0);
      });
      await screen.findByText("Project 1");
      await act(async () => {
        await jest.advanceTimersByTimeAsync(90_000);
      });
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });
  });
});
