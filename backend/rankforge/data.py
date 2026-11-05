import csv
import json
from pathlib import Path

from .core import read_json, write_json, digest

URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/fiqa.zip"
ARCHIVE_SHA256 = "32c7df99ed21252fdfb2cf3f5673502a8d245ee0c44c4a133570d92ce2b3ad02"

# Hand-authored correctness fixture. The text is part of the artifact identity:
# changing it invalidates every bundle built from data/fixture.
FIXTURE_DOCUMENTS = [
    ("savings", "A savings account pays interest on deposited cash. Compound interest earns interest on accumulated interest."),
    ("bonds", "Bonds are debt instruments. Bond prices generally fall when market interest rates rise."),
    ("index", "An index fund tracks a market index. Diversification spreads exposure across many companies."),
    ("mortgage", "A mortgage is a loan secured by property. Fixed rate mortgages keep the same interest rate during the agreed term."),
    ("credit", "A credit score reflects borrowing history. Paying bills on time and credit utilization can affect the score."),
    ("tax", "Income tax is assessed on taxable income. Tax deductions reduce taxable income while tax credits reduce tax owed."),
    ("inflation", "Inflation is a rise in the general price level and reduces the purchasing power of money."),
    ("retirement", "Retirement accounts can offer tax advantages. Employer matching contributions add to employee savings."),
    ("fees", "Fund expense ratios are annual fees charged as a fraction of assets. Fees reduce investment returns."),
    ("risk", "Investment risk includes potential loss of capital. Volatility describes changes in price over time."),
    ("liquidity", "Liquidity describes how easily an asset can be converted to cash. An emergency fund holds accessible savings."),
    ("stocks", "A stock represents ownership in a company. Dividends distribute some company profits to shareholders."),
]

# Query ID prefix selects the split: tr -> train, dv -> dev, te -> test.
FIXTURE_QUERIES = [
    ("tr1", "How does savings interest compound?", "savings"),
    ("tr2", "Why do bond prices fall?", "bonds"),
    ("tr3", "What is a diversified index fund?", "index"),
    ("tr4", "What is a fixed mortgage?", "mortgage"),
    ("tr5", "How is my credit score affected?", "credit"),
    ("tr6", "Tax credits versus deductions", "tax"),
    ("tr7", "Why does money lose purchasing power?", "inflation"),
    ("tr8", "Employer retirement matching", "retirement"),
    ("dv1", "What are fund expense ratios?", "fees"),
    ("dv2", "What is investment volatility?", "risk"),
    ("te1", "What makes savings accessible for emergencies?", "liquidity"),
    ("te2", "Who receives company dividends?", "stocks"),
]

FIXTURE_SPLITS = [("train", "tr"), ("dev", "dv"), ("test", "te")]


def fixture(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    with (path / "corpus.jsonl").open("w") as f:
        for i, text in FIXTURE_DOCUMENTS:
            record = {"_id": i, "title": "Fixture: " + i, "text": text}
            f.write(json.dumps(record) + "\n")

    with (path / "queries.jsonl").open("w") as f:
        for i, text, _ in FIXTURE_QUERIES:
            f.write(json.dumps({"_id": i, "text": text}) + "\n")

    (path / "qrels").mkdir(exist_ok=True)
    for split, prefix in FIXTURE_SPLITS:
        with (path / "qrels" / (split + ".tsv")).open("w") as f:
            f.write("query-id\tcorpus-id\tscore\n")
            for i, _, doc in FIXTURE_QUERIES:
                if i.startswith(prefix):
                    f.write(f"{i}\t{doc}\t1\n")

    write_json(path / "provenance.json", {
        "profile": "fixture",
        "license": "MIT",
        "source": "Hand-authored correctness fixture; not a benchmark",
    })


def download(path):
    import urllib.request
    import zipfile

    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    archive = path / "fiqa.zip"

    if not archive.exists():
        print("Downloading official BEIR FiQA archive", flush=True)
        urllib.request.urlretrieve(URL, archive)
    if digest(archive) != ARCHIVE_SHA256:
        raise ValueError("FiQA archive checksum differs from the pinned release")

    with zipfile.ZipFile(archive) as z:
        # Reject entries that would escape the extraction directory.
        for info in z.infolist():
            target = (path / info.filename).resolve()
            if not target.is_relative_to(path.resolve()):
                raise ValueError("Unsafe archive path")
        z.extractall(path)

    root = path / "fiqa"
    write_json(root / "provenance.json", {
        "profile": "full FiQA",
        "source": URL,
        "archive_sha256": digest(archive),
        "license": "CC-BY-SA-4.0",
        "attribution": "FiQA-2018 contributors; BEIR (Thakur et al., 2021)",
        "card": "https://huggingface.co/datasets/BeIR/fiqa",
        "preprocessing": (
            "Original document text and IDs preserved; no chunking; "
            "lexical lowercase ASCII alphanumeric tokens."
        ),
    })
    print(f"Downloaded to {root}; SHA-256 {digest(archive)}", flush=True)


def load_data(path):
    path = Path(path)
    docs = {}

    for line in (path / "corpus.jsonl").read_text().splitlines():
        d = json.loads(line)
        i = str(d["_id"])
        if i in docs:
            raise ValueError("Duplicate source ID")
        docs[i] = {
            "id": i,
            "title": d.get("title") or "FiQA document " + i,
            "text": d["text"],
        }

    query_lines = (path / "queries.jsonl").read_text().splitlines()
    queries = {str(d["_id"]): d["text"] for d in map(json.loads, query_lines)}
    return docs, queries


def qrels(path, split):
    """Load only the explicitly requested split; training never calls this for test."""
    with (Path(path) / "qrels" / (split + ".tsv")).open() as f:
        rows = csv.DictReader(f, delimiter="\t")
        return [(r["query-id"], r["corpus-id"], int(r["score"])) for r in rows]


def audit(path):
    docs, queries = load_data(path)
    splits = {s: qrels(path, s) for s in ["train", "dev", "test"]}
    sets = {s: {q for q, _, _ in rows} for s, rows in splits.items()}

    assert not (
        sets["train"] & sets["dev"]
        or sets["train"] & sets["test"]
        or sets["dev"] & sets["test"]
    ), "Overlapping splits"
    assert all(
        q in queries and d in docs
        for rows in splits.values()
        for q, d, _ in rows
    ), "Unknown source ID"

    result = {
        "documents": len(docs),
        "queries": len(queries),
        "splits": {s: len(ids) for s, ids in sets.items()},
        "files": {
            str(p.relative_to(path)): digest(p)
            for p in sorted(Path(path).rglob("*"))
            if p.suffix in [".jsonl", ".tsv"]
        },
    }
    write_json(Path(path) / "audit.json", result)
    return result
