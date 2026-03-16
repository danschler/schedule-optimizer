# Research Notes: University Course Timetabling Problem

## Problem Classification

The University Course Timetabling Problem (UCTP) is NP-hard. For our problem size (15 teachers, 30 courses, 12 rooms, 8 student groups), exact methods via constraint programming are practical.

## Algorithm Comparison

| Approach | Pros | Cons | Typical Quality | Solve Time |
|----------|------|------|----------------|------------|
| **CP-SAT (Constraint Programming)** | Guaranteed optimal/feasible, handles hard constraints natively, good for small-medium problems | Slower for very large instances | 90-98% constraint satisfaction | 2-10s for our size |
| Genetic Algorithm (GA) | Good for large instances, handles soft constraints well | No optimality guarantee, requires tuning | 70-90% | 30-120s |
| Simulated Annealing (SA) | Simple to implement, good exploration | Slow convergence, parameter sensitive | 75-85% | 20-60s |
| Integer Linear Programming (ILP) | Optimal solutions, well-studied | Hard to model complex constraints, large variable count | 95-100% (if feasible) | 5-30s |
| Graph Coloring | Natural mapping for conflict avoidance | Limited to conflict constraints only | 60-75% | <1s |
| Tabu Search | Good local search, avoids cycling | Needs good initial solution | 80-90% | 10-30s |
| Hybrid (CP + metaheuristic) | Best of both worlds | Complex implementation | 95-99% | 10-60s |

## Solver Choice: Google OR-Tools CP-SAT

Selected for:
1. **Ease of use**: Python API, declarative constraint modeling
2. **Quality**: 90-98% constraint satisfaction for our problem size
3. **Speed**: 2-10 seconds for 15 teachers, 30 courses
4. **Free/open-source**: Apache 2.0 license
5. **Active maintenance**: Google-backed, regular releases
6. **Rich constraint library**: AddExactlyOne, AddAtMostOne, AddMaxEquality, etc.

### Alternatives Considered

- **DEAP (GA framework)**: Good Python library but no optimality guarantee; would need custom constraint handling
- **PuLP (LP/ILP)**: Good for linear problems but harder to model complex scheduling constraints
- **python-constraint**: Pure Python, too slow for our problem size
- **OptaPlanner**: Java-based, heavy dependency for a Python project

## Reference Implementations Studied

- **UniTime**: Enterprise-grade, Java, uses constraint-based solver. Too complex for our needs.
- **FET (Free Educational Timetabling)**: C++, uses custom heuristics. Good constraint taxonomy reference.
- **PyJobShop**: Python job-shop scheduling with OR-Tools. Similar variable structure to our approach.

## Key Design Decision: Pre-filtering

Naive approach: 30 courses x 15 teachers x 12 rooms x 45 slots = 243,000 variables
With pre-filtering: ~10,000 variables (22x reduction)

Pre-filtering removes impossible combinations before variable creation:
- Only eligible teachers per course (by subject)
- Only eligible rooms per course (by room_type and capacity)
- Only available slots per teacher (by availability schedule)

## Benchmark Expectations

- Solve time: 2-10 seconds (30s timeout)
- Variable count: ~10,000
- Constraint count: ~5,000
- Solution quality: Feasible with 0 hard violations, minimal soft penalties
