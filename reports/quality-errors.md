# Quality review — P5 tooling checkpoint

No historical prediction errors can be measured without the real corpus, gold labels and archived policy outputs. Error rate and factual-error rate are **unavailable**.

The new evaluator rejects future source/rights/graph/narrative/metric clocks, cross-split canonical events or shared documents, changed frozen manifests, incomplete/mismatched case coverage and unrelated gold citations. Its `quality_disagreements` output identifies relevance/push mismatches by case and partition; it does not equate a classification disagreement with an independently verified factual error.

Synthetic regression behavior remains covered by the existing suite: reprints, corrections, future sources, incompatible periods, low quality, WDC/SNDK separation, conditional cost effects and unknown materiality. Those tests are not a real-world error-rate benchmark.

Outstanding review work: source archive authenticity, human reviewer adjudication/agreement, output-fact checking, corpus representativeness and end-to-end security review. See `docs/historical_evaluation.md` for collection requirements.
