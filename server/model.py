import matio
import os
import numpy as np

from configs import MODEL_PATH, FEAT_SEL_PATH


class Model:
    def __init__(self) -> None:
        self.selected_features = []
        self.class_names = ["LB", "H", "BP", "FP", "CP", "SB"]
        self.parsed_trees = []
        self.learner_weights = []

    def _predict_tree(self, x: np.ndarray, tree: dict) -> np.ndarray:
        children = tree["children"]
        cut_var = tree["cut_var"]
        cut_point = tree["cut_point"]
        class_prob = tree["class_prob"]

        node = 0
        while True:
            left_child = children[node, 0]
            right_child = children[node, 1]

            if left_child == 0 and right_child == 0:
                return class_prob[node]

            v = cut_var[node] - 1
            val = x[v]

            if val < cut_point[node]:
                node = left_child - 1
            else:
                node = right_child - 1

    def run_predictions(self, x: np.ndarray) -> dict[str, float]:
        scores = np.zeros(len(self.class_names))
        for t_idx, tree in enumerate(self.parsed_trees):
            prob = self._predict_tree(x, tree)
            scores += self.learner_weights[t_idx] * prob

        total = scores.sum()
        if total > 0:
            scores = scores / total
        else:
            scores = np.full(len(self.class_names), 1.0 / len(self.class_names))

        top_idx = int(np.argmax(scores))
        scores = np.round(scores, 5)
        scores[top_idx] += round(1.0 - scores.sum(), 5)

        return dict(zip(self.class_names, scores))


def get_model() -> Model:
    model = Model()

    print("Loading model and feature list...")
    if not os.path.exists(MODEL_PATH) or not os.path.exists(FEAT_SEL_PATH):
        raise FileNotFoundError(
            f"Model or Feature Selection files missing at: {MODEL_PATH} or {FEAT_SEL_PATH}"
        )

    # Load feature selection results
    feat_data = matio.load_from_mat(FEAT_SEL_PATH)
    model.selected_features = [
        str(s[0]) if hasattr(s, "flat") else str(s)
        for s in feat_data["selected_features"].flat
    ]
    print(f"Loaded {len(model.selected_features)} selected features.")

    # Load ensemble model
    model_data = matio.load_from_mat(MODEL_PATH)
    ens_model = model_data["ensModel"]

    # Extract learners and weights
    impl = ens_model.properties["Impl"]
    learners = impl.properties["Trained"].flat
    weights = impl.properties["Combiner"].properties["LearnerWeights"].flat
    model.learner_weights = np.array([w for w in weights])

    # Pre-parse learners for fast traversal in Python
    model.parsed_trees = []
    for learner in learners:
        tree_impl = learner.properties["Impl"]
        children = tree_impl.properties["Children"].astype(int)
        cut_var = tree_impl.properties["CutVar"].flatten().astype(int)
        cut_point = tree_impl.properties["CutPoint"].flatten()
        class_prob = tree_impl.properties["ClassProb"]

        model.parsed_trees.append(
            {
                "children": children,
                "cut_var": cut_var,
                "cut_point": cut_point,
                "class_prob": class_prob,
            }
        )
    print(f"Loaded ensemble of {len(model.parsed_trees)} decision trees successfully.")
    return model


# Label Mapping Functions
def map_to_5_classes(label: str) -> str:
    if label in ("FP", "BP"):
        return "TP"
    return label


def map_to_4_classes(label: str) -> str:
    if label in ("BP", "FP", "CP"):
        return "P"
    return label
