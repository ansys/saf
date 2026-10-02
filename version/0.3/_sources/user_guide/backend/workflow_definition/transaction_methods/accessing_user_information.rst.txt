.. _accessing_user_information:

Access user information
########################

There are two ways to access the user information in a transaction method: using the ``self.transaction.user_info`` property, and using the ``self.transaction.get_user_info()`` method.

Use the ``user_info`` property
==================================

You can retrieve the information about the user who launched the transaction by accessing the ``self.transaction.user_info`` property:

.. code:: python

    from ansys.saf.glow.solution import UserInfo


    @transaction(self=StepSpec())
    def get_user_info(self) -> UserInfo:
        return self.transaction.user_info

This property is always available, but its content depends on the availability of the authorization token in the request header. If the token is not present,
the property returns an empty ``UserInfo`` object. Otherwise, the user information is fetched from the identity provider. This implies that the token
must be valid and the identity provider must be configured (:envvar:`GLOW_AUTH_ISSUER_URL` and :envvar:`GLOW_AUTH_CLIENT_ID`). An error is thrown if any of these
two conditions are not met.

For more information about the available fields, see the API reference of ``ansys.saf.glow.solution.UserInfo``.

Use the ``get_user_info()`` method
=====================================

Alternatively, you can use the ``self.transaction.get_user_info()`` method to retrieve the user information:

.. code:: python

    from ansys.saf.glow.solution import UserInfo


    @transaction(self=StepSpec())
    def get_user_info(self) -> UserInfo:
        return self.transaction.get_user_info(fields=["preferred_username", "email"])

Similarly to the ``user_info`` property, if the authorization token is not present, this method returns an empty ``UserInfo`` object.
Otherwise, the user information is fetched either directly from the token or through a request to the identity provider depending on the fields specified in the
``fields`` argument.

If no fields are specified or the specified fields are present in the token, the user information is fetched from the token. If any of the specified fields
is not available in the token, a request is made to the identity provider. If the user information fetched from the identity provider contains the specified fields,
it is returned, otherwise an error is thrown.

The fact that this method checks the token before sending a request to the identity provider means that it is generally more efficient than using the ``user_info`` property,
and can work even if the identity provider is not configured (:envvar:`GLOW_AUTH_ISSUER_URL` and :envvar:`GLOW_AUTH_CLIENT_ID`), as long as the specified fields are present
in the token.


Obtain the access token
=======================

If the authorization token itself is needed inside a transaction, it can be retrieved using the ``self.transaction.access_token`` property. This can be used to connect to
downstream services.

.. code:: python

    @transaction(self=StepSpec())
    def connect_to_downstream_service(self) -> None:
        connect_to_my_service(self.transaction.access_token)
