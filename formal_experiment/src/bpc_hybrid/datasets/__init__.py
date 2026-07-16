"""S2.1-B/C: dataset ingesters and official schema auditors.

All importers in this subpackage must:
  * use Python standard library only (csv, json, hashlib, zipfile, ...);
  * stream large inputs line-by-line (the official EStG_sent_vec.csv is
    ~470 MB uncompressed);
  * default to ``no-overwrite`` for any on-disk artifact;
  * never read .env, never call an LLM or external API, never write
    to references/, data/{input,gold,predictions,results}/, or outputs/
    outside the gitignore-allowed reports tree.

For the Sun modality importer, headered ``strict_one_hot`` remains a
synthetic-fixture adapter only. The complete S2.1-C scan locked the official
file as headerless positional one-hot (columns 4-7); it found no integer
modality-code column. The official adapter never guesses positions or labels,
and its guarded import fails closed on the observed normalized-text label
conflict.
"""

__all__: list[str] = []
