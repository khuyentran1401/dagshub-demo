import pickle
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from omegaconf import DictConfig
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from yellowbrick.cluster import KElbowVisualizer

from logger import BaseLogger
import mlflow
import hydra 

def get_pca_model(data: pd.DataFrame) -> PCA:

    pca = PCA(n_components=3)
    pca.fit(data)
    return pca


def reduce_dimension(df: pd.DataFrame, pca: PCA) -> pd.DataFrame:
    return pd.DataFrame(pca.transform(df), columns=["col1", "col2", "col3"])


def get_3d_projection(pca_df: pd.DataFrame) -> dict:
    """A 3D Projection Of Data In The Reduced Dimensionality Space"""
    return {"x": pca_df["col1"], "y": pca_df["col2"], "z": pca_df["col3"]}


def get_best_k_cluster(
    pca_df: pd.DataFrame, image_path: str, logger: BaseLogger
) -> pd.DataFrame:

    fig = plt.figure(figsize=(10, 8))
    fig.add_subplot(111)

    elbow = KElbowVisualizer(KMeans(), metric="distortion")

    elbow.fit(pca_df)
    elbow.fig.savefig(image_path)

    k_best = elbow.elbow_value_

    # Log
    logger.log_metrics(
        {
            "k_best": k_best,
            "score_best": elbow.elbow_score_,
        }
    )
    return k_best


def get_clusters_model(
    pca_df: pd.DataFrame, k: int, logger: BaseLogger
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    model = KMeans(n_clusters=k)

    # Log model
    logger.log_params({"model_class": type(model).__name__})
    logger.log_params({"model": model.get_params()})

    # Fit model
    return model.fit(pca_df)


def predict(model, pca_df: pd.DataFrame):
    return model.predict(pca_df)


def insert_clusters_to_df(
    df: pd.DataFrame, clusters: np.ndarray
) -> pd.DataFrame:
    return df.assign(clusters=clusters)


def plot_clusters(
    pca_df: pd.DataFrame, preds: np.ndarray, projections: dict, image_path: str
) -> None:
    pca_df["clusters"] = preds

    plt.figure(figsize=(10, 8))
    ax = plt.subplot(111, projection="3d")
    ax.scatter(
        projections["x"],
        projections["y"],
        projections["z"],
        s=40,
        c=pca_df["clusters"],
        marker="o",
        cmap="Accent",
    )
    ax.set_title("The Plot Of The Clusters")

    plt.savefig(image_path)

@hydra.main(
    config_path="../config",
    config_name="main",
)
def segment(config: DictConfig) -> None:

    # initialize logger

    mlflow.set_tracking_uri(
        "https://dagshub.com/khuyentran1401/dagshub-demo.mlflow"
    )
    with mlflow.start_run():
        logger = BaseLogger()
        logger.log_params(dict(config.process))
        logger.log_params({"num_columns": len(config.process.keep_columns)})

        data = pd.read_csv(config.intermediate.path)
        pca = get_pca_model(data)
        pca_df = reduce_dimension(data, pca)
        projections = get_3d_projection(pca_df)
        k_best = get_best_k_cluster(pca_df, config.image.kmeans, logger)
        model = get_clusters_model(pca_df, k_best, logger)
        preds = predict(model, pca_df)
        data = insert_clusters_to_df(data, preds)
        plot_clusters(
            pca_df,
            preds,
            projections,
            config.image.clusters,
        )
        data.to_csv(config.final.path, index=False)
        pickle.dump(model, open(config.model.path, "wb"))

if __name__ == "__main__":
    segment()