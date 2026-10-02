.. _transaction_methods:

Transaction methods
###################

.. grid:: 4
  :gutter: 4
  :class-container: onboarding-cards

  .. grid-item-card:: :material-outlined:`description;1.75em` :ref:`transaction_method_definition`
    :class-card: highlight-card
    :link-type: doc
    :link: definition
    :shadow: lg

    Leverage the SAF ``@transaction`` decorator to define methods.

  .. grid-item-card:: :material-outlined:`tune;1.75em` :ref:`getting_and_setting_fields`
    :class-card: highlight-card
    :link-type: doc
    :link: getting_and_setting_fields
    :shadow: lg

    Fetch and modify persisted step fields using ``@transaction`` decorator arguments.

  .. grid-item-card:: :material-outlined:`play_circle;1.75em` :ref:`execution_from_client`
    :class-card: highlight-card
    :link-type: doc
    :link: execution_from_client
    :shadow: lg

    Execute transaction methods from the Dash client or Python client.

  .. grid-item-card:: :material-outlined:`hourglass_empty;1.75em` :ref:`asynchronous_execution`
    :class-card: highlight-card
    :link-type: doc
    :link: asynchronous_execution
    :shadow: lg

    Handle transaction methods that take a long time to complete.

  .. grid-item-card:: :material-outlined:`error_outline;1.75em` :ref:`handling_errors`
    :class-card: highlight-card
    :link-type: doc
    :link: handling_errors
    :shadow: lg

    Raise and handle errors that occur during transaction execution.

  .. grid-item-card:: :material-outlined:`swap_horiz;1.75em` :ref:`parameters_and_return_values`
    :class-card: highlight-card
    :link-type: doc
    :link: parameters_and_return_values
    :shadow: lg

    Pass input parameters and return data directly through a transaction method signature.

  .. grid-item-card:: :material-outlined:`person;1.75em` :ref:`accessing_user_information`
    :class-card: highlight-card
    :link-type: doc
    :link: accessing_user_information
    :shadow: lg

    Retrieve runtime information about the user executing the transaction.

  .. grid-item-card:: :material-outlined:`cached;1.75em` :ref:`field_states`
    :class-card: highlight-card
    :link-type: doc
    :link: field_states
    :shadow: lg

    Determine whether a step field is up to date or outdated.

  .. grid-item-card:: :material-outlined:`cloud;1.75em` :ref:`cloud_compatibility`
    :class-card: highlight-card
    :link-type: doc
    :link: cloud_compatibility
    :shadow: lg

    Understand how transaction methods support cloud and on-premises deployments.

.. toctree::
   :maxdepth: 2
   :hidden:

   definition
   getting_and_setting_fields
   execution_from_client
   asynchronous_execution
   handling_errors
   parameters_and_return_values
   accessing_user_information
   field_states
   cloud_compatibility
