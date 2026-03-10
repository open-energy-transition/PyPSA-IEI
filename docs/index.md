# PyPSA-IEI Documentation

**PyPSA-Eur-IEI** is an energy-system model based on the open-source
[PyPSA-Eur](https://github.com/PyPSA/pypsa-eur) framework (release 0.10),
extended to meet the needs of the study:

> *"Integrated Infrastructure Planning and 2050 Climate Neutrality:
> Deriving Future-Proof European Energy Infrastructures"*
> — Fraunhofer IEG, Fraunhofer ISI and d-fine (November 2025)

---

## About the Model

PyPSA-IEI performs **myopic pathway optimisation** of the European energy
system across multiple planning horizons (2020–2050). It covers electricity,
hydrogen, gas, heat and industry sectors in an integrated framework.

Key extensions over PyPSA-Eur include:

- TYNDP-based electricity and gas network enforcement
- Hydrogen network (Wasserstoffkernnetz + ENTSO-G)
- Energy import modelling (H₂, syngas, synfuel)
- TransHyDe-based industrial demand
- Custom cost assumptions and powerplant lifetimes

---

## Quick Links

- [Installation](installation.md) — set up the environment and input data
- [Model Functionality](functionality.md) — detailed description of model extensions

---

## Contributors

**d-fine GmbH** — Robert Beestermöller, Caroline Blocher, Lukas Czygan,
Linus Erdmann, Felix Greven, Paula Hartnagel, Julian Hohmann, Paul Kock,
Julius Meyer, Ari Pankiewicz, Anna Thünen

**Fraunhofer IEG** — Benjamin Pfluger, Mario Ragwitz, Caspar Schauß

**Fraunhofer ISI** — Khaled Al-Dabbas, Sirin Alibas, Wolfgang Eichhammer,
Tobias Fleiter

For inquiries: [wolfgang.eichhammer@isi.fraunhofer.de](mailto:wolfgang.eichhammer@isi.fraunhofer.de)
or [info@d-fine.com](mailto:info@d-fine.com)
