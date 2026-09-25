.. _troubleshooting_installation:

Installation
############

This section covers common issues and solutions related to the installation of a solution application built with SAF.

.. seealso::

    For the installation procedure itself, see :ref:`ug-install`. If the installation fails with an SSL
    certificate error, see :ref:`troubleshooting_proxy_ssl_certificate`.


Installation fails due to authentication issues
===============================================

**Problem**:
 When installing the solution using the ``saf install`` command, you get an error message indicating that the
 installation failed due to authentication issues.

**Solution**:
 There are several possible causes for this issue. To resolve it, follow these steps:

 #. **Verify environment variables**:

    Ensure that your PyPI access tokens are correctly configured. For guidance on obtaining and configuring credentials for private sources, see
    :ref:`user_guide_install_manage_private_sources`.

    .. important::

        If you need to set or update the environment variables, note that you will need to close all your VS Code
        instances and open a new one to ensure that the changes take effect. A good practice is to print the
        environment variables again in the new terminal to confirm that they are set correctly.

 #. **Clear the Poetry cache and configuration**:

    See :ref:`troubleshooting_clear_poetry_cache`.

 #. **Verify repository configuration**:

    Open the ``pyproject.toml`` file in the solution directory and check which private repository is declared
    under ``[tool.poetry.source]``. Identify which one it is from the source name and follow :ref:`user_guide_install_manage_private_sources` to properly
    configure the required environment variables.

 #. **Check environment variable conflicts**:

    Check your user and system environment variables to ensure that there are no conflicting settings with the ones in the ``.env`` file.


401 client error
================

**Problem**:
 When running ``saf install``, you get a 401 client error, even if your token is valid and correctly configured.

**Cause**:
 Stale credentials or cached metadata in the Poetry configuration take precedence over your current, valid token.

**Solution**:
 #. Rerun the install command with the ``-f`` flag, which removes the virtual environment and cached data:

    .. code-block:: bash

        saf install <app_name> -f

 #. If the error persists, clear the Poetry configuration and cache manually as described in
    :ref:`troubleshooting_clear_poetry_cache`, then run the command again.


Network issues
==============

**Problem**:
 When running ``saf install``, you get network-related errors, such as:

 .. code-block:: text

     ERROR: Could not find a version that satisfies the requirement

**Solution**:
 Check your internet connection and proxy settings. For private PyAnsys packages, verify that
 :envvar:`POETRY_HTTP_BASIC_<SOURCE_NAME>_PASSWORD` is set correctly for each required source.


Workspace clean-up fails with a permission error
================================================

**Problem**:
 When running ``saf install`` with the ``-f`` or ``-F`` option, the command fails with a permission error.

**Cause**:
 The command tries to delete the virtual environment that is currently active.

**Solution**:
 Deactivate the virtual environment before running ``saf install`` with the ``-f`` or ``-F`` option.


PowerShell execution policy blocks virtual environment activation
=================================================================

**Problem**:
 When activating a virtual environment in PowerShell (for example, running ``.venv\Scripts\Activate.ps1``), you
 get an error similar to:

 .. code-block:: powershell

     .venv\Scripts\Activate.ps1 cannot be loaded because running scripts is disabled on this system.

**Cause**:
 This is a common issue on Windows where the default PowerShell execution policy (``Restricted``) prevents
 running ``.ps1`` scripts, including virtual environment activation scripts.

**Solution**:
 #. Open PowerShell as Administrator and run the following command to allow locally created and remote signed
    scripts to execute:

    .. code-block:: powershell

        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

 #. Close and reopen PowerShell.

 You should now be able to activate your virtual environment without errors.


.. _troubleshooting_clear_poetry_cache:

Clear the Poetry cache and configuration
===========================================

Several installation failures are caused by stale Poetry credentials or cached metadata. To reset them, delete
the ``config.toml`` and ``auth.toml`` files and the Poetry cache directory:

.. tab-set::

    .. tab-item:: Windows PowerShell

        .. code-block:: powershell

            Remove-Item "$env:APPDATA\pypoetry\config.toml" -ErrorAction SilentlyContinue
            Remove-Item "$env:APPDATA\pypoetry\auth.toml" -ErrorAction SilentlyContinue
            Remove-Item "$env:LOCALAPPDATA\pypoetry\cache" -Recurse -Force -ErrorAction SilentlyContinue

    .. tab-item:: Windows Command

        .. code-block:: batch

            del "%APPDATA%\pypoetry\config.toml" 2>nul
            del "%APPDATA%\pypoetry\auth.toml" 2>nul
            rmdir /s /q "%LOCALAPPDATA%\pypoetry\cache" 2>nul

    .. tab-item:: Linux/UNIX

        .. code-block:: bash

            rm -f ~/.config/pypoetry/config.toml
            rm -f ~/.config/pypoetry/auth.toml
            rm -rf ~/.cache/pypoetry

After clearing the cache, rerun the installation with the ``-f`` option so that the environment is recreated
from scratch:

.. code-block:: bash

    saf install <app_name> -f
