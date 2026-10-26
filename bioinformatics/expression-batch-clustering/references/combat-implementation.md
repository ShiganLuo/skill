# ComBat Implementation Reference

## Algorithm (Johnson et al. 2007)

### Step 1: OLS estimation
```python
batch_design = pd.get_dummies(batch).values  # (n_samples, n_batch)
B_hat = np.linalg.lstsq(batch_design, df.values.T)[0]  # (n_batch, n_genes)
grand_mean = B_hat.mean(axis=0)
var_pooled = ((df.values.T - batch_design @ B_hat) ** 2).mean(axis=0)
```

### Step 2: Batch-specific parameters
```python
gamma_hat = B_hat - grand_mean  # additive effect
delta_hat = batch_data.std(axis=0, ddof=1)  # multiplicative effect per batch
```

### Step 3: Empirical Bayes shrinkage (method of moments)
```python
# Prior for gamma: Normal(g_bar, tau^2)
g_bar = gamma_hat[i].mean()
tau2 = gamma_hat[i].var()

# Prior for delta: InverseGamma on log(delta^2)
log_d2 = np.log(delta_hat[i] ** 2)
d_bar = log_d2.mean()
v = log_d2.var()

# Posterior gamma (shrinkage toward g_bar)
gamma_star[i] = (n_b * gamma_hat[i] / var_pooled + g_bar / tau2) / \
                (n_b / var_pooled + 1 / tau2)

# Posterior delta (shrinkage on log scale)
v_star = 1.0 / (n_b / 2.0 + 1.0 / v)
d_star = (n_b / 2.0 * np.log(delta_hat[i] ** 2) + d_bar / v) * v_star
delta_star[i] = np.exp(d_star / 2.0)
```

### Step 4: Apply correction
```python
y_corrected = (y - gamma_star) / delta_star * sqrt(var_pooled) + grand_mean
```

## Edge cases

- n_b <= 1: skip shrinkage, use raw gamma_hat/delta_hat
- tau2 == 0: skip shrinkage (no prior variance)
- var_pooled.min() == 0: skip shrinkage (gene has zero variance)
- NaN/inf in output: replace with 0.0 via np.nan_to_num

## scanpy alternative

If scanpy is available:
```python
import scanpy as sc
adata = sc.AnnData(df.T.values, obs=pd.DataFrame(index=df.columns))
adata.obs['batch'] = batch.values
sc.pp.combat(adata, key='batch')
result = adata.X.T
```
