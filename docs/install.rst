:: _install:

Installation
============

.. highlight:: bash

Prerequisites:

* Python >= 3.9

To install TomorrowCities Python package you can use `pip`:

.. code-block:: bash

   pip install tomorrowcities

For local development from source, prefer editable install:

.. code-block:: bash

   git clone https://github.com/TomorrowsCities/tomorrowcities
   cd tomorrowcities
   pip install -e .

`pip install -e .` installs dependencies from ``pyproject.toml`` and installs
this repository as an editable package. This avoids import issues such as
``ModuleNotFoundError: No module named 'tomorrowcities'`` when running:

.. code-block:: bash

   solara run tomorrowcities.pages

``pip install -r requirements.txt`` only installs listed dependencies and does
not install this project package itself unless explicitly included.

