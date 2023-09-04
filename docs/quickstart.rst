Quick Start
===========

.. highlight:: python

After :doc:`/install`, you can import `tomorrowcities` 
package and start generating exposure data or calculating
impact metrics.

.. code-block:: python

   import tomorrowcities as tc
   
   dg = tc.DataGenerator(parameter_file='distribution_table.xlsx',
                    land_use_file='landuse.zip')

   building, household, individual, land_use = dg.generate(seed=42)

   metrics = dg.run_engine(building, household, individual, land_use,
                hazard_scenario="FLOOD", hazard_data="flood.xlsx", policies=None):


