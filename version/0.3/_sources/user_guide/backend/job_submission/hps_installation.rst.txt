.. _hps_installation:

Install and start HPS
#####################

Prerequisites
=============

Set GitHub token
------------------

To download HPS core services from the GitHub Container Registry, you need a GitHub Personal Access Token (PAT) with the
appropriate scopes.

#. Create a Personal Access Token (PAT) in `GitHub <https://github.com/settings/tokens>`_.
   Note it down immediately after creating it as you will not be able to see it again.

#. Click on the token name, select the ``repo`` and **write:packages** scopes, and update the token.

#. Click on **Configure SSO** and authorize both **ansys**.

#. Set your GitHub PAT as an environment variable ``GITHUB_TOKEN``.

.. tab-set::

    .. tab-item:: Windows

        $env:GITHUB_TOKEN = "<token>"

    .. tab-item:: Linux

        export GITHUB_TOKEN="<token>"

.. warning::

    If you are using VS Code, you need to close all instances for the environment variable to take effect.


Install Docker
--------------

`Docker <https://www.docker.com/>`__ is required to run HPS.


.. tab-set::

    .. tab-item:: Windows

        Either install ``Docker Desktop`` (may require a Docker subscription depending on your organization) or run ``Docker CE`` (Community Edition, which is open-source) in WSL (Windows Subsystem for Linux).

        If using Docker CE:

            #. If you don't have WSL installed, follow the official Microsoft `How to install Linux on Windows with WSL <https://learn.microsoft.com/en-us/windows/wsl/install>`_ documentation.
            #. Follow the official `Docker installation guide <https://docs.docker.com/engine/install/>`_ to install Docker Engine and Docker Compose on WSL.

    .. tab-item:: Linux

        #. Install ``Docker CE`` - `instructions here for Linux <https://docs.docker.com/engine/install/ubuntu/>`_.

        #. Add your user to the docker group:

          .. code:: bash

            sudo gpasswd -a $USER docker
            newgrp docker


Set the :envvar:`MACHINE_IP` environment variable
-----------------------------------------------------

The :envvar:`MACHINE_IP` environment variable must be set to the IP address of your machine.

.. tab-set::

    .. tab-item:: Running Docker with WSL (Windows)

        If you are using WSL to run Docker, the ``MACHINE_IP`` is the WSL IP address of your machine.

        #. Find the WSL IP address:

            a. Open a WSL terminal and run the following command:

                .. code-block:: bash

                    ip addr show eth0

            b. Find the ``inet`` line under the ``eth0`` section.
            c. Note the IP address, which is the number before the ``/``.

        #. Add the ``MACHINE_IP`` environment variable:

            a. Click the :guilabel:`Environment Variables` button.
            b. Under **System Variables**, click :guilabel:`New`.
            c. Enter ``MACHINE_IP`` as the variable name.
            d. Set the WSL IP address you noted in the previous step as the value.
            e. Click :guilabel:`OK` to save the variable.

    .. tab-item:: Running Docker with Docker Desktop (Windows)

        If you are using Docker Desktop to run Docker, use your machine's Wireless or Ethernet IP address, as follows:

        * If connected via Wi-Fi, use the IP address from the ``Wireless LAN adapter Wi-Fi`` section.
        * If connected via Ethernet, use the IP address from the ``Ethernet adapter Ethernet`` section.

        #. Find the machine IP address:

            a. Open a terminal and run the following command:

            .. code-block:: bash

                ipconfig /all

            b. Locate the ``Ethernet adapter Ethernet`` or ``Wireless LAN adapter Wi-Fi`` section.
            c. Note the IP address under ``IPv4 Address``.

        #. Add the ``MACHINE_IP`` environment variable:

            a. Click the :guilabel:`Environment Variables` button.
            b. Under **System Variables**, click :guilabel:`New`.
            c. Enter ``MACHINE_IP`` as the variable name.
            d. Set the WSL IP address you noted above as the value.
            e. Click :guilabel:`OK` to save the variable.


.. warning::

    If you are using VS Code, you need to close all instances for the environment variable to take effect.


Deploy the core services
========================

Follow these steps to start and verify the HPS core services.

Start HPS core services
-----------------------

Follow these steps to deploy the Ansys HPS core services using Docker Compose on your machine.

.. seealso::

  For more detailed instructions, see `Deploying Core Services with Docker Compose <https://ansyshelp.ansys.com/public/account/secured?returnurl=/Views/Secured/hpcplat/v110/en/hps_dg/deploy_core_docker_compose.html>`_ in the Ansys HPC Platform Services Deployment Guide.

#. Ensure that Docker is installed and that the ``MACHINE_IP`` environment variable is set (see above).

#. Navigate to the supported HPS version listed in the supported software table to know which version to download.

#. Download HPS core services.
    a. Go to the `Ansys Customer Portal <https://support.ansys.com/>`_.
    b. Navigate to **Downloads > Current release >Platform Components > HPC Platform Services**.
    c. Download **HPS-Core (docker compose)** (``docker-compose-internal.tar.gz``).

    .. important::

        SAF is only tested against the supported HPS version listed in the supported software table. You can try other versions but they may not work correctly.

#. Extract the downloaded file. Extract the ``docker-compose-customer.tar.gz`` file:

    .. code-block:: bash

        tar -xvf docker-compose-customer.tar.gz

    A folder named ``docker-compose-customer`` is extracted.

#. Navigate to the extracted folder:

    .. code-block:: bash

        cd docker-compose-customer

#. Log in to the Docker Registry. Authenticate with your GitHub username and personal access token (PAT):

    .. code-block:: bash

        docker login ghcr.io/ansys

    .. note::

        If you have lost or forgotten your PAT, follow the steps in `GitHub Docs: Creating a personal access token <https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic>`_  to generate a new one. Make sure it has the ``read:packages`` scope.

#. Update the environment variables file.

    a. In a text editor, open the environment variables file. This is the ``.env`` file located in the ``docker-compose-customer`` folder.

    b. Locate the following line:

       .. code-block:: makefile

           EXTERNAL_NAME=localhost

    c. In this line, replace ``localhost`` with your machine's IP (``MACHINE_IP``), so it reads:

       .. code-block:: makefile

           EXTERNAL_NAME=${MACHINE_IP}

    d. Save the file.

#. Start the HPS core service containers.

    .. code-block:: bash

        docker-compose up -d

    .. note::

        The first time you run this command, it takes time to build the image and download the required third-party containers. You can expect subsequent runs to be faster.

Verify HPS core services
------------------------

Follow these steps to verify that the HPS core services started correctly.


#. Open this URL in a web browser:
    .. code:: none

     https://<MACHINE_IP>:8443/hps

#. Access the HPS web app.
    a. Click the :guilabel:`JMS Web UI` button to access the HPS web app.
    b. Log in using the default administrative credentials:

       * Username: ``repadmin``
       * Password: ``repadmin``

If you completed these steps successfully, the HPS core services have been started correctly.


Deploy a static evaluator or an autoscaling service
===================================================

You can deploy either a static evaluator or an autoscaling service to run jobs on your machine.
Refer to the `official documentation <https://ansyshelp.ansys.com/public/account/secured?returnurl=/Views/Secured/hpcplat/v110/en/hps_dg/hps_dg.html>`__ for more details on each option.


Deploy a static evaluator
-------------------------

.. seealso::

    For more detailed instructions, see `Deploying Static Evaluators <https://ansyshelp.ansys.com/public/account/secured?returnurl=/Views/Secured/hpcplat/v110/en/hps_dg/hps_dg_evaluators.html>`_ in the Ansys HPC Platform Services Deployment Guide.


Follow these steps to start and verify the HPS evaluator.

Start the HPS evaluator
~~~~~~~~~~~~~~~~~~~~~~~

Follow these steps to deploy the HPS evaluator on your machine.

.. seealso::

  For more detailed instructions, see `Deploying Core Services with Docker Compose <https://ansyshelp.ansys.com/public/account/secured?returnurl=/Views/Secured/hpcplat/v110/en/hps_dg/deploy_core_docker_compose.html>`_ in the Ansys HPC Platform Services Deployment Guide.

#. Download the HPS evaluator.
    a. Go to the `Ansys Customer Portal <https://support.ansys.com/>`_.
    b. Navigate to **Downloads > Current release > Platform Components > HPC Platform Services**.
    c. Download the evaluator file that corresponds to your operating system:

       .. tab-set::

           .. tab-item:: Windows

             Click **hps-evaluator (Windows)** to download ``rep-evaluator-windows-signed.tgz``.

           .. tab-item:: CentOS 8 or later, Ubuntu

               Click **hps-evaluator (ubuntu20_04)** to download ``rep-evaluator-default.tgz``.

           .. tab-item:: CentOS 7

               Click **hps-evaluator (Centos7)** to download ``rep-evaluator-centos7.tgz``.

#. Extract the archive.
    For example, on Windows:

    .. code-block:: bash

        tar -xvf rep-evaluator-windows-signed.tgz

#. Navigate to the extracted folder.
    .. code-block:: bash

        cd rep-evaluator-windows-signed

    The folder contains the ``rep-evaluator.exe`` file.

#. Log in to the controller.
    The evaluator must be able to communicate with the services on the controller. This is done by logging in to the controller from the evaluator.

    At the command prompt, run the ``rep-evaluator`` executable's login command with the following arguments:

    .. tab-set::

        .. tab-item:: Windows PowerShell

            .. code-block:: bash

                ./rep-evaluator.exe login --url https://$($env:MACHINE_IP):8443/rep --username repadmin --password repadmin

        .. tab-item:: Linux Bash

            .. code-block:: bash

                ./rep-evaluator login --url https://$MACHINE_IP:8443/rep --username repadmin --password repadmin

#. Start the evaluator.
    Once you are logged in, run this command to start the evaluator:

    .. tab-set::

        .. tab-item:: Windows

            .. code-block:: powershell

                ./rep-evaluator.exe

        .. tab-item:: Linux

            .. code-block:: bash

                ./rep-evaluator

The evaluator should now be available on the **Resources** page of the Ansys HPC Manager.


Verify the HPS evaluator
~~~~~~~~~~~~~~~~~~~~~~~~

Follow these steps to ensure that the HPS evaluator is running correctly.

#. **Go to the Ansys HPC Manager Resources page.**
#. **Confirm that the evaluator is listed as a resource.**


Deploy an autoscaling service
-----------------------------

Refer to the `HPS official documentation <https://ansyshelp.ansys.com/public/account/secured?returnurl=/Views/Secured/hpcplat/v110/en/hps_dg/hps_dg_autoscalers.html>`_ to deploy and configure an autoscaling service.




