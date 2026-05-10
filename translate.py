import argparse
import csv
import sys

MODEL_NAME = "Helsinki-NLP/opus-mt-es-en"


def needs_translation(value: str | None) -> bool:
    return not (value or "").strip()


def read_rows(path: str) -> tuple[list[dict[str, str]], list[str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return rows, fieldnames


def write_rows(path: str, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--source-col", default="sentence")
    parser.add_argument("--output-col", default="english_sentence")
    parser.add_argument("--num-beams", type=int, default=1)
    args = parser.parse_args()

    rows, fieldnames = read_rows(args.input)

    if args.source_col not in fieldnames:
        raise ValueError(f"CSV must contain a '{args.source_col}' column")
    if args.output_col not in fieldnames:
        fieldnames.append(args.output_col)
        for row in rows:
            row[args.output_col] = ""

    pending_indices = [
        i for i, row in enumerate(rows)
        if needs_translation(row.get(args.output_col))
    ]
    print(f"rows needing translation: {len(pending_indices)}")

    if not pending_indices:
        write_rows(args.output, rows, fieldnames)
        print(f"saved to {args.output}")
        return

    try:
        import torch
        from tqdm import tqdm
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "missing torch translation dependency: install torch, transformers, "
            "and sentencepiece, then rerun"
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME, local_files_only=True)
    model.eval()

    pending_sentences = [
        str(rows[i].get(args.source_col) or "")
        for i in pending_indices
    ]
    indexed = sorted(
        enumerate(pending_sentences),
        key=lambda pair: len(pair[1]),
        reverse=True,
    )
    translations = [""] * len(pending_sentences)

    for i in tqdm(range(0, len(indexed), args.batch_size)):
        batch_pairs = indexed[i:i + args.batch_size]
        batch_local_indices, batch = zip(*batch_pairs)

        max_src = min(128, max(len(text.split()) * 3 for text in batch) + 10)
        inputs = tokenizer(
            list(batch),
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_src,
        )

        max_tgt = min(128, max_src + 20)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_length=max_tgt,
                num_beams=args.num_beams,
            )

        decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        for local_idx, text in zip(batch_local_indices, decoded):
            translations[local_idx] = text

    for local_idx, row_idx in enumerate(pending_indices):
        rows[row_idx][args.output_col] = translations[local_idx]

    print(f"translated rows: {len(pending_indices)}")

    write_rows(args.output, rows, fieldnames)
    print(f"saved to {args.output}")


if __name__ == "__main__":
    main()
