This solution still has the ansys-saf-desktop-installer dependency in the DESKTOP group AND in the BUILD group. Newer solutions, SAF-CLI 3.6.0 or greater, only have it in the BUILD group.

Both Poetry and UV configurations retain this legacy dependency layout.
Poetry-specific tests select it through `use_poetry_mock_solution`.
doc/source is used by the packaging unit test.
