# Internal Engine Performance

These are deterministic local measurements, not external network timings.

- Iterations: 12
- Connectors: 3 concurrent fixtures at 50 ms each
- Records per search: 15 collected / 2 unique
- Median wall time: 198.99 ms
- P95 wall time: 230.92 ms
- Median phases: {'connector_collection': 57.55, 'persistence': 18.55, 'deduplication': 22.55, 'ranking': 75.82, 'clustering': 6.64}
- Transformation scaling: [{'records': 100, 'normalization_ms': 0.3, 'ranking_ms': 5.2, 'deduplication_ms': 80.33, 'clustering_ms': 5.78}, {'records': 200, 'normalization_ms': 0.61, 'ranking_ms': 8.94, 'deduplication_ms': 344.69, 'clustering_ms': 13.56}, {'records': 1000, 'normalization_ms': 3.13, 'ranking_ms': 44.35, 'deduplication_ms': None, 'clustering_ms': None}, {'records': 5000, 'normalization_ms': 16.19, 'ranking_ms': 226.95, 'deduplication_ms': None, 'clustering_ms': None}, {'records': 10000, 'normalization_ms': 32.56, 'ranking_ms': 434.71, 'deduplication_ms': None, 'clustering_ms': None}]
- Deduplication and clustering are measured at 100 and 200 records because interactive collection is capped at 200; larger values would not represent a production search.
