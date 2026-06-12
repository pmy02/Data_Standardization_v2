"""Label discovery: propose new canonical labels from unmatched names.

In the original project, K-means over TF-IDF vectors was used once as EDA to
diagnose the long-tail problem. Here clustering is given a precise job in the
loop: names the canonicalizer *abstained* on are grouped, and each group's
most frequent member is proposed as a candidate canonical label for human
review. This turns "manual standardization" into a review queue.
"""

from __future__ import annotations

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


def propose_labels(
    names: list[str],
    max_clusters: int = 15,
    min_cluster_size: int = 3,
    seed: int = 42,
) -> pd.DataFrame:
    """Cluster unmatched names and extract a representative per cluster.

    Args:
        names: Unmatched normalized names (duplicates allowed; frequency is
            used to pick representatives).
        max_clusters: Upper bound on the number of proposed labels.
        min_cluster_size: Clusters smaller than this are not proposed.
        seed: Random seed for K-means.

    Returns:
        DataFrame with columns ``proposed_label``, ``cluster_size``,
        ``examples`` sorted by cluster size (descending). Empty if there is
        not enough material to cluster.
    """
    series = pd.Series([n for n in names if n and n.strip()])
    if series.empty or series.nunique() < 2:
        return pd.DataFrame(columns=["proposed_label", "cluster_size", "examples"])

    unique = series.value_counts()  # name -> frequency
    k = int(min(max_clusters, max(2, unique.size // max(min_cluster_size, 1))))
    k = min(k, unique.size)

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
    matrix = vectorizer.fit_transform(unique.index.tolist())
    kmeans = KMeans(n_clusters=k, random_state=seed, n_init=10).fit(matrix)

    frame = pd.DataFrame(
        {"name": unique.index, "freq": unique.values, "cluster": kmeans.labels_}
    )
    rows = []
    for cluster_id, group in frame.groupby("cluster"):
        size = int(group["freq"].sum())
        if size < min_cluster_size:
            continue
        top = group.sort_values("freq", ascending=False)
        rows.append(
            {
                "proposed_label": top.iloc[0]["name"],
                "cluster_size": size,
                "examples": ", ".join(top["name"].head(5)),
            }
        )
    result = pd.DataFrame(rows, columns=["proposed_label", "cluster_size", "examples"])
    return result.sort_values("cluster_size", ascending=False).reset_index(drop=True)
