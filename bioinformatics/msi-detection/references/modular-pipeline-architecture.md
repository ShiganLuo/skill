# MSI Detection Modular Pipeline Architecture

## Design Principles

1. **Pluggable components** — each stage is an abstract base class with concrete implementations
2. **Locus selection before feature engineering** — select sensitive loci first
3. **Two-level selection** — locus-level (which microsatellites) + sample-level (which aggregated features)
4. **No sklearn dependency** — use scipy/numpy for anomaly detection

## Class Hierarchy

```
MSIDetectionPipeline
├── FeatureExtractor          # site.txt → features
├── LocusSelector             # select sensitive loci
│   ├── AUCBasedLocusSelector
│   ├── UnitLengthLocusSelector
│   └── CombinedLocusSelector
├── FeatureSelector           # select sample-level features
│   ├── SingleVariableAUCSelector
│   ├── TwoStageSelector
│   └── LassoSelector
├── SampleFilter              # filter low-quality samples
│   ├── DepthFilter
│   ├── QualityFilter
│   └── CombinedFilter
└── Detector                  # anomaly detection
    ├── MahalanobisDetector
    ├── MSIPercentageDetector
    └── EnsembleDetector
```

## Pipeline Flow

```
1. Extract ALL locus features (no filter)
2. Fit locus selector on labeled data (BL MSI-H vs MSS)
3. Re-extract features (only selected loci)
4. Filter samples (min loci, depth)
5. Select sample-level features (AUC, two-stage, Lasso)
6. Train detector on MSS samples
7. Evaluate on BL (AUC, threshold)
8. Validate on PCR (if available)
9. Predict on renqun
```

## Key Abstractions

### LocusSelector

```python
class LocusSelector(ABC):
    @abstractmethod
    def fit(self, locus_data: Dict[str, List[Dict]], 
            sample_labels: Dict[str, int]) -> 'LocusSelector':
        """Fit on labeled data."""
        pass
    
    @abstractmethod
    def is_selected(self, locus_feat: Dict) -> bool:
        """Check if a locus should be included."""
        pass
```

### Detector

```python
class Detector(ABC):
    @abstractmethod
    def fit(self, X_train: np.ndarray) -> 'Detector':
        """Fit on normal (MSS) samples."""
        pass
    
    @abstractmethod
    def score(self, X: np.ndarray) -> np.ndarray:
        """Compute anomaly scores."""
        pass
    
    @abstractmethod
    def predict(self, X: np.ndarray, threshold: float) -> np.ndarray:
        """Predict MSI status."""
        pass
```

## Usage Example

```python
# Initialize components
feature_extractor = FeatureExtractor(min_depth=10)
locus_selector = AUCBasedLocusSelector(auc_threshold=0.6)
feature_selector = TwoStageSelector(auc_threshold=0.6, top_k=50)
sample_filter = QualityFilter(min_loci=100)
detector = MahalanobisDetector()

# Create pipeline
pipeline = MSIDetectionPipeline(
    feature_extractor=feature_extractor,
    locus_selector=locus_selector,
    feature_selector=feature_selector,
    sample_filter=sample_filter,
    detector=detector,
)

# Run
results = pipeline.run(meta_df, n_sigma=3.0)
```

## CLI Interface

```bash
python anomaly_detection_v2.py \
    --all-info all_info.tsv \
    --output-dir results/ \
    --min-depth 10 \
    --locus-selector auc \
    --selector twostage \
    --top-k 50 \
    --n-sigma 3.0
```

## Extension Points

To add a new detector:
```python
class MyDetector(Detector):
    def fit(self, X_train):
        # Learn normal distribution
        return self
    
    def score(self, X):
        # Return anomaly scores (higher = more anomalous)
        return scores
    
    def predict(self, X, threshold):
        # Return 'MSI-H' or 'MSS'
        return np.where(scores >= threshold, 'MSI-H', 'MSS')
```

To add a new locus selector:
```python
class MyLocusSelector(LocusSelector):
    def fit(self, locus_data, sample_labels):
        # Learn which loci are sensitive
        return self
    
    def is_selected(self, locus_feat):
        # Return True if locus should be included
        return True/False
```
