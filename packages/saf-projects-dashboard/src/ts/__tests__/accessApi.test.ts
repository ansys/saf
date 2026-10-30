/**
 * Tests for the access control API clients (accessApi, usersApi)
 */
import { accessApi, createAccessApi } from "../api/accessApi";
import { ApiError, projectsApi } from "../api/projectsApi";
import { usersApi } from "../api/usersApi";

const mockFetch = global.fetch as jest.Mock;

const jsonResponse = (body: unknown, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  statusText: status === 200 ? "OK" : "Error",
  headers: { get: () => "application/json" },
  json: async () => body,
});

describe("accessApi", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }));
  });

  const lastCall = () => mockFetch.mock.calls[mockFetch.mock.calls.length - 1];

  it("getMe: GET /access/me", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ user_id: "u1", is_super_admin: false }),
    );
    const me = await accessApi.getMe();
    expect(lastCall()[0]).toBe("/access/me");
    expect(lastCall()[1]).toMatchObject({ method: "GET" });
    expect(me).toEqual({ user_id: "u1", is_super_admin: false });
  });

  it("prepends the base URL and drops its trailing slash", async () => {
    await accessApi.getMe("http://glow:5678/");
    expect(lastCall()[0]).toBe("http://glow:5678/access/me");
  });

  it.each([
    ["getAccess", (id: string) => accessApi.getAccess(id), "GET", "/access"],
    ["acquire", (id: string) => accessApi.acquire(id), "POST", "/lock:acquire"],
    ["release", (id: string) => accessApi.release(id), "POST", "/lock:release"],
    [
      "takeOver",
      (id: string) => accessApi.takeOver(id),
      "POST",
      "/lock:take-over",
    ],
    [
      "forceRelease",
      (id: string) => accessApi.forceRelease(id),
      "POST",
      "/lock:force-release",
    ],
    [
      "requestWrite",
      (id: string) => accessApi.requestWrite(id),
      "POST",
      "/write-requests",
    ],
  ])("%s uses %s %s", async (_name, call, method, suffix) => {
    await call("projects/p1");
    expect(lastCall()[0]).toBe(`/projects/p1${suffix}`);
    expect(lastCall()[1]).toMatchObject({ method });
  });

  it("accepts project ids with or without the projects/ prefix", async () => {
    await accessApi.getAccess("p1");
    expect(lastCall()[0]).toBe("/projects/p1/access");
    await accessApi.getAccess("projects/p1");
    expect(lastCall()[0]).toBe("/projects/p1/access");
  });

  it("share: POST members with the user id", async () => {
    await accessApi.share("projects/p1", "u2");
    expect(lastCall()[0]).toBe("/projects/p1/access/members");
    expect(lastCall()[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ user_id: "u2" }),
    });
  });

  it("unshare: DELETE the member, URL-encoding the user id", async () => {
    await accessApi.unshare("projects/p1", "a b/c");
    expect(lastCall()[0]).toBe("/projects/p1/access/members/a%20b%2Fc");
    expect(lastCall()[1]).toMatchObject({ method: "DELETE" });
  });

  it("transferOwnership: POST access:transfer-ownership", async () => {
    await accessApi.transferOwnership("projects/p1", "u2");
    expect(lastCall()[0]).toBe("/projects/p1/access:transfer-ownership");
    expect(lastCall()[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ user_id: "u2" }),
    });
  });

  it("assignOwner: POST access:assign-owner", async () => {
    await accessApi.assignOwner("projects/p1", "u2");
    expect(lastCall()[0]).toBe("/projects/p1/access:assign-owner");
    expect(lastCall()[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ user_id: "u2" }),
    });
  });

  it.each([
    ["approve", ":approve"],
    ["deny", ":deny"],
    ["withdraw", ":withdraw"],
  ] as const)("%s: POST write-requests/{id}%s", async (name, suffix) => {
    await accessApi[name]("projects/p1", "r1");
    expect(lastCall()[0]).toBe(`/projects/p1/write-requests/r1${suffix}`);
    expect(lastCall()[1]).toMatchObject({ method: "POST" });
  });

  it("throws an ApiError carrying the status and the server detail", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ detail: "Locked by someone" }, 423),
    );
    await expect(accessApi.acquire("projects/p1")).rejects.toMatchObject({
      name: "ApiError",
      status: 423,
      message: "Locked by someone",
    });
    mockFetch.mockResolvedValueOnce(jsonResponse({ detail: "x" }, 409));
    await expect(accessApi.acquire("projects/p1")).rejects.toBeInstanceOf(
      ApiError,
    );
  });

  it("createAccessApi binds the base URL", async () => {
    const api = createAccessApi("http://glow:1");
    await api.release("projects/p1");
    expect(lastCall()[0]).toBe("http://glow:1/projects/p1/lock:release");
  });
});

describe("projectsApi.listProjects orphansOnly", () => {
  it("sends orphans_only=true", async () => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValueOnce(jsonResponse({ projects: [] }));
    await projectsApi.listProjects(1, 10, { orphansOnly: true });
    expect(mockFetch.mock.calls[0][0]).toBe(
      "/projects?page=1&page_size=10&orphans_only=true",
    );
  });
});

describe("usersApi", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("resolve: GET /_saf/users/resolve?q= and returns the user id", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ user_id: "u9" }));
    const id = await usersApi.resolve("bob@example.com & co");
    expect(mockFetch.mock.calls[0][0]).toBe(
      "/_saf/users/resolve?q=bob%40example.com+%26+co",
    );
    expect(mockFetch.mock.calls[0][1]).toMatchObject({ method: "GET" });
    expect(id).toBe("u9");
  });

  it("resolve: returns null on 404", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ error: "User not found" }, 404),
    );
    expect(await usersApi.resolve("nobody")).toBeNull();
  });

  it("resolve: throws on other failures (directory unavailable)", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ error: "User directory unavailable" }, 502),
    );
    await expect(usersApi.resolve("bob")).rejects.toMatchObject({
      status: 502,
    });
  });

  it("resolve uses the users base URL", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ user_id: "u9" }));
    await usersApi.resolve("bob", "http://dash:8050");
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://dash:8050/_saf/users/resolve?q=bob",
    );
  });

  it("names: POST /_saf/users/names and returns the names map", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ names: { u1: "Alice" } }));
    const names = await usersApi.names(["u1", "u2"]);
    expect(mockFetch.mock.calls[0][0]).toBe("/_saf/users/names");
    expect(mockFetch.mock.calls[0][1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ user_ids: ["u1", "u2"] }),
    });
    expect(names).toEqual({ u1: "Alice" });
  });

  it("names: does not call the server for an empty list", async () => {
    expect(await usersApi.names([])).toEqual({});
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
