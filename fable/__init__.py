"""FABLE post-processing: recalc engines, data contract, and bundle builder.

Layering (see fable/contract/CONTRACT.md):

    FABLE .xlsx
        -> compute.engines  (recalc every pathway -> CSV run dir)  [fragile, isolated]
        -> compute.bundle   (CSV run dir -> bundle.json)           [pure python]
        -> compute.validate (sanity gate)                          [pure python]
        -> viewer/          (static React, consumes bundle.json)   [cannot touch pipeline]

The only stable interface between compute and viewer is the versioned bundle
described by ``fable/contract/bundle.schema.json``.
"""

__version__ = "2.0.0"
