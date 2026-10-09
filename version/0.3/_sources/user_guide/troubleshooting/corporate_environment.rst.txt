.. _troubleshooting_corporate_environment:

Corporate environment
#####################

This section covers issues that appear only on machines managed by a corporate IT department, typically
because of a proxy server, a TLS-inspecting firewall, or a restrictive group policy.

These issues share a common characteristic: the solution works on an unmanaged developer machine and fails
on a corporate one, with error messages that point at the network rather than at the solution. If you are a
solution developer reproducing a customer issue, start here before investigating the solution code itself.


.. _troubleshooting_proxy_ssl_certificate:

SSL certificate error during installation
=========================================

**Problem**:
 When running ``saf install`` behind a corporate proxy or TLS-inspecting firewall, the installation fails with
 errors such as:

 .. code-block:: text

     All attempts to connect to files.pythonhosted.org failed.

 or:

 .. code-block:: text

     SSLCertVerificationError: certificate verify failed: unable to get local issuer certificate

**Cause**:
 Poetry does not use the OS certificate store. Even if ``pip`` works correctly in your environment, Poetry's
 internal download path for package files (from ``files.pythonhosted.org``) ignores the certificate configured
 via :envvar:`POETRY_CERTIFICATES_<SOURCE>_CERT`. This is a
 `known Poetry limitation <https://github.com/python-poetry/poetry/issues/1012>`_.

**Solution**:
 Set the :envvar:`REQUESTS_CA_BUNDLE` environment variable to point to your corporate CA certificate bundle
 **before** running ``saf install``:

 .. tab-set::

     .. tab-item:: Windows PowerShell

         .. tab-set::

             .. tab-item:: Current session

                 .. code-block:: powershell

                     $env:REQUESTS_CA_BUNDLE = "C:\path\to\corporate-ca-bundle.pem"
                     saf install <app_name> -f

             .. tab-item:: Persistent across sessions

                 .. code-block:: powershell

                     [Environment]::SetEnvironmentVariable("REQUESTS_CA_BUNDLE", "C:\path\to\corporate-ca-bundle.pem", "User")

     .. tab-item:: Linux/macOS

             .. code-block:: bash

                 export REQUESTS_CA_BUNDLE="/path/to/corporate-ca-bundle.pem"
                 saf install <app_name> -f

                 # To persist, add the export line to your shell profile (~/.bashrc, ~/.bash_profile, etc.)

 .. note::
     Ask your IT department for the corporate CA certificate file (PEM format). This is the same certificate
     that your browser or system uses to trust traffic through the corporate proxy.


.. _troubleshooting_proxy_startup_failure:

Desktop solution fails to start when a proxy is configured
==========================================================

**Problem**:
 On a machine where corporate proxy settings are configured system-wide, an installed desktop solution fails to
 start. Double-clicking the desktop shortcut or selecting the solution from the Start menu appears to do nothing:
 no window opens, no error dialog is displayed, and no message is shown to the end user. The solution starts
 correctly on machines without a proxy configuration.

**Cause**:
 There are two independent parts to this failure: why startup fails, and why it fails silently.

 *Why startup fails.* The orchestrator starts the solution services (solution API, solution UI, SAF Portal, and,
 depending on the configuration, the telemetry dashboard and the product instance manager) as local processes
 bound to the loopback interface, each on a port assigned at launch time. It then polls each service over HTTP
 until it reports healthy—for example ``http://127.0.0.1:<port>/health``.

 The HTTP client used for these health checks reads the standard proxy environment variables. When
 :envvar:`HTTP_PROXY` or :envvar:`HTTPS_PROXY` is set and the loopback address is not exempted, the health checks
 are sent to the corporate proxy instead of directly to the local service. The proxy cannot route a request back
 to a short-lived port on the machine that issued it, so every attempt fails.

 The orchestrator retries every 0.25 seconds until :envvar:`SAF_DESKTOP_HEALTH_CHECK_TIMEOUT` expires
 (25 seconds by default), then raises an error of the following form:

 .. code-block:: text

     RuntimeError: Error: unable to reach http://127.0.0.1:<port>/health

 Because a service never becomes healthy, the orchestrator shuts down every service it started and exits.

 *Why it fails silently.* The installer runs the solution with ``pythonw.exe`` so that no console window
 appears. Under ``pythonw.exe``, the standard output and standard error streams are discarded, so the error
 above is never displayed. The end user sees nothing at all.

 .. note::
     This is why the symptom is a silent failure rather than an error message, and why the same solution
     launched from a terminal (which does not use ``pythonw.exe``) reports the problem clearly.

**Diagnosis**:
 #. **Check whether proxy variables are set.**

    .. tab-set::

        .. tab-item:: Windows PowerShell

            .. code-block:: powershell

                echo $env:HTTP_PROXY
                echo $env:HTTPS_PROXY
                echo $env:NO_PROXY

        .. tab-item:: Linux/macOS

            .. code-block:: bash

                echo "$HTTP_PROXY $http_proxy"
                echo "$HTTPS_PROXY $https_proxy"
                echo "$NO_PROXY $no_proxy"

    If :envvar:`HTTP_PROXY` or :envvar:`HTTPS_PROXY` has a value and :envvar:`NO_PROXY` does not include the
    loopback address, this issue applies.

 #. **Read the orchestrator log.**

    The orchestrator writes a log file even when it runs under ``pythonw.exe``, so this is the most reliable
    source of evidence:

    .. tab-set::

        .. tab-item:: Windows

            .. code-block:: text

                %APPDATA%\ansys\glow\<solution-name>\orchestrator.log

        .. tab-item:: Linux

            .. code-block:: text

                $XDG_DATA_HOME/ansys/glow/<solution-name>/orchestrator.log

                # If XDG_DATA_HOME is not set:
                ~/.local/share/ansys/glow/<solution-name>/orchestrator.log

    Search the file for ``unable to reach``. A matching entry confirms that a service was started but could not
    be contacted.

    .. important::
        The log file is overwritten on every launch. Reproduce the failure first, then read the log without
        starting the solution again in between.

 #. **Confirm from the command line.**

    Launch the solution from a terminal as described in :ref:`deploy_desktop_check_installation`. Because a
    terminal launch uses ``python`` rather than ``pythonw.exe``, the error is printed directly.

**Solution**:
 Exempt the loopback interface from the proxy by adding it to :envvar:`NO_PROXY`. Choose one of the two methods
 below, then restart the solution.

 .. attention::
     List both ``127.0.0.1`` and ``localhost``. Entries in :envvar:`NO_PROXY` are matched against the host as
     written in the request URL, so neither value covers the other. Include ``::1`` as well to cover IPv6
     loopback.

 .. rubric:: Method 1: Solution-scoped ``.env`` file

 Add the following line to the ``.env`` file in the solution installation directory:

 .. code-block:: bash

     NO_PROXY=127.0.0.1,localhost,::1

 The ``.env`` file is located next to the solution definition, for example:

 .. code-block:: text

     C:\Program Files\ANSYS Inc\SAF Solutions\<solution-display-name> Solution\<version>\definitions\<solution-name>\.env

 This method affects only the solution, which makes it the preferred option when you must not alter machine-wide
 settings.

 .. warning::
     Values in the ``.env`` file **do not override variables that are already set in the environment**. If
     :envvar:`NO_PROXY` is already defined on the machine—even with a value that omits the loopback address—
     the entry in the ``.env`` file is ignored and the solution still fails to start. In that case, use Method 2
     instead, or extend the existing value rather than defining a new one.

 .. rubric:: Method 2: User-level environment variable

 Set :envvar:`NO_PROXY` for the user, which also applies to any other solution installed on the machine:

 .. tab-set::

     .. tab-item:: Windows PowerShell

         .. code-block:: powershell

             # Preserve any existing value and append the loopback entries
             $existing = [Environment]::GetEnvironmentVariable("NO_PROXY", "User")
             $value = if ($existing) { "$existing,127.0.0.1,localhost,::1" } else { "127.0.0.1,localhost,::1" }
             [Environment]::SetEnvironmentVariable("NO_PROXY", $value, "User")

         Close and reopen any terminal, then launch the solution again so that it picks up the new value.

     .. tab-item:: Linux/macOS

         .. code-block:: bash

             # Add to your shell profile (for example, ~/.bashrc or ~/.profile)
             export NO_PROXY="${NO_PROXY:+$NO_PROXY,}127.0.0.1,localhost,::1"
             export no_proxy="$NO_PROXY"

             # Reload your profile
             source ~/.bashrc

 .. note::
     If the proxy configuration is pushed by a group policy, a login script, or a proxy auto-configuration (PAC)
     file, the variables may be reapplied at every logon and overwrite your change. Ask your IT department to add
     the loopback exemption to the managed configuration so that it persists.


Restrictive group policy
========================

Corporate group policies can also prevent the Windows Long Path setting from being enabled, which the installer
validates by default.

.. seealso::

    For the available workaround, see :ref:`bypassing-long-path-check`.
