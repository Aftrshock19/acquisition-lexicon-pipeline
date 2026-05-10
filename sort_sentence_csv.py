#!/usr/bin/env python3

import argparse
import csv
import math
import statistics
from collections import Counter
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sort a CSV by the character length of a text column."
    )
    parser.add_argument(
        "--input",
        default="spa-eng.csv",
        help="Input CSV file path.",
    )
    parser.add_argument(
        "--output",
        default="new.csv",
        help="Output CSV file path.",
    )
    parser.add_argument(
        "--column",
        default="sentence",
        help="Column to sort by.",
    )
    parser.add_argument(
        "--stats-output",
        default="statistics.csv",
        help="Output CSV file for sentence-length statistics.",
    )
    parser.add_argument(
        "--bucket-stats-output",
        default="statistics_buckets.csv",
        help="Output CSV file for bucketed sentence-length statistics.",
    )
    return parser.parse_args()


def percentile(sorted_values: list[int], pct: float) -> float:
    if not sorted_values:
        raise ValueError("Cannot calculate a percentile for an empty list.")

    if len(sorted_values) == 1:
        return float(sorted_values[0])

    position = (len(sorted_values) - 1) * pct
    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return float(sorted_values[lower_index])

    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    weight = position - lower_index
    return lower_value + (upper_value - lower_value) * weight


def count_words(text: str) -> int:
    return len(text.split())


def write_statistics(stats_path: Path, word_counts: list[int]) -> None:
    sorted_word_counts = sorted(word_counts)
    counts = Counter(sorted_word_counts)

    with stats_path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(["metric", "value"])
        writer.writerow(["total_sentences", len(sorted_word_counts)])
        writer.writerow(["min_words", min(sorted_word_counts)])
        writer.writerow(["max_words", max(sorted_word_counts)])
        writer.writerow(["mean_words", f"{statistics.mean(sorted_word_counts):.2f}"])
        writer.writerow(["median_words", f"{statistics.median(sorted_word_counts):.2f}"])
        writer.writerow(["p10_words", f"{percentile(sorted_word_counts, 0.10):.2f}"])
        writer.writerow(["p25_words", f"{percentile(sorted_word_counts, 0.25):.2f}"])
        writer.writerow(["p75_words", f"{percentile(sorted_word_counts, 0.75):.2f}"])
        writer.writerow(["p90_words", f"{percentile(sorted_word_counts, 0.90):.2f}"])
        writer.writerow([])
        writer.writerow(["word_count", "sentence_count", "percentage"])

        total = len(sorted_word_counts)
        for word_count in sorted(counts):
            sentence_count = counts[word_count]
            percentage = (sentence_count / total) * 100
            writer.writerow([word_count, sentence_count, f"{percentage:.4f}"])


def write_bucket_statistics(
    stats_path: Path, word_counts: list[int], bucket_size: int = 5
) -> None:
    sorted_word_counts = sorted(word_counts)
    total = len(sorted_word_counts)
    bucket_counts: Counter[tuple[int, int]] = Counter()

    for word_count in sorted_word_counts:
        bucket_start = ((word_count - 1) // bucket_size) * bucket_size + 1
        bucket_end = bucket_start + bucket_size - 1
        bucket_counts[(bucket_start, bucket_end)] += 1

    with stats_path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(["bucket", "sentence_count", "percentage"])

        for bucket_start, bucket_end in sorted(bucket_counts):
            sentence_count = bucket_counts[(bucket_start, bucket_end)]
            percentage = (sentence_count / total) * 100
            writer.writerow(
                [f"{bucket_start}-{bucket_end}", sentence_count, f"{percentage:.4f}"]
            )


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    stats_output_path = Path(args.stats_output)
    bucket_stats_output_path = Path(args.bucket_stats_output)

    with input_path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        if reader.fieldnames is None or args.column not in reader.fieldnames:
            raise SystemExit(
                f"Column '{args.column}' was not found in {input_path.name}."
            )

        rows = list(reader)
        word_counts = [count_words((row.get(args.column) or "").strip()) for row in rows]
        rows.sort(
            key=lambda row: count_words((row.get(args.column) or "").strip()),
            reverse=True,
        )

    with output_path.open("w", encoding="utf-8", newline="") as outfile:
        fieldnames = ["word_count", "lemma", "sentence", "english_sentence"]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        rows_by_word_count: dict[int, list[dict[str, str]]] = defaultdict(list)

        for row in rows:
            word_count = count_words((row.get(args.column) or "").strip())
            if len(rows_by_word_count[word_count]) < 20:
                rows_by_word_count[word_count].append(row)

        for word_count in sorted(rows_by_word_count, reverse=True):
            for row in rows_by_word_count[word_count]:
                writer.writerow(
                    {
                        "word_count": word_count,
                        "lemma": row.get("lemma", ""),
                        "sentence": row.get("sentence", ""),
                        "english_sentence": row.get("english_sentence", ""),
                    }
                )

    write_statistics(stats_output_path, word_counts)
    write_bucket_statistics(bucket_stats_output_path, word_counts)


if __name__ == "__main__":
    main()
