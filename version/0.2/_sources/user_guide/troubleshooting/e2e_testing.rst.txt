.. _troubleshooting_e2e_testing:

End-to-end testing
##################

This section covers common issues encountered when running the end-to-end (E2E) test
suite of a solution. See :ref:`test_e2e` for a description of the suite itself.

* **SAF CLI not found:** run ``saf --version`` in the pytest environment or set
  ``SAF_EXECUTABLE``.
* **Installer not found:** update the expected filename in
  ``_get_installer_path``.
* **Shortcut not found:** update the solution display name and platform-specific
  desktop path.
* **API/UI timeout:** check the URL patterns and platform-specific Glow log
  directory used by ``running_examples``.
* **No pages discovered:** inspect the rendered DOM and update the navigation
  selectors or group detection helpers.
* **Linux launch failure:** install ``gtk-launch`` and ``xvfb-run`` or replace
  the Linux launcher with the solution's supported mechanism.
* **Chrome startup failure:** inspect the ChromeDriver log named in the pytest
  error. The fixture uses a fresh temporary Chrome profile for each retry.
* **Dependency verification failure:** compare the ``saf install`` dependency
  groups with the groups reported by ``poetry show`` and check that the
  solution's lock file is current.
* **Processes remain after pytest:** verify that the launcher teardown stops the
  parent and all child processes.
