import argparse
from pathlib import Path

from .core import write_json, digest
from .data import fixture, download, audit
from .build import build


def parse_args():
    parser = argparse.ArgumentParser(
        description="Reproducible RankForge artifact pipeline"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ["fixture", "download", "audit"]:
        p = sub.add_parser(name)
        p.add_argument("--data", required=True)

    p = sub.add_parser("index")
    p.add_argument("--data", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--revision")

    p = sub.add_parser("train")
    p.add_argument("--data", required=True)
    p.add_argument("--bundle", required=True)
    p.add_argument("--output", required=True)

    p = sub.add_parser("freeze")
    p.add_argument("--bundle", required=True)
    p.add_argument("--output", required=True)

    p = sub.add_parser("evaluate")
    p.add_argument("--data", required=True)
    p.add_argument("--bundle", required=True)
    p.add_argument("--split", choices=["dev", "test"], required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--frozen")

    return parser.parse_args()


def freeze(bundle, output):
    """Record the validated bundle hash that a test evaluation must match."""
    from .core import validate

    validate(bundle)
    write_json(output, {"bundle_sha256": digest(Path(bundle) / "manifest.json")})


def main():
    args = vars(parse_args())
    command = args.pop("command")

    if command == "fixture":
        fixture(args["data"])
    elif command == "download":
        download(args["data"])
    elif command == "audit":
        print(audit(args["data"]))
    elif command == "index":
        build(**args)
    elif command == "freeze":
        freeze(**args)
    elif command == "train":
        from .experiment import train

        train(**args)
    elif command == "evaluate":
        from .experiment import evaluate

        evaluate(**args)


if __name__ == "__main__":
    main()
