.. _minerva_auth:

Minerva authentication
######################

Three different authentication modes are supported: impersonation, non-interactive, and interactive.

.. note::

   Pay attention to the double underscore used in the environment variables mentioned in this document.


Impersonation with access token
===============================

If a ``bearer`` access token is present in the request, SAF GLOW Engine uses the impersonation feature of the ``MinervaClient`` to authenticate as the user represented by the access token.
The username is extracted directly from the token's JWT payload, without requiring an identity provider (:envvar:`GLOW_AUTH_ISSUER_URL` and :envvar:`GLOW_AUTH_CLIENT_ID`)
to be configured. This requires setting the environment variables :envvar:`ANS_MINERVA_AUTH__CERTCONFIG` and :envvar:`ANS_MINERVA_AUTH__DATABASE`.

This authentication mode has priority over the other modes.


Non-interactive
===============

If impersonation cannot be triggered (for example, no access token is present or identity provider is not configured). ``MinervaClient`` tries to use the environment variables
:envvar:`ANS_MINERVA_AUTH__DATABASE`, :envvar:`ANS_MINERVA_AUTH__USER`, and :envvar:`ANS_MINERVA_AUTH__PASSWORD` to automatically sign in to the Minerva instance.


Interactive
===========

If no access token is provided and environment variables are not configured, Minerva automatically launches a login page for you to enter your credentials.