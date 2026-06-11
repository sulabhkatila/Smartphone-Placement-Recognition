import os

# Configuration and Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(
    BASE_DIR,
    "smartphone-placement-recognition",
    "results",
    "models",
    "best50_features",
    "ensModel.mat",
)
FEAT_SEL_PATH = os.path.join(
    BASE_DIR,
    "smartphone-placement-recognition",
    "results",
    "models",
    "best50_features",
    "FeatSel_Results.mat",
)
