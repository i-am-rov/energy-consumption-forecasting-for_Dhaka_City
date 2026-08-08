"""Stable public model numbers and their replaceable artifact definitions.

Keep a model number stable when replacing or retraining its artifact.  To add a
new model later, add one enum value and one registry entry here; API consumers
do not need to know artifact filenames.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIRECTORY = PROJECT_ROOT / "models" / "artifacts"


class ModelId(IntEnum):
    LINEAR_REGRESSION = 1
    RIDGE_REGRESSION = 2
    LASSO_REGRESSION = 3
    K_NEAREST_NEIGHBORS = 4
    RANDOM_FOREST = 5
    EXTRA_TREES = 6
    CATBOOST = 7
    GRADIENT_BOOSTING = 8
    SVR_RBF = 9
    MLP_REGRESSOR = 10
    VOTING_REGRESSOR = 11


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    id: ModelId
    name: str
    family: str
    artifact_filename: str
    artifact_format: str = "joblib"
    description: str = ""

    @property
    def artifact_path(self) -> Path:
        return MODEL_DIRECTORY / self.artifact_filename


MODEL_REGISTRY: dict[ModelId, ModelDefinition] = {
    ModelId.LINEAR_REGRESSION: ModelDefinition(
        ModelId.LINEAR_REGRESSION,
        "Linear Regression",
        "Linear",
        "linear_regression.joblib",
        description="Ordinary least-squares linear baseline.",
    ),
    ModelId.RIDGE_REGRESSION: ModelDefinition(
        ModelId.RIDGE_REGRESSION,
        "Ridge Regression",
        "Linear",
        "ridge_regression.joblib",
        description="L2-regularized linear regression.",
    ),
    ModelId.LASSO_REGRESSION: ModelDefinition(
        ModelId.LASSO_REGRESSION,
        "Lasso Regression",
        "Linear",
        "lasso_regression.joblib",
        description="L1-regularized linear regression.",
    ),
    ModelId.K_NEAREST_NEIGHBORS: ModelDefinition(
        ModelId.K_NEAREST_NEIGHBORS,
        "K-Nearest Neighbors",
        "Distance-based",
        "knn_regressor.joblib",
        description="Distance-weighted K-nearest-neighbors regression.",
    ),
    ModelId.RANDOM_FOREST: ModelDefinition(
        ModelId.RANDOM_FOREST,
        "Random Forest",
        "Tree-based",
        "random_forest_regressor.joblib",
        description="Bagged decision-tree ensemble.",
    ),
    ModelId.EXTRA_TREES: ModelDefinition(
        ModelId.EXTRA_TREES,
        "Extra Trees",
        "Tree-based",
        "extra_trees_regressor.joblib",
        description="Highly randomized decision-tree ensemble.",
    ),
    ModelId.CATBOOST: ModelDefinition(
        ModelId.CATBOOST,
        "CatBoost",
        "Boosting",
        "catboost_regressor.cbm",
        "catboost",
        "Gradient boosting with native categorical-feature handling.",
    ),
    ModelId.GRADIENT_BOOSTING: ModelDefinition(
        ModelId.GRADIENT_BOOSTING,
        "Gradient Boosting",
        "Boosting",
        "gradient_boosting_regressor.joblib",
        description="Huber-loss gradient-boosted decision trees.",
    ),
    ModelId.SVR_RBF: ModelDefinition(
        ModelId.SVR_RBF,
        "SVR (RBF)",
        "Kernel-based",
        "svr_rbf.joblib",
        description="Nonlinear support-vector regression using an RBF kernel.",
    ),
    ModelId.MLP_REGRESSOR: ModelDefinition(
        ModelId.MLP_REGRESSOR,
        "MLP Regressor",
        "Neural network",
        "mlp_regressor.joblib",
        description="Feed-forward multilayer perceptron regressor.",
    ),
    ModelId.VOTING_REGRESSOR: ModelDefinition(
        ModelId.VOTING_REGRESSOR,
        "Voting Regressor",
        "Advanced ensemble",
        "voting_regressor.joblib",
        description="Voting average of Ridge, Extra Trees, and Gradient Boosting.",
    ),
}


if set(MODEL_REGISTRY) != set(ModelId):
    raise RuntimeError("Every ModelId must have exactly one registry entry.")


def model_definitions() -> tuple[ModelDefinition, ...]:
    """Return definitions in stable numeric order."""

    return tuple(MODEL_REGISTRY[model_id] for model_id in ModelId)
