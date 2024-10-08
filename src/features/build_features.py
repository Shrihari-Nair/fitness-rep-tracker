import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from DataTransformation import LowPassFilter, PrincipalComponentAnalysis
from TemporalAbstraction import NumericalAbstraction
from FrequencyAbstraction import FourierTransformation
from sklearn.cluster import KMeans

# --------------------------------------------------------------
# Load data
# --------------------------------------------------------------
df = pd.read_pickle("../../data/interim/02_outliers_removed_chauvenets.pkl")
predictor_columns = list(df.columns[:6])

plt.style.use("seaborn-v0_8-deep")
plt.rcParams["figure.figsize"] = (20,5)
plt.rcParams["figure.dpi"] = 100
# --------------------------------------------------------------
# Dealing with missing values (imputation)
# --------------------------------------------------------------
for col in predictor_columns:
    df[col] = df[col].interpolate()

# --------------------------------------------------------------
# Calculating set duration
# --------------------------------------------------------------

for s in df["set"].unique():
    start = df[df["set"] == s].index[0]
    stop = df[df["set"] == s].index[-1]
    duration = stop - start
    df.loc[(df["set"] == s), "duration"] = duration.seconds

duration_df = df.groupby(["category"])["duration"].mean()




# --------------------------------------------------------------
# Butterworth lowpass filter
# --------------------------------------------------------------

df_lowpass = df.copy()
LowPass = LowPassFilter()
fs = 1000/200
cutoff = 1.3
df_lowpass = LowPass.low_pass_filter(df_lowpass,"acc_y",fs,cutoff,order=5)

for col in predictor_columns:
    df_lowpass = LowPass.low_pass_filter(df_lowpass,col,fs,cutoff,order=5)
    df_lowpass[col] = df_lowpass[col+"_lowpass"]
    del df_lowpass[col+"_lowpass"]


# --------------------------------------------------------------
# Principal component analysis PCA
# --------------------------------------------------------------

df_pca = df_lowpass.copy()
PCA = PrincipalComponentAnalysis()
pc_values = PCA.determine_pc_explained_variance(df_pca,predictor_columns)
df_pca = PCA.apply_pca(df_pca,predictor_columns,3) #  3 based on pc_values and elbow method.

# --------------------------------------------------------------
# Sum of squares attributes
# --------------------------------------------------------------
df_squared = df_pca.copy()
acc_r = df_squared["acc_x"]**2 + df_squared["acc_y"]**2 + df_squared["acc_z"]**2
gyr_r = df_squared["gyr_x"]**2 + df_squared["gyr_y"]**2 + df_squared["gyr_z"]**2
df_squared["acc_r"] = np.sqrt(acc_r)
df_squared["gyr_r"] = np.sqrt(gyr_r)


# --------------------------------------------------------------
# Temporal abstraction
# --------------------------------------------------------------

df_temporal = df_squared.copy()
NumAbs = NumericalAbstraction()
predictor_columns = predictor_columns+["acc_r","gyr_r"]
ws = int(1000/200)

for col in predictor_columns:
    df_temporal = NumAbs.abstract_numerical(df_temporal,[col],ws,"mean")
    df_temporal = NumAbs.abstract_numerical(df_temporal,[col],ws,"std")


df_temporal_list = []
for s in df_temporal["set"].unique():
    subset = df_temporal[df_temporal["set"] == s].copy()
    for col in predictor_columns:
        subset = NumAbs.abstract_numerical(subset,[col],ws,"mean")
        subset = NumAbs.abstract_numerical(subset,[col],ws,"std")
    df_temporal_list.append(subset)
df_temporal_list = pd.concat(df_temporal_list)
# --------------------------------------------------------------
# Frequency features
# --------------------------------------------------------------
df_freq = df_temporal.copy().reset_index() #the fn to be used need index resetted.
FreqAbs = FourierTransformation()

fs = int(1000/200)
ws = int(2800/200) # avg length of a set

df_freq = FreqAbs.abstract_frequency(df_freq,["acc_y"],ws,fs)

df_freq_list = []
for s in df_freq["set"].unique():
    subset = df_freq[df_freq["set"] == s].reset_index(drop=True).copy()
    subset = FreqAbs.abstract_frequency(subset,predictor_columns,ws,fs)
    df_freq_list.append(subset)

df_freq = pd.concat(df_freq_list).set_index("epoch (ms)",drop=True)


# --------------------------------------------------------------
# Dealing with overlapping windows
# --------------------------------------------------------------
df_freq = df_freq.dropna()

df_freq = df_freq.iloc[::2]


# --------------------------------------------------------------
# Clustering
# --------------------------------------------------------------
df_cluster = df_freq.copy()
cluster_columns = ["acc_x","acc_y","acc_z"]
k_values = range(2,10)
inertias = []

for k in k_values:
    subset = df_cluster[cluster_columns]
    kmeans = KMeans(n_clusters=k,n_init=20,random_state=0)
    cluster_labels = kmeans.fit_predict(subset)
    inertias.append(kmeans.inertia_)


plt.figure(figsize=(10,10))
plt.plot(k_values,inertias)
plt.xlabel("k")
plt.ylabel("sum of squared dist")
plt.show()

kmeans = KMeans(n_clusters=5,n_init=20,random_state=0)
subset = df_cluster[cluster_columns]
df_cluster["cluster"] = kmeans.fit_predict(subset)
# inertias.append(kmeans.inertia_)

# --------------------------------------------------------------
# Export dataset
# --------------------------------------------------------------
df_cluster.to_pickle("../../data/interim/03_data_features.pkl")