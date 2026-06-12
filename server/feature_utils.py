import numpy as np
import numpy as np
import scipy.stats as stats
import scipy.signal as signal
from scipy.spatial.distance import cdist


# --- DSP / Feature Extraction helper functions ---
def sample_entropy(x: np.ndarray, m: int = 2, r: float = 0.2) -> float:
    N = len(x)
    if N <= m:
        return 0.0

    # Form m-dimensional templates
    Xm = np.array([x[i : i + m] for i in range(N - m + 1)])
    # Form (m+1)-dimensional templates
    Xmp = np.array([x[i : i + m + 1] for i in range(N - m)])

    # Compute Chebyshev distances
    d_m = cdist(Xm, Xm, metric="chebyshev")
    B = np.sum(d_m <= r) - len(Xm)  # subtract diagonal (self-matches)

    d_mp = cdist(Xmp, Xmp, metric="chebyshev")
    A = np.sum(d_mp <= r) - len(Xmp)

    if A == 0 or B == 0:
        return 0.0
    return -np.log(A / B)


def coarse_grain(x: np.ndarray, s: int) -> np.ndarray:
    N = len(x)
    num_points = N // s
    return np.mean(x[: num_points * s].reshape(num_points, s), axis=1)


def multiscale_entropy(
    x: np.ndarray, m: int = 2, r_factor: float = 0.2, scales: range = range(1, 11)
) -> dict:
    std_x = np.std(x)
    r = r_factor * std_x
    entropy_values = {}
    for s in scales:
        cg_x = coarse_grain(x, s)
        entropy_values[s] = sample_entropy(cg_x, m, r)
    return entropy_values


def harmonic_ratio(sig: np.ndarray, fs: float = 100.0) -> float:
    sig = sig - np.mean(sig)
    N = len(sig)
    if N == 0:
        return 0.0
    faxis = np.fft.fftfreq(N, 1 / fs)
    Y = np.fft.fft(sig)
    P2 = np.abs(Y / N)

    # Keep only positive frequencies
    half_n = N // 2
    P1 = P2[:half_n]
    f = faxis[:half_n]

    # Find fundamental frequency
    if len(P1) <= 1:
        return 0.0
    idx_max = np.argmax(P1[1:]) + 1  # ignore DC
    f0 = f[idx_max]

    if f0 == 0:
        return 0.0

    # Number of harmonics
    num_harmonics = int(np.floor((fs / 2) / f0))

    odd_sum = 0.0
    even_sum = 0.0
    for k in range(1, num_harmonics + 1):
        idx_h = int(np.round(f0 * k / (fs / N)))
        if idx_h < len(P1):
            if k % 2 == 1:
                odd_sum += P1[idx_h]
            else:
                even_sum += P1[idx_h]

    if odd_sum == 0:
        return 0.0
    return even_sum / odd_sum


def compute_fft_features(x: np.ndarray, prefix: str, fs: float = 100.0) -> dict:
    N = len(x)
    x_detrend = x - np.mean(x)
    fft_val = np.abs(np.fft.fft(x_detrend))

    half_n = N // 2 + 1
    fft_side = fft_val[:half_n]

    sum_fft = np.sum(fft_side)
    if sum_fft > 0:
        fft_norm = fft_side / sum_fft
    else:
        fft_norm = np.zeros_like(fft_side)

    faxis = np.fft.fftfreq(N, 1 / fs)[:half_n]

    if len(fft_norm) > 1:
        idx1 = np.argmax(fft_norm[1:]) + 1
        fft_temp = fft_norm.copy()
        fft_temp[idx1] = 0.0
        idx2 = np.argmax(fft_temp[1:]) + 1
        dom_freqs = faxis[[idx1, idx2]]
    else:
        dom_freqs = [0.0, 0.0]

    mean_freq = np.sum(faxis * fft_norm)
    cumsum_fft = np.cumsum(fft_norm)
    idx_med = np.searchsorted(cumsum_fft, 0.5)
    median_freq = faxis[idx_med] if idx_med < len(faxis) else 0.0
    spec_entropy = -np.sum(fft_norm * np.log(fft_norm + 1e-12))
    dom_power = np.max(fft_norm)

    return {
        f"SpecEntropy{prefix}": spec_entropy,
        f"DomPower{prefix}": dom_power,
        f"MeanFreq{prefix}": mean_freq,
        f"MedianFreq{prefix}": median_freq,
        f"F0F1Dist{prefix}": abs(dom_freqs[0] - dom_freqs[1]),
    }


def compute_cwt_band_features(
    acc: np.ndarray, gyr: np.ndarray, fs: float = 100.0
) -> dict:
    N = len(acc)
    acc_fft = np.fft.fft(acc - np.mean(acc))
    gyr_fft = np.fft.fft(gyr - np.mean(gyr))
    omega = 2 * np.pi * np.fft.fftfreq(N, 1 / fs)

    frequencies = np.linspace(0.5, 25, 40)
    freq_bands = [
        (0.5, 1.0),
        (1.0, 2.0),
        (2.0, 3.0),
        (3.0, 5.0),
        (5.0, 8.0),
        (8.0, 12.0),
        (12.0, 18.0),
        (18.0, 25.0),
    ]

    band_cfs_acc = {i: [] for i in range(len(freq_bands))}
    band_cfs_gyr = {i: [] for i in range(len(freq_bands))}

    for f in frequencies:
        a = 6 / (2 * np.pi * f)
        filt = (
            (omega > 0)
            * (2 * np.sqrt(np.pi)) ** 0.5
            * np.exp(-0.5 * (a * omega - 6) ** 2)
        )

        # ACC CWT
        C_acc = np.fft.ifft(acc_fft * filt)
        power_acc = np.abs(C_acc) ** 2

        # GYR CWT
        C_gyr = np.fft.ifft(gyr_fft * filt)
        power_gyr = np.abs(C_gyr) ** 2

        for b_idx, (low, high) in enumerate(freq_bands):
            if low <= f < high:
                band_cfs_acc[b_idx].append(power_acc)
                band_cfs_gyr[b_idx].append(power_gyr)
                break

    features = {}
    spec_ent_fn = lambda P: -np.sum(P * np.log(P + 1e-12))

    for b_idx in range(len(freq_bands)):
        band_num = b_idx + 1

        # ACC
        powers_acc = band_cfs_acc[b_idx]
        if len(powers_acc) > 0:
            bp_acc = np.concatenate(powers_acc)
            features[f"CWT_Eng_Acc_B{band_num}"] = np.sum(bp_acc)
            features[f"CWT_Mean_Acc_B{band_num}"] = np.mean(bp_acc)
            features[f"CWT_Std_Acc_B{band_num}"] = np.std(bp_acc)
            p_norm_acc = bp_acc / (np.sum(bp_acc) + 1e-12)
            features[f"CWT_Entropy_Acc_B{band_num}"] = spec_ent_fn(p_norm_acc)
        else:
            features[f"CWT_Eng_Acc_B{band_num}"] = 0.0
            features[f"CWT_Mean_Acc_B{band_num}"] = 0.0
            features[f"CWT_Std_Acc_B{band_num}"] = 0.0
            features[f"CWT_Entropy_Acc_B{band_num}"] = 0.0

        # GYR
        powers_gyr = band_cfs_gyr[b_idx]
        if len(powers_gyr) > 0:
            bp_gyr = np.concatenate(powers_gyr)
            features[f"CWT_Eng_Gyr_B{band_num}"] = np.sum(bp_gyr)
            features[f"CWT_Mean_Gyr_B{band_num}"] = np.mean(bp_gyr)
            features[f"CWT_Std_Gyr_B{band_num}"] = np.std(bp_gyr)
            p_norm_gyr = bp_gyr / (np.sum(bp_gyr) + 1e-12)
            features[f"CWT_Entropy_Gyr_B{band_num}"] = spec_ent_fn(p_norm_gyr)
        else:
            features[f"CWT_Eng_Gyr_B{band_num}"] = 0.0
            features[f"CWT_Mean_Gyr_B{band_num}"] = 0.0
            features[f"CWT_Std_Gyr_B{band_num}"] = 0.0
            features[f"CWT_Entropy_Gyr_B{band_num}"] = 0.0

    return features


def extract_all_features(acc: np.ndarray, gyr: np.ndarray) -> dict:
    fs = 100
    features = {}

    # 1. Statistics
    for signal_arr, prefix in [(acc, "Acc"), (gyr, "Gyr")]:
        features[f"Mean{prefix}"] = np.mean(signal_arr)
        features[f"Var{prefix}"] = np.var(signal_arr, ddof=1)
        features[f"Skew{prefix}"] = stats.skew(signal_arr, bias=True)
        features[f"Kurt{prefix}"] = stats.kurtosis(signal_arr, bias=True, fisher=False)
        features[f"IQR{prefix}"] = stats.iqr(signal_arr)
        features[f"RMS{prefix}"] = np.sqrt(np.mean(signal_arr**2))
        features[f"SMA{prefix}"] = np.mean(np.abs(signal_arr))
        features[f"Max{prefix}"] = np.max(signal_arr)
        features[f"Range{prefix}"] = np.ptp(signal_arr)

    # 2. Jerk RMS
    features["JerkRMS"] = np.sqrt(np.mean(np.diff(acc) ** 2))

    # 3. Median Cross Rate
    features["MedCrossRateAcc"] = np.sum(np.diff(acc > np.median(acc)) != 0) / len(acc)
    features["MedCrossRateGyr"] = np.sum(np.diff(gyr > np.median(gyr)) != 0) / len(gyr)

    # 4. Teager Energy Operator
    for signal_arr, prefix in [(acc, "Acc"), (gyr, "Gyr")]:
        teo_val = signal_arr[1:-1] ** 2 - signal_arr[:-2] * signal_arr[2:]
        features[f"TEO_Mean_{prefix}"] = np.mean(teo_val)
        features[f"TEO_Var_{prefix}"] = np.var(teo_val, ddof=1)
        peaks, _ = signal.find_peaks(teo_val, prominence=2.5)
        features[f"TEO_Peaks_{prefix}"] = len(peaks)

    # 5. Multiscale Entropy (scales 1 to 10)
    entropy_acc = multiscale_entropy(acc, m=2, r_factor=0.2, scales=range(1, 11))
    for s, val in entropy_acc.items():
        features[f"En{s}_Acc"] = val
    features["EnSum_Acc"] = sum(entropy_acc.values())

    entropy_gyr = multiscale_entropy(gyr, m=2, r_factor=0.2, scales=range(1, 11))
    for s, val in entropy_gyr.items():
        features[f"En{s}_Gyr"] = val
    features["EnSum_Gyr"] = sum(entropy_gyr.values())

    # 6. Autocorrelation (ACF lags 1-10)
    for signal_arr, prefix in [(acc, "Acc"), (gyr, "Gyr")]:
        for k in range(1, 11):
            features[f"ACF{k}_{prefix}"] = np.sum(signal_arr[:-k] * signal_arr[k:])

    # 7. NumPeaks
    for signal_arr, prefix in [(acc, "Acc"), (gyr, "Gyr")]:
        peaks, _ = signal.find_peaks(signal_arr, prominence=2.5)
        features[f"NumPeaks{prefix}"] = len(peaks)

    # 8. FFT Frequency Domain features
    features.update(compute_fft_features(acc, "Acc", fs))
    features.update(compute_fft_features(gyr, "Gyr", fs))

    # 9. Harmonic Ratio
    features["HarmonicRatioAcc"] = harmonic_ratio(acc, fs)
    features["HarmonicRatioGyr"] = harmonic_ratio(gyr, fs)

    # 10. Acc-Gyr cross features
    features["GyroAccCorr"] = np.corrcoef(acc, gyr)[0, 1]
    features["GyroAccMax"] = np.max(acc) * np.max(gyr)
    features["GyroAccStdProd"] = np.std(acc) * np.std(gyr)

    # 11. CWT Band Features
    features.update(compute_cwt_band_features(acc, gyr, fs))

    return features
