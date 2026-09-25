.. _home:

:html_theme.show_toc: false


.. CI trigger: doc deploy verification for PR workflow.
.. CI trigger: second docs touch to verify deploy-doc visibility in PR checks.

.. title:: SAF developer's guide

.. toctree::
   :maxdepth: 1
   :hidden:

   overview/index
   getting_started/index
   user_guide/index
   examples/index
   api/index
   contribute/index


.. Top section

.. raw:: html

   <div class="saf-hero">
     <div class="saf-hero__content">
       <h1 class="saf-hero__title">Build and deploy simulation web apps at scale</h1>
       <p class="saf-hero__subtitle">
         Use SAF (Solution Application Framework), a Python-centric framework, to turn complex, multi-domain PyAnsys workflows
         into guided, shareable web apps — without needing to become full-stack software engineers.
       </p>
       <div class="saf-hero__ctas">
         <a class="saf-cta saf-cta--primary" href="getting_started/index.html">Get started</a>
         <a class="saf-cta saf-cta--secondary" href="examples/index.html">View examples</a>
       </div>
     </div>
   </div>

.. raw:: html

   <div class="saf-section-primary">

Where do you want to start?
#############################

.. grid:: 3
   :gutter: 4

   .. grid-item-card:: I'm new to SAF
      :link: getting_started/index
      :link-type: doc
      :class-card: sd-border-primary
      :img-top: _static/images/getting-started.svg

      Start here. Install prerequisites, scaffold your first solution, and run it locally
      in under 30 minutes.

      **→ Getting Started**

   .. grid-item-card:: I'm building a solution
      :link: user_guide/index
      :link-type: doc
      :class-card: sd-border-primary
      :img-top: _static/images/user-guide.svg

      Follow the method developer workflow: scaffold, build backend and frontend,
      run, test, and package your solution.

      **→ User guide**

   .. grid-item-card:: I'm deploying a solution
      :link: user_guide/deploy/index
      :link-type: doc
      :class-card: sd-border-primary
      :img-top: _static/images/deployment.svg

      Choose your deployment target: desktop installer, single-node Windows service,
      or distributed Docker Compose / K3s.

      **→ Deployment**

