# Legacy notebooks (2023)

These are the original notebooks from the 2023 industry collaboration,
preserved for provenance. **Code logic, identifiers, and string literals are
unchanged**; only prose comments and markdown headings were translated to
English, and files were renamed from Korean.

They are *not runnable as-is*: they reference NDA data via hardcoded local /
Google Drive paths (e.g. `참고용 ver26.xlsx`) and reflect the manual,
spreadsheet-versioned workflow that [`src/menunorm/`](../../src/menunorm)
replaces.

| Notebook | Original name | Role in 2023 workflow |
|---|---|---|
| `remove_stopwords/01_preprocessing.ipynb` | 데이터 전처리.ipynb | Bracket/symbol removal, Google-translate pass, English cleanup |
| `remove_stopwords/02_standardization.ipynb` | 데이터 표준화.ipynb | Hand-edited regex standardization (one rule at a time) |
| `remove_stopwords/03_kmeans_clustering.ipynb` | K-means Clustering.ipynb | TF-IDF + K-means EDA that revealed the long-tail problem |
| `dictionary_based_morphological_analysis/01_preprocess.ipynb` | (same) | NA fill, symbol/bracket removal, alphabetical work split |
| `dictionary_based_morphological_analysis/02_fill_dict.ipynb` | (same) | Jongseong detection to fill the MeCab user-dictionary sheet |
| `dictionary_based_morphological_analysis/03_pos_tagging.ipynb` | (same) | MeCab POS tagging with the compiled user dictionary |

How each step evolved into the package is summarized in the
[Method table](../../README.md#method) of the main README.
