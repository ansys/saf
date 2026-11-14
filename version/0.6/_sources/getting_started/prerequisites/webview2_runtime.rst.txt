.. _prerequisites_webview2_runtime:

WebView2 runtime
################

.. note::

   WebView2 runtime is a **Windows-only** prerequisite. If you are developing on another platform,
   you can skip this section.

SAF SDK relies on PyWebView to create desktop applications with web technologies.
PyWebView relies on the WebView2 runtime, a component that allows applications to embed web content using
Microsoft Edge (Chromium) as the rendering engine, to function correctly.

WebView2 runtime is not always included with Windows by default, so you need to install it separately to ensure
that your SAF SDK applications can render the UI properly.

Step 1: Check if WebView2 runtime is installed
***********************************************

Open a PowerShell terminal and run the following command to check if the WebView2 runtime is already installed:

.. code-block:: powershell

   Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" -Name "pv" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty pv

If the WebView2 runtime is installed, this command returns the version number (for example, ``130.0.2849.56``).
If nothing is returned or an error occurs, the runtime is not installed and you should proceed to Step 2.

Step 2: Install WebView2 runtime
*********************************

To install WebView2 runtime, follow the instructions on the official `Microsoft WebView2 documentation <https://developer.microsoft.com/en-us/microsoft-edge/webview2/>`_.
