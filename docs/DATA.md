# Data, model, attribution
## FiQA
[Official BEIR archive](https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/fiqa.zip).
SHA-256: 32c7df99ed21252fdfb2cf3f5673502a8d245ee0c44c4a133570d92ce2b3ad02.

Verified: **57,638 documents; 6,648 queries; 5,500 train, 500 dev, 648 test queries.** All qrel IDs resolve; splits are disjoint. One original document per unit, no chunking/split reassignment. Missing titles use “FiQA document <id>” and internal links. Original URLs/authors are missing from this archive and are not invented.

The [dataset card](https://huggingface.co/datasets/BeIR/fiqa) identifies **CC BY-SA 4.0**. Attribute FiQA-2018 contributors and BEIR (Thakur et al., 2021). Preserve this notice and the [CC BY-SA 4.0 license](https://creativecommons.org/licenses/by-sa/4.0/) when redistributing corpus/adaptations. The application MIT license does not relicense the dataset.

BEIR: Nandan Thakur, Nils Reimers, Andreas Rücklé, Abhishek Srivastava, Iryna Gurevych, “BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models,” 2021. [Project](https://github.com/beir-cellar/beir).

Source text retained; lexical normalization/truncation are in RANKING.md. Full-corpus UI examples are official dev IDs 17 and 29; fixture examples are authored training queries.

## Model
[Sentence Transformers multi-qa-MiniLM-L6-cos-v1](https://huggingface.co/sentence-transformers/multi-qa-MiniLM-L6-cos-v1), revision b207367332321f8e44f96e224ef15bc607f4dbf0. Model card: 384-dimensional cosine retrieval. **Model weight license is unspecified in the pinned card/API metadata.** The upstream [missing-license discussion](https://huggingface.co/sentence-transformers/multi-qa-MiniLM-L6-cos-v1/discussions/3) remains unanswered in the page inspected. Do not substitute the Sentence Transformers software license for a model-weight license. Clarify distribution/use terms before publishing the bundled image, or select an explicitly licensed model and rebuild/retrain/evaluate it. Saved model files are bundled offline for release; initial download occurs during indexing.

Pretraining may overlap public financial text. The project guarantees separation of its supervised splits, not absence of all pretraining contamination.

## Fixture
Twelve authored explanations; eight train, two dev, two test queries. MIT alongside code. Fixture scores are correctness checks, not full-corpus benchmarks.

## Provenance
data/fiqa/provenance.json records archive source/checksum/license. audit.json records source file hashes and inventory. Bundles contain provenance, corpus hash, model revision, token limit, source-ID map, and per-file checksums. Large data/artifacts stay out of normal source commits; packaging explicitly copies them into release images.
