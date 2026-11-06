.. _best_practices:

##############
Best practices
##############

This section provides examples of best practices to use when building your solution.


.. grid:: 3
   :gutter: 4
   :class-container: onboarding-cards

   .. grid-item-card:: :material-outlined:`rule;1.75em` :ref:`best_practices_general_rules`
    :class-card: highlight-card
    :link-type: doc
    :link: general_rules
    :shadow: lg

    Essential rules for writing correct SAF modules.

   .. grid-item-card:: :material-outlined:`schema;1.75em` :ref:`best_practices_logic`
    :class-card: highlight-card
    :link-type: doc
    :link: logic
    :shadow: lg

    Implement the business logic in your solution.

   .. grid-item-card:: :material-outlined:`dns;1.75em` :ref:`best_practices_backend_conventions`
    :class-card: highlight-card
    :link-type: doc
    :link: backend_conventions
    :shadow: lg

    Stateless design, file naming, and field defaults.

   .. grid-item-card:: :material-outlined:`view_module;1.75em` :ref:`best_practices_step_decomposition`
    :class-card: highlight-card
    :link-type: doc
    :link: step_decomposition
    :shadow: lg

    When to merge or split steps in your workflow.

   .. grid-item-card:: :material-outlined:`account_tree;1.75em` :ref:`best_practices_dag_design`
    :class-card: highlight-card
    :link-type: doc
    :link: dag_design
    :shadow: lg

    Design the dependency graph between fields and steps.

   .. grid-item-card:: :material-outlined:`data_object;1.75em` :ref:`best_practices_data_model_rules`
    :class-card: highlight-card
    :link-type: doc
    :link: data_model
    :shadow: lg

    Define typed step fields and supported data types.

   .. grid-item-card:: :material-outlined:`sync;1.75em` :ref:`best_practices_transaction_methods`
    :class-card: highlight-card
    :link-type: doc
    :link: transaction_methods
    :shadow: lg

    Transaction types, cross-step reads, progress streaming, and decorator order.

   .. grid-item-card:: :material-outlined:`folder;1.75em` :ref:`best_practices_files`
    :class-card: highlight-card
    :link-type: doc
    :link: files
    :shadow: lg

    Manage solution files and avoid common file handling errors.

   .. grid-item-card:: :material-outlined:`task_alt;1.75em` :ref:`best_practices_bdm`
    :class-card: highlight-card
    :link-type: doc
    :link: bdm
    :shadow: lg

    Follow recommended patterns for reliable and maintainable file management with BDM.

   .. grid-item-card:: :material-outlined:`apps;1.75em` :ref:`best_practices_product_instance_management`
    :class-card: highlight-card
    :link-type: doc
    :link: product_instances
    :shadow: lg

    Manage Ansys product instance lifecycles correctly.

   .. grid-item-card:: :material-outlined:`settings;1.75em` :ref:`best_practices_environment_variables`
    :class-card: highlight-card
    :link-type: doc
    :link: environment_variables
    :shadow: lg

    Properly access environment variables in your solution.

   .. grid-item-card:: :material-outlined:`web;1.75em` :ref:`best_practices_frontend`
    :class-card: highlight-card
    :link-type: doc
    :link: frontend
    :shadow: lg

    Dash callbacks, project injection, and UI component choices.

   .. grid-item-card:: :material-outlined:`book;2.25em` :ref:`best_practices_dictionary`
    :class-card: highlight-card
    :link-type: doc
    :link: dictionary

    Learn to define, access, and modify dictionary step fields.

   .. grid-item-card:: :material-outlined:`inventory;1.75em` :ref:`best_practices_products`
    :class-card: highlight-card
    :link-type: doc
    :link: products
    :shadow: lg

    Learn how to use Ansys products within your solution.


.. toctree::
   :maxdepth: 3
   :hidden:

   general_rules
   logic
   backend_conventions
   step_decomposition
   dag_design
   data_model
   transaction_methods
   files
   bdm
   product_instances
   environment_variables
   frontend
   dictionary
   products
