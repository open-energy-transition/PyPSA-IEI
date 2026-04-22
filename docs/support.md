# Support & Reporting Issues

If you encounter a problem — whether during installation, while running the
pipeline, or with unexpected results — please open an issue on the GitHub
repository so the team can help.

**Issues tracker:**
[github.com/open-energy-transition/PyPSA-IEI/issues](https://github.com/open-energy-transition/PyPSA-IEI/issues)

For a general guide on how to create a GitHub issue, see the
[official GitHub documentation](https://docs.github.com/en/issues/tracking-your-work-with-issues/creating-an-issue).

---

## When to Open an Issue

Open an issue for any of the following:

- **Installation failure** — conda environment creation errors, missing packages, or import errors
- **Pipeline crash** — a Snakemake rule fails with an error traceback
- **Wrong or unexpected results** — outputs that differ from the published study without an obvious explanation
- **Missing or incorrect input data** — files that cannot be retrieved or produce errors when parsed
- **Documentation problems** — unclear instructions, broken links, or missing information

---

## What to Include in Your Report

A good issue report allows the team to reproduce and fix the problem quickly.
Please include the following:

**1. Environment information**

```bash
conda activate pypsa-iei
conda list | grep -E "pypsa|snakemake|python|linopy|gurobi"
```

Also state your operating system (Windows / Linux / macOS) and version.

**2. The error message** *(recommended)*

If possible, copy the complete traceback from the terminal as text — this
allows the team to search and analyse it directly. If that is not convenient,
a screenshot of the terminal output is also acceptable.

For Snakemake errors, the most useful information is usually in the log file
for the failing rule rather than the terminal itself:

```bash
cat logs/<rule_name>.log
```

**3. The config file used**

State which scenario config was used (e.g. `config/scenarios/config.SE.yaml`)
and paste any relevant settings you modified.

**4. Steps to reproduce** *(optional — helpful for unexpected results)*

If the issue is not a straightforward crash, briefly describe what you did
and what you expected to happen instead. For example, which planning horizon
failed, or which config settings were changed.

**5. Expected vs actual behaviour**

Briefly state what you expected to happen and what actually happened.

---

## Checking Existing Issues

Before opening a new issue, search the
[existing issues](https://github.com/open-energy-transition/PyPSA-IEI/issues)
to see if your problem has already been reported or resolved.
