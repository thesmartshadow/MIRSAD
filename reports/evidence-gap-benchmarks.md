# Evidence-Gap Benchmarks

## GDELT Total Budget

- Per-attempt HTTP timeout: 1000 ms
- Strict connector budget, including retries and backoff: 350 ms
- Search 1 attempts: [20.13, 20.16] ms
- Search 1 retry backoff: 250.62 ms
- Search 1 total: 291.32 ms; circuit closed
- Search 2 attempts: [20.14, 20.68] ms
- Search 2 retry backoff: 250.99 ms
- Search 2 total: 292.16 ms; circuit open
- Open-circuit response: 0.007 ms with zero HTTP attempts

The two measured searches are separate calls used to cross the repeated-failure threshold. Each call has one total budget; retry count cannot multiply that budget.

## First Useful Result

- Source completion: {'fast': 37.95, 'medium': 98.17, 'slow': 188.41}
- First healthy connector completed: 37.95 ms
- Result available through current request/response API: 980.23 ms
- Final state: partial with 2 results
- Streaming: not exposed by the current architecture; the API returns after all bounded connector tasks complete. The final partial response retains healthy results and identifies the failed source.

## Backend Memory Observation

- Snapshots: [{'completed_searches': 1, 'rss_kib': 708996}, {'completed_searches': 10, 'rss_kib': 709316}, {'completed_searches': 20, 'rss_kib': 709420}, {'completed_searches': 30, 'rss_kib': 709436}, {'completed_searches': 31, 'rss_kib': 711836}]
- Observed RSS range: 2840 KiB
- Scope: bounded observation only, not a formal retained-heap or leak proof.
