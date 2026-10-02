# Intent reader: fact-by-fact evaluation

2000 synthetic students (seed 99), keyword reader (`uniadvisor.student.intent.keywords`). Regenerate with `uniadvisor intent-eval`. The texts come from the generator's phrase banks: these numbers measure coverage of that phrasing, not accuracy on real students.

## Facts with one value

| Fact | Stated | Read right | Read wrong | Missed | Not stated | Read anyway |
|---|---|---|---|---|---|---|
| Budget (amount, or poor / rich) | 1382 | 97% | 0% | 3% | 618 | 4% |
| Location | 1456 | 96% | 0% | 3% | 544 | 2% |
| Main campus only | 158 | 99% | 0% | 1% | 1842 | 0% |
| Risk attitude | 1207 | 98% | 0% | 2% | 793 | 7% |
| Top priority | 1305 | 96% | 1% | 3% | 695 | 6% |
| English level | 895 | 95% | 0% | 5% | 1105 | 0% |
| Speech difficulty | 71 | 99% | 0% | 1% | 1929 | 0% |
| Goes along with the family's wish | 406 | 95% | 1% | 4% | 1594 | 0% |

## Areas of study (MOET codes)

Judged by the programs the codes take in, over the 1424 programs with a MOET code: precision = of the programs the read codes take in, the share the true codes also take in; recall = the reverse; exact = the same programs.

| Fact | Stated | Precision | Recall | Exact | Missed | Not stated | Read anyway |
|---|---|---|---|---|---|---|---|
| Interests | 1629 | 84% | 83% | 72% | 7% | 371 | 5% |
| Dislikes | 815 | 91% | 62% | 24% | 13% | 1185 | 1% |
| Family's wish | 406 | 100% | 95% | 94% | 4% | 1594 | 0% |

## Subjects

| Fact | Precision | Recall |
|---|---|---|
| Strong subjects | 86% | 92% |
| Weak subjects | 96% | 96% |

Stated vs hobby (one interest, read as one): 96% right (863 students).
