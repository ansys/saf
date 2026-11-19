.. _technology_radar:

################
Technology Radar
################

The SAF technology radar shows the technologies, tools, and practices that the SAF team uses or
evaluates, and how the team recommends using them when building solutions.

The radar groups items into four quadrants:

- **Staples**: Languages, frameworks, and services used to build software.
- **Security & Compliance**: Tools that streamline and enforce security and compliance rules.
- **Platforms & Operations**: Platforms and services for operating and scaling applications.
- **Tools & Patterns**: Productivity tools and patterns for projects of any size.

Each item is placed in one of four rings:

- **Adopt**: Recommended default for SAF solutions.
- **Trial**: Worth using on projects that can handle some risk.
- **Assess**: Worth exploring to understand its impact.
- **Hold**: Not recommended for new work.

.. button-link:: /version/stable/radar/
   :color: primary
   :shadow:

   Open the technology radar in full screen

.. raw:: html

   <iframe
     src="/version/stable/radar/"
     title="SAF technology radar"
     loading="lazy"
     style="width: 100%; height: 900px; border: 0;">
   </iframe>

The radar content is maintained in the ``doc/radar/radar`` folder of the
`SAF repository <https://github.com/ansys/saf/tree/main/doc/radar/radar>`_. To propose a change,
open a pull request that adds or edits a Markdown file in a new release folder.
