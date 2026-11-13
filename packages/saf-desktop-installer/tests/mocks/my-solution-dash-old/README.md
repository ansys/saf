This solution still has the ansys-saf-desktop-installer dependency in the DESKTOP group AND in the BUILD group. Newer solutions, SAF-CLI 3.6.0 or greater, only have it in the BUILD group.

It is also the Poetry compatibility solution: tests about Poetry-based solutions use it (see `use_poetry_mock_solution` in tests/conftest.py). doc/source is used by the Poetry packaging test.
