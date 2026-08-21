# Relevance Performance

Local CPU measurements only; connector network time is excluded.

| Documents | FTS | Lexical | Semantic cold | Semantic warm | Total cold | Total warm |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 0.10 ms | 4.03 ms | 727.85 ms | 4.30 ms | 733.30 ms | 9.75 ms |
| 1000 | 0.83 ms | 40.52 ms | 77.01 ms | 4.30 ms | 119.60 ms | 46.89 ms |
| 5000 | 3.89 ms | 189.06 ms | 70.42 ms | 4.39 ms | 264.65 ms | 198.62 ms |
| 10000 | 8.03 ms | 397.45 ms | 74.13 ms | 4.70 ms | 480.86 ms | 411.43 ms |

Peak observed RSS increase: 683.8 MiB.
Semantic work is bounded to 20 candidates. Production collection is capped at 200; the 1,000-10,000 rows are lexical scaling stress observations, not normal session sizes.
