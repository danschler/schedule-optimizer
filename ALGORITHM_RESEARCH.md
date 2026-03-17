# Optimization Algorithm Research: University Course Timetabling

## 1. Problem Classification

The University Course Timetabling Problem (UCTP) is a well-studied NP-hard combinatorial optimization problem. It belongs to the broader family of constraint satisfaction and optimization problems (CSOPs). Our specific instance has:

- **~10,000 binary decision variables** (after pre-filtering from ~243K)
- **~5,000 constraints** (8 hard + 10 soft)
- **Problem size**: 15 teachers, 30 courses, 12 rooms, 8 student groups, 45 time slots
- **Objective**: Minimize weighted sum of soft constraint violations while satisfying all hard constraints

This is a **small-to-medium** instance by academic standards. Large university instances can have 500+ courses, 100+ rooms, and 50+ student groups.

---

## 2. Current Approach: Google OR-Tools CP-SAT

### How It Works

CP-SAT (Constraint Programming with Satisfiability) is a hybrid solver that combines:
- **Constraint Propagation**: Reduces domains by inferring infeasible values
- **SAT-based search**: Uses Boolean satisfiability (CDCL) techniques for systematic exploration
- **Linear relaxation**: Applies LP bounds to prune the search space
- **Lazy clause generation**: Learns from conflicts to avoid repeating failed assignments

The solver operates on Boolean variables with linear constraints and a linear objective function. It uses **parallelism** (8 workers in our config) where each worker explores with a different strategy simultaneously.

### Strengths for This Project

| Aspect | Assessment |
|--------|-----------|
| Solution quality | Provably optimal or near-optimal for our problem size |
| Solve time | 2-10 seconds (well within the 30s timeout) |
| Hard constraint handling | Native — modeled as hard clauses, guaranteed satisfied |
| Soft constraint handling | Weighted penalty minimization in objective function |
| Implementation effort | Low — declarative modeling via Python API |
| Library quality | Excellent — Google-maintained, Apache 2.0, well-documented |
| Parallelism | Built-in multi-worker search |

### Limitations

- **Scalability ceiling**: Performance degrades exponentially as problem size grows. At 5-10x our current size (~50-100K variables), solve times can exceed minutes or hit timeout
- **No traditional warm-starting**: CP-SAT does not support MIP-start style warm-starting. However, it does support **solution hints** via `model.AddHint(var, value)` which biases the search toward a known good solution
- **Memory usage**: Scales with variable count; can become significant for very large instances
- **Black box**: Limited control over search strategy beyond parameter tuning
- **Internal LNS**: CP-SAT already runs LNS workers internally as part of its parallel portfolio, but you cannot define custom destroy/repair operators through the public API

---

## 3. Algorithm Comparison

### 3.1 Integer Linear Programming (ILP)

**How it works**: Models the problem as minimizing a linear objective subject to linear equality/inequality constraints over integer (typically binary) variables. Uses branch-and-bound with LP relaxations, cutting planes, and presolve techniques.

**Solvers**:

| Solver | License | Python API | Relative Speed |
|--------|---------|-----------|---------------|
| **Gurobi** | Commercial (free academic) | gurobipy, PuLP | Fastest (1x baseline) |
| **CPLEX** | Commercial (free academic) | docplex, PuLP | ~1.1x Gurobi |
| **HiGHS** | Open source (MIT) | highspy, PuLP | ~2-5x Gurobi |
| **CBC/COIN-OR** | Open source (EPL) | PuLP | ~5-20x Gurobi |
| **GLPK** | Open source (GPL) | PuLP, pyomo | ~10-50x Gurobi |

**Comparison to CP-SAT**:

| Criterion | CP-SAT | ILP |
|-----------|--------|-----|
| Variable types | Boolean, integer | Continuous, integer, binary |
| Constraint types | Rich (AllDifferent, Circuit, etc.) | Linear only (must linearize complex constraints) |
| Modeling ease for scheduling | Higher — native constraint types | Lower — must linearize everything with Big-M, indicator constraints |
| Optimality proof | Yes (if solved within time limit) | Yes (with optimality gap and LP bound) |
| Dual bounds | Weaker for some structures | Strong LP relaxation bounds — you always know how far from optimal |
| Performance (our size) | 2-10s | 2-30s (solver-dependent) |
| Performance (10x size) | 30s-5min | 10s-2min (Gurobi), 1-10min (open source) |
| Warm-starting | Solution hints only | Full MIP start support |
| Incremental solving | Not supported | Supported (fix variables, re-solve) |
| Scheduling primitives | Native (NewIntervalVar, AddNoOverlap) | Must be encoded as linear constraints |

**Can ILP express our constraints?** Yes — all constraint types in this project map to ILP:
- Boolean/binary variables: native in MIP
- Exactly-one: `sum(x_i) == 1`
- At-most-one: `sum(x_i) <= 1`
- Weighted soft penalties: `minimize sum(w_i * p_i)` with slack variables
- Implications: `x => y` becomes `x <= y`

**Verdict**: ILP with Gurobi or CPLEX would perform **comparably or slightly better at scale**, but adds commercial licensing complexity. For open-source, CP-SAT is typically faster than HiGHS/CBC for highly combinatorial problems with many Boolean variables. ILP's main advantage is warm-starting, incremental solving, and strong LP bounds.

**When to switch**: If the problem grows to 100+ courses and warm-starting becomes important (e.g., "only reschedule these 5 courses"), ILP with Gurobi becomes attractive.

**Note on HiGHS**: HiGHS (University of Edinburgh, MIT license) won the 2023 INFORMS optimization competition for open-source solvers. It is now the default solver in PuLP 2.7+. For pure LP it's competitive with commercial solvers; for MIP it's roughly 2-5x slower than Gurobi but dramatically better than CBC/GLPK. It is the best open-source ILP option if you wanted to compare approaches.

---

### 3.2 Genetic Algorithms (GA)

**How it works**: Maintains a population of candidate schedules, applies selection, crossover, and mutation operators to evolve better solutions over generations.

**Encoding strategies for timetabling**:
- **Direct encoding**: Each gene represents (course -> time_slot, room, teacher) assignment. Simple but produces many infeasible offspring during crossover
- **Permutation encoding**: Genes define a priority ordering; a deterministic decoder greedily assigns courses to feasible slots. Guarantees feasibility by construction — the recommended approach
- **Hybrid encoding**: Encode only timeslot assignments genetically; use a separate deterministic room-assignment step to reduce search space

**Hard constraint handling** (a major challenge for GAs):
- **Penalty functions**: Hard violations get very large penalty weights (e.g., 1000x soft weights). Tuning these weights is notoriously finicky
- **Repair operators**: Fix constraint violations after crossover/mutation. More reliable but expensive and problem-specific
- **Decoder-based feasibility**: Best practice — the decoder only constructs feasible solutions, so hard constraints are never violated
- **Feasibility-first sorting** (Deb's method): Any feasible solution beats any infeasible one in tournament selection, regardless of objective

**Key characteristics**:

| Criterion | GA | CP-SAT |
|-----------|------|--------|
| Solution quality | 70-90% of optimal | 95-100% of optimal |
| Solve time | 30-120s (population-based) | 2-10s |
| Optimality guarantee | None | Yes (within time limit) |
| Hard constraint handling | Difficult — penalty or repair operators | Native |
| Scalability | Good — linear time per generation | Exponential worst-case |
| Parallelism | Embarrassingly parallel | Multi-worker search |
| Parameter tuning | Extensive (population size, crossover rate, mutation rate, selection method) | Minimal |

**Python libraries**:
- **DEAP**: Most flexible, good for custom operators. Steep learning curve
- **pymoo**: Multi-objective focused. Good for Pareto-front analysis but overkill here
- **pygad**: Simpler API but less customizable

**Verdict**: GAs are **significantly worse** for our problem size. They shine at very large instances (1000+ courses) where exact methods time out, but for small-medium problems they're slower, less reliable, and produce inferior solutions. The main advantage is that they can always produce *some* solution, even if constraints are conflicting.

**When to consider**: Only if the problem grows to 500+ courses AND optimal solutions aren't needed.

---

### 3.3 Simulated Annealing (SA)

**How it works**: Starts from a random feasible schedule, iteratively applies small modifications (moves), accepts improving moves always and worsening moves with a probability that decreases over time (temperature cooling).

**Typical moves for timetabling**:
- Swap time slots of two courses
- Move a course to a different room
- Swap teachers between two sections

**Key characteristics**:

| Criterion | SA | CP-SAT |
|-----------|------|--------|
| Solution quality | 75-90% of optimal | 95-100% of optimal |
| Solve time | 20-60s | 2-10s |
| Optimality guarantee | None (probabilistic convergence) | Yes |
| Implementation complexity | Low | Low (with OR-Tools) |
| Parameter sensitivity | High (cooling schedule is critical) | Low |
| Memory usage | Very low (single solution) | Moderate (constraint model) |

**Cooling schedule details**:
- **Geometric cooling**: `T(k+1) = alpha * T(k)`, alpha typically 0.95-0.9999. Most common but requires careful tuning
- **Initial temperature calibration**: Set T0 so ~50-80% of worsening moves are accepted initially
- **Reheating**: Periodic temperature increases help escape local optima; used by several ITC competition entries

**Verdict**: SA is **inferior to CP-SAT** for our problem size. It's simple to implement but produces worse solutions more slowly. Its only real advantage is very low memory usage and simplicity without external dependencies. SA is generally considered slightly worse than Tabu Search for timetabling specifically.

**When to consider**: Embedded systems or environments where you can't install OR-Tools and need a pure-Python solution.

---

### 3.4 Tabu Search

**How it works**: A local search method that maintains a "tabu list" of recently visited solutions/moves to prevent cycling. Systematically explores neighborhoods of the current solution, always moving to the best non-tabu neighbor.

**Historical significance**: Tabu Search (introduced by Fred Glover, 1986) was the dominant approach for timetabling from the 1990s through the 2000s. Many competition winners used Tabu Search or Tabu-based hybrids. Di Gaspero and Schaerf (2003) achieved strong results with it for course timetabling. Burke and Bykov (2008, 2012) developed the related "Late Acceptance Hill Climbing" variant with excellent timetabling results. It remains one of the core algorithms in OptaPlanner/Timefold.

**Key characteristics**:

| Criterion | Tabu Search | CP-SAT |
|-----------|------------|--------|
| Solution quality | 80-95% of optimal | 95-100% of optimal |
| Solve time | 10-30s | 2-10s |
| Optimality guarantee | None | Yes |
| Hard constraint handling | Needs feasible initial solution or repair | Native |
| Diversification | Built-in (tabu list + aspiration criteria) | Automatic (search strategies) |
| Implementation complexity | Medium (neighborhood design is critical) | Low |

**Verdict**: Tabu Search is **competitive but outclassed by CP-SAT** for this problem size. It was state-of-the-art before modern CP solvers matured. Today, CP-SAT achieves better solutions with less engineering effort. However, Tabu Search remains useful as a component in hybrid approaches.

---

### 3.5 Adaptive Large Neighborhood Search (ALNS)

**How it works**: Iteratively destroys part of the current solution (removes some course assignments) and repairs it (re-assigns them), adapting which destroy/repair operators to use based on past performance.

**Key characteristics**:

| Criterion | ALNS | CP-SAT |
|-----------|------|--------|
| Solution quality | 90-98% of optimal | 95-100% of optimal |
| Solve time | 10-60s | 2-10s |
| Scalability | Excellent — scales gracefully to large instances | Degrades exponentially |
| Hard constraint handling | Via repair heuristics | Native |
| Implementation complexity | Medium-High | Low |

**Typical destroy operators for timetabling**:
- Remove all courses for a random room
- Remove all courses in a random time slot
- Remove courses involved in the most constraint violations (worst-removal)
- Remove courses from a random student group/curriculum
- Remove a random subset of courses

**Typical repair operators**:
- Greedy insertion (assign each removed course to its best slot)
- Regret insertion (assign the course that would lose the most by waiting)
- CP-SAT repair (solve a small subproblem to optimally reinsert — this is the "matheuristic" approach)

**Python implementation**: The `alns` package (`pip install alns`) by Niels Wouda provides a general-purpose ALNS framework. You define custom destroy/repair operators; it handles the adaptive weight mechanism. Alternatively, the core loop is simple enough (~200-300 lines) to implement from scratch.

**This is notable because**: OR-Tools CP-SAT internally uses LNS as one of its parallel search workers. You are already partially benefiting from LNS within CP-SAT. However, you cannot define custom destroy/repair operators through the public API.

**Verdict**: ALNS is the **strongest alternative for scaling up**. If the problem grows significantly, implementing ALNS with CP-SAT as the repair solver (destroy some assignments, let CP-SAT re-optimize that subproblem) is a powerful hybrid approach. This is essentially what the academic state-of-the-art looks like.

---

### 3.6 Hybrid Approaches (CP + Metaheuristic)

**How it works**: Combines exact methods for local optimization with metaheuristics for global exploration. Common patterns:

1. **LNS with CP repair**: Destroy a portion of the schedule, use CP-SAT to optimally repair it. Repeat.
2. **CP first, local search refinement**: Use CP-SAT to find an initial feasible solution, then apply Tabu Search or SA to improve soft constraints.
3. **Decomposition**: Split the problem into sub-problems (e.g., per department), solve each with CP-SAT, then handle inter-department constraints with local search.

**Specific hybrid patterns**:
- **Fix-and-optimize** (matheuristic): Fix a subset of variables to current values, re-optimize the rest with an exact solver, rotate blocks. Very effective for timetabling
- **Corridor methods**: Restrict search to a "corridor" around the current solution
- **Custom LNS with OR-Tools**: Implement the destroy/repair loop in Python, calling CP-SAT repeatedly with partial hints via `model.AddHint()` or by fixing variables. This is a common and effective pattern

**Competition results**: The International Timetabling Competition (ITC) winners have predominantly used hybrid approaches:
- **ITC-2007**: Track 1 (exam timetabling): graph coloring heuristics + local search. Track 2 (post-enrollment): SA and Tabu Search variants. Track 3 (curriculum-based): Tabu Search + SA combinations. Notable: Lach & Lubbecke used ILP competitively on smaller instances. Muller's solver (later used in UniTime) placed well.
- **ITC-2019** (sports timetabling): Constraint programming, ILP decomposition, and ALNS. Teams from KU Leuven and other OR groups performed well with hybrid approaches
- **Key takeaway from all ITCs**: No single approach dominates. The best results consistently come from **hybrid methods** combining exact methods (ILP/CP) with metaheuristics

**Verdict**: Hybrids represent the **academic state-of-the-art** for large instances. For our current problem size, pure CP-SAT is sufficient. But if scaling is needed, LNS with CP-SAT repair is the recommended upgrade path.

---

### 3.7 SAT/MaxSAT Solvers Directly

**How it works**: Encode the problem as a Boolean satisfiability problem. Hard constraints become clauses; soft constraints use weighted MaxSAT or pseudo-Boolean optimization.

**Comparison to CP-SAT**: OR-Tools CP-SAT already uses SAT internally (it's a CP solver built on a SAT engine). Using a raw SAT/MaxSAT solver would require manual encoding of constraints as CNF clauses — significantly more work for no benefit.

**Verdict**: **Not recommended**. CP-SAT already leverages SAT techniques internally while providing a much friendlier API. No advantage to going lower-level.

---

### 3.8 Reinforcement Learning (RL)

**How it works**: Train an agent to sequentially assign courses to slots, learning a policy that minimizes constraint violations. Approaches include Deep Q-Networks (DQN), Policy Gradient methods, and recent transformer-based approaches.

**Current state (as of 2024-2025)**:
- Mostly academic research; no known production university timetabling system uses RL
- Works reasonably for job-shop scheduling (simpler structure) — Park et al. (2021) showed RL-based dispatching rules competitive with priority rules on job-shop benchmarks
- For UCTP specifically, the action space is huge (event x timeslot x room) and constraints are too heterogeneous for current RL methods
- Training time is orders of magnitude longer than just running CP-SAT
- Generalization is poor — a model trained on one university's constraints doesn't transfer well
- **Most promising RL direction**: Learning to select heuristics/operators within a metaheuristic framework (hyper-heuristics), e.g., learning which LNS destroy operator to apply

**Key reference**: Bengio et al. (2021) "Machine Learning for Combinatorial Optimization: A Methodological Tour d'Horizon" — balanced assessment concluding ML/RL is not yet competitive with state-of-the-art OR methods for static combinatorial optimization.

**Verdict**: **Not recommended** for production use. The field is advancing rapidly, but RL is not competitive with CP-SAT or ILP for constrained timetabling today.

---

### 3.9 Quantum-Inspired and Emerging Approaches

- **Quantum annealing** (D-Wave): Limited to QUBO formulations, small problem sizes, and only useful for unconstrained binary optimization. Not practical for timetabling.
- **Tensor network methods**: Theoretical interest only.
- **Neural combinatorial optimization**: Similar limitations to RL — not competitive with classical solvers for constrained problems.

**Verdict**: **Not recommended**. No practical advantages over classical methods for the foreseeable future.

---

## 4. Comprehensive Comparison Matrix

| Algorithm | Solution Quality | Solve Time (Our Size) | Scalability (10x) | Hard Constraints | Soft Constraints | Implementation Effort | Warm Start | Optimality Guarantee |
|-----------|-----------------|----------------------|-------------------|-----------------|-----------------|---------------------|------------|---------------------|
| **CP-SAT (current)** | 95-100% | 2-10s | Moderate | Native | Weighted penalties | Low | No | Yes |
| **ILP (Gurobi)** | 95-100% | 2-15s | Good | Linear constraints | Weighted penalties | Low-Medium | Yes | Yes |
| **ILP (HiGHS/CBC)** | 95-100% | 5-30s | Moderate | Linear constraints | Weighted penalties | Low-Medium | Yes | Yes |
| **Genetic Algorithm** | 70-90% | 30-120s | Good | Penalty/repair | Penalty function | Medium-High | N/A | No |
| **Simulated Annealing** | 75-90% | 20-60s | Good | Penalty/repair | Penalty function | Low-Medium | N/A | No |
| **Tabu Search** | 80-95% | 10-30s | Good | Penalty/repair | Penalty function | Medium | N/A | No |
| **ALNS** | 90-98% | 10-60s | Excellent | Repair heuristics | Penalty function | Medium-High | Yes | No |
| **Hybrid (CP+LNS)** | 95-99% | 10-60s | Excellent | Native (CP repair) | Weighted + search | High | Yes | No |
| **RL** | 50-80% | Hours (training) | Unknown | Learned | Learned | Very High | N/A | No |

---

## 5. Scalability Analysis

### When does CP-SAT become insufficient?

| Problem Size | Variables (est.) | CP-SAT Performance | Recommendation |
|-------------|-----------------|-------------------|----------------|
| **Current** (30 courses, 15 teachers) | ~10K | 2-10s, optimal | CP-SAT (current) |
| **2x** (60 courses, 30 teachers) | ~40-80K | 10-60s, near-optimal | CP-SAT still works |
| **5x** (150 courses, 75 teachers) | ~200-500K | 1-10min, may timeout | Consider ILP (Gurobi) or Hybrid |
| **10x** (300 courses, 150 teachers) | ~1-2M | Likely timeout | ALNS/Hybrid required |
| **University-wide** (1000+ courses) | ~10M+ | Infeasible | Decomposition + ALNS |

The pre-filtering strategy becomes even more critical at larger scales. The 22x reduction in variables is already excellent, but additional decomposition strategies (per-department, per-day) would be needed.

### Important caveat on crossover points

The scalability crossover depends heavily on **constraint structure**, not just raw problem size:
- **Tightly-constrained problems** (many hard constraints, few feasible solutions): Exact methods can struggle even at moderate sizes because the feasible region is tiny. Metaheuristics with good repair operators may find feasible solutions faster
- **Loosely-constrained problems** (mostly soft constraints, feasibility is easy): CP-SAT excels up to surprisingly large sizes because it quickly finds feasible solutions and then optimizes

**A practical heuristic**: If CP-SAT finds a good solution within your time budget, stick with it. If it's still far from the bound after several minutes, consider hybrid approaches.

---

## 6. Real-World Timetabling Software

What algorithms do production systems actually use?

| Software | License | Algorithm | Used By |
|----------|---------|-----------|---------|
| **UniTime** | Open source (Java) | Multi-phase: CP construction + hill climbing/great deluge/SA local search (Tomas Muller's solver) | Purdue University, AGH University (Poland), many others |
| **FET** | Open source (C++) | Recursive swapping heuristic (constraint-based backtracking with heuristic ordering). Despite the name, does NOT use genetic algorithms | Popular with high schools in Europe and Middle East |
| **OptaPlanner/Timefold** | Open source (Java) | Tabu Search (primary), SA, Late Acceptance Hill Climbing, Step Counting Hill Climbing, plus construction heuristics. Core team forked to Timefold Solver in 2024 | Employee rostering, vehicle routing, timetabling |
| **Scientia Syllabus Plus** | Commercial | Proprietary (reportedly CP + local search) | Most widely deployed commercial system globally for higher education (UK, Australia) |
| **CELCAT** | Commercial | Proprietary | Popular in UK and France |
| **Ad Astra/CollegeScheduler** | Commercial | Proprietary | US higher education market |

**Key observation**: Even commercial systems predominantly use hybrid approaches (exact construction + local search improvement), not pure metaheuristics or pure exact methods.

---

## 7. Recommendation

### For the Current Problem Size: Keep CP-SAT

**CP-SAT is the right choice** for this project. The reasons:

1. **Optimal solutions in seconds** — no other approach matches this for our problem size
2. **Guaranteed feasibility** — hard constraints are always satisfied
3. **Minimal tuning** — unlike metaheuristics, no parameter tuning needed
4. **Clean API** — declarative modeling is easy to maintain and extend
5. **Free and well-maintained** — Google OR-Tools is actively developed

### If Scaling Becomes Necessary: Upgrade Path

If the project needs to handle significantly larger instances (100+ courses), here is the recommended upgrade path, in order of priority:

#### Priority 1: Tune CP-SAT Parameters (Minimal effort)
- Increase `max_time_in_seconds` for larger instances
- Experiment with `num_workers` (more isn't always better)
- Use `solver.parameters.log_search_progress = True` to diagnose bottlenecks
- Add more aggressive pre-filtering to reduce variables further

#### Priority 2: Add Solution Hints (Low effort)
- While CP-SAT doesn't support warm-starting from a previous solution in the traditional sense, it supports **solution hints** via `model.AddHint(var, value)` which biases the search
- Use a previous schedule as a hint when making small changes
- This can dramatically speed up re-optimization scenarios

#### Priority 3: Problem Decomposition (Medium effort)
- Split large problems by department or building
- Solve sub-problems independently with CP-SAT
- Handle cross-department constraints in a coordination layer

#### Priority 4: LNS Hybrid (High effort, high reward)
- Implement Large Neighborhood Search with CP-SAT as the repair solver
- Randomly destroy 10-20% of assignments, re-optimize with CP-SAT
- Repeat with adaptive operator selection
- This is the state-of-the-art approach used by competition winners

#### Priority 5: Switch to ILP with Gurobi (If commercial licensing is acceptable)
- Gurobi is the fastest solver for large MIP instances
- Supports warm-starting and incremental solving natively
- Free for academic use, ~$10K+/year for commercial
- Only worth the switch if the problem regularly exceeds CP-SAT's capabilities

### Not Recommended for This Project
- **Genetic Algorithms**: Inferior solution quality, slower, more complex
- **Simulated Annealing**: No advantages over CP-SAT at this scale
- **Pure Tabu Search**: Outclassed by CP-SAT for small-medium problems
- **RL/Quantum**: Not ready for production timetabling
- **Raw SAT/MaxSAT**: CP-SAT already uses SAT internally

---

## 8. Key Takeaways

1. **CP-SAT is well-chosen for this problem** — it's the best open-source option for small-to-medium UCTP instances
2. **The pre-filtering strategy is critical** — the 22x variable reduction is as important as the solver choice
3. **Scaling concerns are premature** — at 15 teachers and 30 courses, CP-SAT has massive headroom
4. **If scaling is ever needed**, the path is: tune parameters -> add hints -> decompose -> LNS hybrid -> Gurobi
5. **Competition winners use hybrids**, but those are engineered for specific competition formats, not general usability

---

## 9. Academic References

Key papers and resources in university timetabling optimization:

### Surveys and Overviews
- Schaerf, A. (1999). "A Survey of Automated Timetabling." *Artificial Intelligence Review* — foundational survey
- Lewis, R. (2008). "A survey of metaheuristic-based techniques for University Timetabling problems" — comprehensive metaheuristic comparison
- Pillay, N. (2014). "A survey of school timetabling research." *Annals of Operations Research*
- Bettinelli, A. et al. (2015). "An overview of curriculum-based university timetabling." *TOP* — covers ILP and CP approaches
- Lemos, A. et al. (2019). "A survey on university timetabling" — meta-analysis of 150+ papers
- Bengio, Y. et al. (2021). "Machine Learning for Combinatorial Optimization: A Methodological Tour d'Horizon" — ML/RL vs classical OR assessment

### Specific Algorithms
- Glover, F. (1986). "Future paths for integer programming and links to artificial intelligence" — foundational Tabu Search paper
- Shaw, P. (1998). "Using constraint programming and local search methods to solve vehicle routing problems" — introduced LNS
- Schrimpf, G. et al. (2000). "Record Breaking Optimization Results Using the Ruin and Recreate Principle" — early LNS for scheduling
- Di Gaspero, L. & Schaerf, A. (2003). "Multi-neighbourhood local search with application to course timetabling." *PATAT*
- Ropke, S. & Pisinger, D. (2006). "An adaptive large neighborhood search heuristic for the pickup and delivery problem with time windows" — foundational ALNS paper
- Burke, E.K. & Bykov, Y. (2008, 2012). Papers on Late Acceptance Hill Climbing for timetabling

### Competitions and Benchmarks
- Muller, T. (2009). "ITC2007 solver description: a hybrid approach." *Annals of Operations Research*
- Ceschia, S. et al. (2023). "The Second International Timetabling Competition (ITC-2019): Benchmarks and Results"
- MirHassani, S.A. & Habibi, F. (2013). ILP formulations for course timetabling — widely cited

### Tools and Documentation
- Google OR-Tools CP-SAT documentation and best practices
- Hans Mittelmann's MIP benchmarks (plato.asu.edu) — solver performance comparisons
- ALNS Python package: `pip install alns` (github.com/N-Wouda/ALNS)
