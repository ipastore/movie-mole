from __future__ import annotations

from .pipeline import (
    INGESTION_MANIFEST_PATH,
    build_dataset,
    manifest_for,
    verify_sources,
    write_manifest,
)


def main() -> None:
    source_hash = verify_sources()
    dataset = build_dataset()
    manifest = manifest_for(dataset, source_hash)
    write_manifest(manifest)

    print(f"sourceManifestHash {source_hash}")
    for label, count in manifest["nodes"].items():
        print(f"{label} {count:,}")
    for relationship, count in manifest["relationships"].items():
        suffix = f" (K={manifest['similarityK']})" if relationship == "SIMILAR_TO" else ""
        print(f"{relationship} {count:,}{suffix}")
    if dataset.similarity_peak_rss_mib is not None:
        print(f"similarity peak RSS {dataset.similarity_peak_rss_mib:.1f} MiB")
    print(f"manifest {INGESTION_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
