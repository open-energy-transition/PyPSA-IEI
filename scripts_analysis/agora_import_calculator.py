from typing import List

import pypsa


class AgoraImportCalculator:
    def __init__(
        self,
        network: pypsa.Network,
        sets_filter: List[str],
        year: str,
        scenario: str,
    ):
        self.network = network
        self.sets_filter = sets_filter
        self.year = year
        self.scenario = scenario

        # calculate series
        import_genenators = network.generators[
            network.generators.carrier.isin(sets_filter)
        ].index
        self.import_gens_series = network.generators_t.p[import_genenators]
        not_empty_columns = self.import_gens_series.columns[
            (self.import_gens_series != 0).any()
        ]
        self.import_gens_series_used = self.import_gens_series[
            not_empty_columns
        ]
        snapshots = network.snapshot_weightings.generators
        self.import_gens_series_TWh = (
            self.import_gens_series.mul(snapshots, axis=0) / 1e6
        )
        self.import_gens_series_used_ThW = (
            self.import_gens_series_used.mul(snapshots, axis=0) / 1e6
        )

    def get_total(self, subset: List[str]):
        import_generators = self.network.generators[
            self.network.generators.carrier.isin(subset)
        ].index
        return self.import_gens_series_TWh[import_generators].sum().sum()
