# Sepsis-3 criteria summary (demo)

source_id: sepsis3_summary

Educational paraphrase informed by Sepsis-3 (Singer et al., JAMA 2016). Not for clinical use. ChartProof criteria YAML is a further simplification of this summary.

## Section: Definition

Sepsis is life-threatening organ dysfunction caused by a dysregulated host response to infection. Sepsis-3 operationalizes organ dysfunction using an acute change in total SOFA score of 2 or more points consequent to infection.

## Section: Infection

There should be documented or strongly suspected infection (source, cultures, or antimicrobial therapy started for presumed infection). Infection alone without organ dysfunction is not sepsis under Sepsis-3.

## Section: Organ dysfunction indicators (simplified for demo)

Demo proxies used in ChartProof (not a full SOFA implementation):

- Lactate elevated above a demo threshold (e.g. > 2.0 mmol/L)
- Hypotension (e.g. MAP below 65 mmHg) or vasopressor use
- Acute kidney injury signal (creatinine rise)
- Thrombocytopenia
- Altered mentation / reduced GCS

These thresholds live in `data/criteria/sepsis.yaml` and are labeled educational only.

## Section: qSOFA

qSOFA (altered mentation, SBP <= 100, respiratory rate >= 22) is a bedside prompt for risk, not a definition of sepsis. ChartProof v1 does not require qSOFA for the rules verdict.

## Section: How ChartProof should cite this source

Cite `(sepsis3_summary, <section title>)`. Keep wording original; do not quote the JAMA article at length.
