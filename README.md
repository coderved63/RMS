# Failure Recovery System Using Agentic AI in Software Development

A multi-agent framework for automated software debugging and failure recovery, built as part of the **Research Methodology and Seminar (RMS)** course — B.Tech CSE, Semester VI, Nirma University (AY 2025-26).

---

## Overview

Modern software systems frequently experience failures such as compilation errors, runtime exceptions, logical bugs, and test case failures. Manual debugging is time-consuming, error-prone, and expensive. This project implements an **Agentic AI-based failure recovery system** that automatically detects, analyzes, localizes, and fixes software bugs using a structured multi-agent pipeline powered by Large Language Models (LLMs).

The system is evaluated on the **QuixBugs** benchmark — a well-known dataset of 40 single-line bugs in classic algorithm implementations, widely used in Automated Program Repair (APR) research.

---

## Architecture

The system follows a **6-agent architecture** coordinated by a central recovery loop:

```
┌──────────────────────────────────────────────────────────────────┐
│                      COORDINATOR AGENT                           │
│                  (Manages recovery loop)                          │
│                                                                  │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│   │   Agent 1:    │   │   Agent 2:    │   │   Agent 3:    │       │
│   │   Failure     │──▶│    Code       │──▶│   Debugging   │       │
│   │  Detection    │   │ Localization  │   │   Analysis    │       │
│   │   (LLM)      │   │   (LLM)       │   │   (LLM)       │       │
│   └──────────────┘   └──────────────┘   └──────────────┘       │
│          │                                       │               │
│          ▼                                       ▼               │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│   │   Agent 6:    │   │   Agent 5:    │   │   Agent 4:    │       │
│   │  Validation   │◀──│    Patch      │◀──│    Patch      │       │
│   │  (Python)     │   │ Application   │   │  Generation   │       │
│   │              │   │  (Python)      │   │   (LLM)       │       │
│   └──────────────┘   └──────────────┘   └──────────────┘       │
│          │                                                       │
│          ▼                                                       │
│   ┌──────────────────────────────────────┐                      │
│   │  All tests pass? ──▶ SUCCESS         │                      │
│   │  Tests fail?     ──▶ RETRY (max 3)   │                      │
│   └──────────────────────────────────────┘                      │
└──────────────────────────────────────────────────────────────────┘
```

### Agent Descriptions

| Agent | Role | Uses LLM? |
|-------|------|-----------|
| **1. Failure Detection** | Runs tests on buggy code, captures errors, and classifies the failure type (WrongOutput, InfiniteLoop, RuntimeError, etc.) using LLM analysis | Yes |
| **2. Code Localization** | Identifies the exact faulty line number and content in the source code | Yes |
| **3. Debugging** | Performs root cause analysis and proposes a fix strategy (what to change and why) | Yes |
| **4. Patch Generation** | Generates the complete corrected function based on the debugging analysis | Yes |
| **5. Patch Application** | Applies the generated patch and verifies it compiles successfully | No |
| **6. Validation** | Runs all test cases against the patched code to verify correctness | No |

**4 LLM calls per attempt, max 3 attempts per bug = max 12 LLM calls per bug.**

---

## Dataset: QuixBugs Benchmark

[QuixBugs](https://github.com/jkoppel/QuixBugs) is a multi-lingual program repair benchmark containing **40 classic algorithm programs**, each with exactly **one single-line bug**. It includes both Python and Java versions along with test cases.

- **Programs**: Sorting (quicksort, mergesort, bucketsort), Search (find_in_sorted, find_first_in_sorted), Graph algorithms (shortest_paths, topological_ordering), Dynamic programming (knapsack, lcs_length), Mathematical (gcd, bitcount, sqrt), and more
- **Bug Types**: Operator replacement, boundary condition errors, variable swaps, incorrect array slicing, missing conditions
- **Test Cases**: 31 programs have JSON test cases (used in our evaluation); 9 graph-based programs require special test setup
- **Citation**: Lin et al., "QuixBugs: A Multi-Lingual Program Repair Benchmark Set Based on the Quixey Challenge," ACM SPLASH 2017

---

## Project Structure

```
review2/
├── src/
│   ├── config.py              # API key config + model settings
│   ├── gemini_client.py       # Gemini API wrapper with rate limiting + retries
│   ├── agents.py              # All 6 agent classes
│   ├── coordinator.py         # Recovery loop orchestrator
│   ├── run_experiment.py      # Run multi-agent system on all QuixBugs programs
│   ├── baseline.py            # Single-prompt baseline (for comparison)
│   ├── analyze_results.py     # Generate metrics, tables, and charts
│   ├── test_api.py            # Quick test to verify Gemini API key works
│   └── test_one.py            # Test on a single bug (bitcount) for quick validation
├── dataset/
│   └── quixbugs/              # QuixBugs benchmark dataset
│       ├── python_programs/   # 40 buggy Python programs
│       ├── correct_python_programs/  # 40 correct versions
│       ├── json_testcases/    # Test cases for 31 programs
│       └── ...
├── results/                   # Experiment results (generated after running)
│   ├── results.csv            # Multi-agent results
│   ├── baseline_results.csv   # Baseline results
│   ├── results_detailed.json  # Full agent logs per bug
│   └── figures/               # Generated charts and tables
├── report/
│   ├── main.tex               # Full IEEE-format LaTeX paper
│   └── references.bib         # Bibliography
├── requirements.txt           # Python dependencies
├── .env.example               # Template for API key configuration
├── PPT-RMS.pdf                # Review 1 presentation
├── final report.docx          # Review 1 report
└── final report.pdf           # Review 1 report (PDF)
```

---

## Setup & Installation

### Prerequisites
- Python 3.8+
- A Google Gemini API key ([Get one free](https://aistudio.google.com/apikey))

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Configure API Key

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:

```
GEMINI_API_KEY=your_api_key_here
```

### Step 3: Verify API Key

```bash
cd src
python test_api.py
```

You should see `ALL TESTS PASSED — Your API key is working!`

---

## Running the Experiments

### Quick Test (Single Bug)

Test the system on one bug (`bitcount`) to verify everything works:

```bash
cd src
python test_one.py
```

Expected output: System detects the bug (`^=` instead of `&=`), generates a fix, and validates it — all 5 tests pass.

### Full Multi-Agent Experiment

Run the 6-agent recovery system on all 31 QuixBugs programs:

```bash
python run_experiment.py
```

- Takes approximately **30-50 minutes** (due to API rate limiting)
- Results are saved after **each bug** — safe to interrupt and resume
- Saves to `results/results.csv` and `results/results_detailed.json`

### Baseline Experiment

Run the single-prompt baseline for comparison:

```bash
python baseline.py
```

- One LLM call per bug, no agents, no iteration
- Also supports resume — safe to interrupt
- Saves to `results/baseline_results.csv`

### Generate Analysis & Charts

After both experiments complete:

```bash
python analyze_results.py
```

Generates:
- `results/figures/success_rate_comparison.png` — Multi-agent vs Baseline bar chart
- `results/figures/pass_at_1_comparison.png` — Pass@1 comparison
- `results/figures/per_program_results.png` — Per-bug success/failure visualization
- `results/figures/results_table.png` — Summary metrics table

---

## Evaluation Metrics

| Metric | Description |
|--------|-------------|
| **Repair Success Rate** | Percentage of bugs successfully fixed (all tests pass) |
| **Pass@1** | Bugs fixed on the first attempt |
| **Pass@3** | Bugs fixed within 3 attempts |
| **MTTR** | Mean Time to Recovery — average time to fix a bug |
| **Average Attempts** | Mean number of retry attempts for successfully fixed bugs |
| **Invalid Patch Rate** | Patches that compile but fail tests |
| **Compilation Failure Rate** | Patches with syntax errors |

---

## How the Recovery Loop Works

For each buggy program:

1. **Failure Detection**: Run buggy code against test cases. Capture error output. LLM classifies the failure type and key observations.

2. **Code Localization**: LLM analyzes the numbered source code + failure info to pinpoint the exact faulty line.

3. **Debugging**: LLM performs root cause analysis — explains *why* the bug occurs and proposes a specific fix strategy (e.g., "change `^=` to `&=`").

4. **Patch Generation**: LLM generates the complete corrected function based on the debugging analysis.

5. **Patch Application**: Pure Python — applies the patch and verifies it compiles without syntax errors.

6. **Validation**: Pure Python — executes all test cases against the patched code with a 5-second timeout per test (catches infinite loops).

7. **Retry**: If validation fails, the Coordinator feeds the error back into the pipeline for another attempt (up to 3 total).

---

## Model Configuration

| Parameter | Value |
|-----------|-------|
| Model | Gemini 3.1 Flash Lite (Preview) |
| Temperature | 0.2 |
| Max Output Tokens | 2048 |
| Max Retry Attempts | 3 per bug |
| API Rate Limit | 4s delay between calls |
| Test Execution Timeout | 5s per test case |
| API Error Retry | Exponential backoff (10s → 20s → 40s → 80s) |

The model can be changed in `src/config.py`. Supported options include any model available on the Gemini API free tier.

---

## Resume Support

Both `run_experiment.py` and `baseline.py` support **automatic resume**:

- Results are saved to CSV after **every single bug**
- On restart, completed bugs are detected and **automatically skipped**
- No work is ever lost — even if the API crashes mid-experiment
- Just re-run the same command to continue from where it stopped

---

## LaTeX Report

The `report/` directory contains the full IEEE-format research paper:

- `main.tex` — Complete paper with all sections (Abstract, Introduction, Literature Review, Proposed System, Implementation, Results, Conclusion)
- `references.bib` — Bibliography in BibTeX format

Compile on [Overleaf](https://www.overleaf.com) or locally with:

```bash
cd report
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.8+ |
| LLM Provider | Google Gemini API (free tier) |
| LLM SDK | `google-genai` |
| Benchmark | QuixBugs (40 programs, 31 with JSON tests) |
| Orchestration | Custom multi-agent framework (plain Python) |
| Visualization | Matplotlib |
| Report | LaTeX (IEEEtran class) |

---

## Authors

- **Meet Patel** (23BCE177)
- **Vedant Mehta** (23BCE180)

**Guide**: Mr. AjayKumar Patel

School of Technology, Institute of Technology, Nirma University, Ahmedabad-382481

---

## References

1. Lin, D. et al., "QuixBugs: A Multi-Lingual Program Repair Benchmark Set Based on the Quixey Challenge," ACM SPLASH Companion, 2017.
2. Jimenez, C.E. et al., "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?," arXiv:2310.06770, 2023.
3. Xia, C.S. et al., "Automated Program Repair in the Era of Large Pre-trained Language Models," ICSE, 2023.
4. Yang, J. et al., "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering," arXiv:2405.15793, 2024.
5. Google, "Gemini API Documentation," https://ai.google.dev, 2024.

---

## License

This project is for academic purposes as part of the RMS course at Nirma University.
The QuixBugs dataset is used under its original [MIT License](https://github.com/jkoppel/QuixBugs/blob/master/LICENSE).
