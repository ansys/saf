/**
 * Tests for the ownership / write-lock integration of the projects table and cards
 */
import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import ProjectsTable from "../components/ProjectsTable";
import ProjectsList from "../components/ProjectsList";
import {
  AccessMe,
  Project,
  ProjectAccessSummary,
  ProjectRole,
} from "../types/project";

const ME = "me-0000-1111-2222";
const OTHER = "other-aaaa-bbbb-cccc";
const THIRD = "third-dddd-eeee-ffff";

const me: AccessMe = { user_id: ME, is_super_admin: false };
const admin: AccessMe = { user_id: "admin-0000-1111", is_super_admin: true };

const makeProject = (
  access: Partial<ProjectAccessSummary> | null | undefined,
  name = "projects/p1",
): Project => ({
  name,
  display_name: `Project ${name}`,
  ...(access === undefined
    ? {}
    : {
        access:
          access === null
            ? null
            : {
                owner_id: null,
                holder_id: null,
                my_role: null,
                pending_request_count: 0,
                ...access,
              },
      }),
});

const handlers = () => ({
  onEdit: jest.fn(),
  onDelete: jest.fn(),
  onExport: jest.fn(),
  onCardClick: jest.fn(),
  onFavoriteToggle: jest.fn(),
  onInfo: jest.fn(),
  onAccessAction: jest.fn(),
  favoriteIds: [] as string[],
});

const menuLabels = () =>
  screen.getAllByRole("menuitem").map((item) => item.textContent);

const openMenu = (index = 0) => {
  fireEvent.click(
    screen.getAllByRole("button", { name: /more actions/i })[index],
  );
};

type ViewCase = [string, React.ComponentType<any>];
const views: ViewCase[] = [
  ["table", ProjectsTable],
  ["cards", ProjectsList],
];

describe.each(views)("access menu (%s view)", (_name, View) => {
  const renderView = (
    project: Project,
    accessMe: AccessMe | null = me,
    extra: Record<string, unknown> = {},
  ) => {
    const props = handlers();
    render(
      <View
        projects={[project]}
        {...props}
        accessMe={accessMe}
        userNames={{}}
        {...extra}
      />,
    );
    return props;
  };

  it("feature off (access == null): exactly today's items", () => {
    for (const project of [makeProject(undefined), makeProject(null)]) {
      const { unmount } = render(
        <View projects={[project]} {...handlers()} accessMe={me} />,
      );
      openMenu();
      expect(menuLabels()).toEqual(["Edit", "Export", "Delete"]);
      unmount();
    }
  });

  it("owner: Share…, Export, Delete", () => {
    renderView(makeProject({ owner_id: ME, my_role: "owner" }));
    openMenu();
    expect(menuLabels()).toEqual(["Share…", "Export", "Delete"]);
  });

  it("owner: adds Take over lock when another user holds the lock", () => {
    renderView(
      makeProject({ owner_id: ME, my_role: "owner", holder_id: OTHER }),
    );
    openMenu();
    expect(menuLabels()).toEqual([
      "Share…",
      "Take over lock",
      "Export",
      "Delete",
    ]);
  });

  it("owner: adds Approve and Deny when a request is pending", () => {
    renderView(
      makeProject({
        owner_id: ME,
        my_role: "owner",
        holder_id: OTHER,
        pending_request_count: 1,
      }),
    );
    openMenu();
    expect(menuLabels()).toEqual([
      "Share…",
      "Take over lock",
      "Approve",
      "Deny",
      "Export",
      "Delete",
    ]);
  });

  it("owner holding the lock can release it", () => {
    renderView(makeProject({ owner_id: ME, my_role: "owner", holder_id: ME }));
    openMenu();
    expect(menuLabels()).toEqual([
      "Share…",
      "Release lock",
      "Export",
      "Delete",
    ]);
  });

  it("holder: Release lock", () => {
    renderView(
      makeProject({ owner_id: OTHER, my_role: "viewer", holder_id: ME }),
    );
    openMenu();
    expect(menuLabels()).toEqual(["Release lock"]);
  });

  it("holder: Release lock, Approve, Deny when a request is pending", () => {
    renderView(
      makeProject({
        owner_id: OTHER,
        my_role: "viewer",
        holder_id: ME,
        pending_request_count: 2,
      }),
    );
    openMenu();
    expect(menuLabels()).toEqual(["Release lock", "Approve", "Deny"]);
  });

  it("viewer, lock free: Start editing", () => {
    renderView(makeProject({ owner_id: OTHER, my_role: "viewer" }));
    openMenu();
    expect(menuLabels()).toEqual(["Start editing"]);
  });

  it("viewer, lock held by someone else: Request write access", () => {
    renderView(
      makeProject({ owner_id: OTHER, my_role: "viewer", holder_id: THIRD }),
    );
    openMenu();
    expect(menuLabels()).toEqual(["Request write access"]);
  });

  it("viewer with a pending request: Withdraw request", () => {
    renderView(
      makeProject({
        owner_id: OTHER,
        my_role: "viewer",
        holder_id: THIRD,
        pending_request_count: 1,
      }),
      me,
      { myPendingRequests: { "projects/p1": "req-1" } },
    );
    openMenu();
    expect(menuLabels()).toEqual(["Withdraw request"]);
  });

  it("super admin who is not a member: Assign owner…, Force release, Delete", () => {
    renderView(
      makeProject({ owner_id: OTHER, my_role: null, holder_id: THIRD }),
      admin,
    );
    openMenu();
    expect(menuLabels()).toEqual(["Assign owner…", "Force release", "Delete"]);
  });

  it("menu items call back with the action and the project", () => {
    const project = makeProject({
      owner_id: ME,
      my_role: "owner",
      holder_id: OTHER,
    });
    const props = renderView(project);
    openMenu();
    fireEvent.click(screen.getByRole("menuitem", { name: "Take over lock" }));
    expect(props.onAccessAction).toHaveBeenCalledWith("takeOver", project);
    openMenu();
    fireEvent.click(screen.getByRole("menuitem", { name: "Share…" }));
    expect(props.onAccessAction).toHaveBeenCalledWith("share", project);
    openMenu();
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete" }));
    expect(props.onDelete).toHaveBeenCalledWith("projects/p1");
  });

  describe("pending request badge", () => {
    const pending = (role: ProjectRole, holder: string | null, owner = OTHER) =>
      makeProject({
        owner_id: owner,
        my_role: role,
        holder_id: holder,
        pending_request_count: 3,
      });

    it("is shown to the owner", () => {
      renderView(pending("owner", OTHER, ME));
      expect(
        screen.getByLabelText("3 pending write requests"),
      ).toHaveTextContent("3");
    });

    it("is shown to the holder", () => {
      renderView(pending("viewer", ME));
      expect(
        screen.getByLabelText("3 pending write requests"),
      ).toHaveTextContent("3");
    });

    it("is not shown to other viewers", () => {
      renderView(pending("viewer", THIRD));
      expect(screen.queryByLabelText(/pending write request/)).toBeNull();
    });

    it("is not shown when nothing is pending", () => {
      renderView(makeProject({ owner_id: ME, my_role: "owner" }));
      expect(screen.queryByLabelText(/pending write request/)).toBeNull();
    });
  });
});

describe("ProjectsTable access columns", () => {
  it("does not render Owner / Editing now columns when access is absent", () => {
    render(
      <ProjectsTable
        projects={[makeProject(undefined), makeProject(null, "projects/p2")]}
        {...handlers()}
      />,
    );
    expect(screen.queryByText("Owner")).toBeNull();
    expect(screen.queryByText("Editing now")).toBeNull();
    expect(screen.queryByLabelText("Locked")).toBeNull();
  });

  it("renders Owner / Editing now columns after Name when access is present", () => {
    render(
      <ProjectsTable
        projects={[
          makeProject({ owner_id: OTHER, my_role: "viewer", holder_id: ME }),
        ]}
        {...handlers()}
        accessMe={me}
        userNames={{ [OTHER]: "Olivia Owner", [ME]: "Me Myself" }}
      />,
    );
    const headers = screen
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    const nameIndex = headers.indexOf("Name");
    expect(headers[nameIndex + 1]).toBe("Owner");
    expect(headers[nameIndex + 2]).toBe("Editing now");

    const row = screen.getAllByRole("row")[1];
    expect(within(row).getByText("Olivia Owner")).toBeInTheDocument();
    expect(within(row).getByText("Me Myself")).toBeInTheDocument();
    expect(within(row).getByLabelText("Locked")).toBeInTheDocument();
  });

  it("shows unknown user (first 8 chars…) when a name cannot be resolved", () => {
    render(
      <ProjectsTable
        projects={[
          makeProject({
            owner_id: "0123456789abcdef",
            my_role: "viewer",
            holder_id: "fedcba9876543210",
          }),
        ]}
        {...handlers()}
        accessMe={me}
        userNames={{}}
      />,
    );
    expect(screen.getByText("unknown user (01234567…)")).toBeInTheDocument();
    expect(screen.getByText("unknown user (fedcba98…)")).toBeInTheDocument();
  });

  it("shows no lock and an empty editor when nobody holds the lock", () => {
    render(
      <ProjectsTable
        projects={[makeProject({ owner_id: OTHER, my_role: "viewer" })]}
        {...handlers()}
        accessMe={me}
        userNames={{ [OTHER]: "Olivia" }}
      />,
    );
    expect(screen.queryByLabelText("Locked")).toBeNull();
  });

  it("marks projects without owner", () => {
    render(
      <ProjectsTable
        projects={[makeProject({ owner_id: null, my_role: null })]}
        {...handlers()}
        accessMe={admin}
      />,
    );
    expect(screen.getByText("No owner")).toBeInTheDocument();
  });
});
