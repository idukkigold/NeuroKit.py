# -*- coding: utf-8 -*-
"""
Subsubmodule for ecg processing.
"""
import numpy as np
import pandas as pd
import biosppy
import datetime
import hrv
import sklearn
import scipy

from .bio_rsp import *
from ..signal import complexity
from ..materials import Path
from ..statistics import z_score
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
def ecg_process(ecg, rsp=None, sampling_rate=1000, resampling_method="bfill", quality_model="default"):
    """
    Automated processing of ECG and RSP signals.

    Parameters
    ----------
    ecg : list or array
        ECG signal array.
    rsp : list or array
        Respiratory (RSP) signal array.
    sampling_rate : int
        Sampling rate (samples/second).
    resampling_method : str
        "mean", "pad" or "bfill", the resampling method used for ECG and RSP heart rate.
    quality_model : str
        Path to model used to check signal quality. "default" uses the builtin model.

    Returns
    ----------
    processed_ecg : dict
        Dict containing processed ECG features.

        Contains the ECG raw signal, the filtered signal, the R peaks indexes, HRV characteristics, all the heartbeats, the Heart Rate, the RSP filtered signal (if respiration provided) and the respiratory sinus arrhythmia (RSA) features.

        This function is mainly a wrapper for the biosppy.ecg.ecg() and the hrv.hrv() functions. Credits go to their authors.

    Example
    ----------
    >>> import neurokit as nk
    >>>
    >>> processed_ecg = nk.ecg_process(ecg_signal, resp_signal)

    Notes
    ----------
    *Details*

    - **RSA**: Respiratory sinus arrhythmia (RSA) is a naturally occurring variation in heart rate that occurs during the breathing cycle, serving as a measure of parasympathetic nervous system activity.
    - **HRV**: Heart-Rate Variability is a finely tuned measure of heart-brain communication, as well as a strong predictor of morbidity and death (Zohar et al., 2013).

       - **SDNN** is the standard deviation of the time interval between successive normal heart beats (*i.e.*, the RR intervals). Reflects all influences on HRV including slow influences across the day, circadian variations, the effect of hormonal influences such as cortisol and epinephrine.
       - **RMSSD** is the root mean square of the RR intervals (*i.e.*, square root of the mean of the squared differences in time between successive normal heart beats). Reflects high frequency (fast or parasympathetic) influences on HRV (*i.e.*, those influencing larger changes from one beat to the next).
       - **NN50**: This description is waiting your contribution!
       - **PNN50**: This description is waiting your contribution!
       - **mRR** is the mean RR interval.
       - **mHR** is the mean RR interval expressed in seconds.
       - **VLF** is the variance (*i.e.*, power) in HRV in the Very Low Frequency (.003 to .04 Hz). Reflect an intrinsic rhythm produced by the heart which is modulated by primarily by sympathetic activity.
       - **LF**  is the variance (*i.e.*, power) in HRV in the Low Frequency (.04 to .15 Hz). Reflects a mixture of sympathetic and parasympathetic activity, but in long-term recordings like ours, it reflects sympathetic activity and can be reduced by the beta-adrenergic antagonist propanolol (McCraty & Atkinson, 1996).
       - **HF**  is the variance (*i.e.*, power) in HRV in the High Frequency (.15 to .40 Hz). Reflects fast changes in beat-to-beat variability due to parasympathetic (vagal) activity. Sometimes called the respiratory band because it corresponds to HRV changes related to the respiratory cycle and can be increased by slow, deep breathing (about 6 or 7 breaths per minute) (Kawachi et al., 1995) and decreased by anticholinergic drugs or vagal blockade (Hainsworth, 1995).
       - **Total_Power**: no description :'(.
       - **LF_HF**: This description is waiting your contribution!
       - **LFNU**: This description is waiting your contribution!
       - **HFNU**: This description is waiting your contribution!

    - **Complexity**: Non-linear chaos/complexity measures of RR intervals. See :function:`neurokit.complexity`.


    *Authors*

    - Dominique Makowski (https://github.com/DominiqueMakowski)
    - Rhenan Bartels (https://github.com/rhenanbartels)

    *Dependencies*

    - biosppy
    - numpy
    - pandas

    *See Also*

    - BioSPPY: https://github.com/PIA-Group/BioSPPy
    - hrv: https://github.com/rhenanbartels/hrv

    References
    ------------
    - Zohar, A. H., Cloninger, C. R., & McCraty, R. (2013). Personality and heart rate variability: exploring pathways from personality to cardiac coherence and health. Open Journal of Social Sciences, 1(06), 32.
    """
    ecg_df = pd.DataFrame({"ECG_Raw": np.array(ecg)})

    # Compute several features using biosppy
    biosppy_ecg = dict(biosppy.signals.ecg.ecg(ecg, sampling_rate=sampling_rate, show=False))

    # Filtered signal
    ecg_df["ECG_Filtered"] = biosppy_ecg["filtered"]

    # Store R peaks indexes
    r_peaks = np.array([np.nan]*len(ecg))
    r_peaks[biosppy_ecg['rpeaks']] = 1
    ecg_df["ECG_Rpeaks"] = r_peaks


    # Heart rate index creation
    time_now = datetime.datetime.now()
    # Convert seconds to datetime deltas
    time_index = [datetime.timedelta(seconds=x) for x in biosppy_ecg["heart_rate_ts"]]
    time_index = np.array(time_index) + time_now
    heart_rate = pd.Series(biosppy_ecg["heart_rate"], index=time_index)

    # Create resampling factor
    resampling_rate = str(int(1000/sampling_rate)) + "L"

    # Resample
    if resampling_method == "mean":
        heart_rate = heart_rate.resample(resampling_rate).mean()
    if resampling_method == "pad":
        heart_rate = heart_rate.resample(resampling_rate).pad()
    if resampling_method == "bfill":
        heart_rate = heart_rate.resample(resampling_rate).bfill()

    # Store Heart Rate
    if len(heart_rate) >= len(ecg):
        ecg_df["Heart_Rate"] = np.array(heart_rate[0:len(ecg)])
    else:
        ecg_df["Heart_Rate"] = np.array([heart_rate[-1]]*(len(ecg)-len(heart_rate)) + list(heart_rate))
#        ecg_features["Heart_Rate"] = scipy.signal.resample(heart_rate, len(ecg))  # Looks more badly when resampling with scipy

    # RR intervals (RRis)
    rri = np.diff(biosppy_ecg["rpeaks"])

    # Heartbeats
    heartbeats = pd.DataFrame(biosppy_ecg["templates"]).T
    heartbeats.index = pd.date_range(pd.datetime.today(), periods=len(heartbeats), freq=resampling_rate)

    # Signal quality
    quality = ecg_signal_quality(heartbeats, sampling_rate, quality_model=quality_model)

    # HRV
    hrv = ecg_hrv(rri, sampling_rate)

    # Store results
    processed_ecg = {"df": ecg_df,
                     "ECG": {
                            "RR_Intervals": rri,
                            "Cardiac_Cycles": heartbeats,
                            "R_Peaks": biosppy_ecg["rpeaks"],
                            "HRV": hrv}
                     }

    processed_ecg["ECG"].update(quality)

    # RSP
    if rsp is not None:
        rsp = rsp_process(rsp=rsp, sampling_rate=sampling_rate, resampling_method=resampling_method)
        processed_ecg["RSP"] = rsp["RSP"]
        processed_ecg["df"] = pd.concat([processed_ecg["df"], rsp["df"]], axis=1)

        # RSA
        rpeaks = biosppy_ecg["rpeaks"]
        rsp_cycles = rsp["RSP"]["Cycles_Onsets"]
        rsp_signal = rsp["df"]["RSP_Filtered"]
        rsa = respiratory_sinus_arrhythmia(rpeaks, rsp_cycles, rsp_signal)

        processed_ecg["df"]["RSA"] = rsa["RSA"]

        processed_ecg["ECG"]["RSA"] = {}
        processed_ecg["ECG"]["RSA"]["RSA_Mean"] = rsa["RSA_Mean"]
        processed_ecg["ECG"]["RSA"]["RSA_Variability"] = rsa["RSA_Variability"]
        processed_ecg["ECG"]["RSA"]["RSA_Values"] = rsa["RSA_Values"]


    # Complexity
    processed_ecg["ECG"]["Complexity"] = {}
    chaos = complexity(rri, lyap_r=False, lyap_e=False, emb_dim=2, k_max=8)
    chaos = pd.Series(chaos)
    chaos.index = ["ECG_Complexity_" + s for s in chaos.index]
    processed_ecg["ECG"]["Complexity"] = chaos.to_dict()

    return(processed_ecg)


# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
def ecg_find_peaks(signal, sampling_rate=1000):
    """
    Find R peaks indices on the ECG channel.

    Parameters
    ----------
    signal : list or array
        ECG signal (preferably filtered).
    sampling_rate : int
        Sampling rate (samples/second).


    Returns
    ----------
    rpeaks : list
        List of R-peaks location indices.

    Example
    ----------
    >>> import neurokit as nk
    >>> Rpeaks = nk.ecg_find_peaks(signal)

    Notes
    ----------
    *Authors*

    - the bioSSPy dev team (https://github.com/PIA-Group/BioSPPy)

    *Dependencies*

    - biosppy

    *See Also*

    - BioSPPY: https://github.com/PIA-Group/BioSPPy

    """
    rpeaks, = biosppy.ecg.hamilton_segmenter(signal, sampling_rate=sampling_rate)
    rpeaks, = biosppy.ecg.correct_rpeaks(signal=signal, rpeaks=rpeaks, sampling_rate=sampling_rate, tol=0.05)
    return(rpeaks)



# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
def respiratory_sinus_arrhythmia(rpeaks, rsp_cycles, rsp_signal, sampling_rate=1000):
    """
    Returns Respiratory Sinus Arrhythmia (RSA) features.

    Parameters
    ----------
    rpeaks : list or array
        List of R peaks indices.
    rsp_cycles : list or array
        List of respiratory cycles onsets.
    rsp_signal : list or array
        RSP signal.
    sampling_rate : int
        Sampling rate (samples/second).


    Returns
    ----------
    rsa : dict
        Contains RSA features.

    Example
    ----------
    >>> import neurokit as nk
    >>> rsa = nk.respiratory_sinus_arrhythmia(rpeaks, rsp_cycles, rsp_signal)

    Notes
    ----------
    *Details*

    - **RSA**: Respiratory sinus arrhythmia (RSA) is a naturally occurring variation in heart rate that occurs during the breathing cycle, serving as a measure of parasympathetic nervous system activity.

    *Authors*

    - Dominique Makowski (https://github.com/DominiqueMakowski)
    - Rhenan Bartels (https://github.com/rhenanbartels)

    *Dependencies*

    - biosppy
    - numpy
    - pandas

    *See Also*

    - BioSPPY: https://github.com/PIA-Group/BioSPPy

    """
    # Find all RSP cycles and the Rpeaks within
    cycles_rri = []
    for idx in range(len(rsp_cycles) - 1):
        cycle_init = rsp_cycles[idx]
        cycle_end = rsp_cycles[idx + 1]
        cycles_rri.append(rpeaks[np.logical_and(rpeaks >= cycle_init,
                                                rpeaks < cycle_end)])

    # Iterate over all cycles
    RSA = []
    for cycle in cycles_rri:
        RRis = np.diff(cycle)/sampling_rate
        if len(RRis) > 1:
            RSA.append(np.max(RRis) - np.min(RRis))
        else:
            RSA.append(np.nan)


    # Continuous RSA
    current_rsa = np.nan

    continuous_rsa = []
    phase_counter = 0
    for i in range(len(rsp_signal)):
        if i == rsp_cycles[phase_counter]:
            current_rsa = RSA[phase_counter]
            if phase_counter < len(rsp_cycles)-2:
                phase_counter += 1
        continuous_rsa.append(current_rsa)

    # Find last phase
    continuous_rsa = np.array(continuous_rsa)
    continuous_rsa[max(rsp_cycles):] = np.nan

    RSA = {"RSA": continuous_rsa,
           "RSA_Values": RSA,
           "RSA_Mean": pd.Series(RSA).mean(),
           "RSA_Variability": pd.Series(RSA).std()}

    return(RSA)


# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
def ecg_signal_quality(cardiac_cycles, sampling_rate, quality_model="default"):
    """
    Attempt to find the recording lead and the overall and individual quality of hearbeats signal.

    Parameters
    ----------
    cardiac_cycles : pd.DataFrame
        DataFrame containing heartbeats. Computed by :function:neurokit.ecg_process().
    quality_model : str
        Path to model used to check signal quality. "default" uses the builtin model.

    Returns
    ----------
    classification : dict
        Contains classification features.

    Example
    ----------
    >>> import neurokit as nk
    >>> rsa = nk.respiratory_sinus_arrhythmia(rpeaks, rsp_cycles, rsp_signal)

    Notes
    ----------
    *Details*

    Using the PTB-Diagnostic dataset available from PhysioNet, we extracted all the ECGs signal from the healthy participants. For each ECG, the 15 leads were available. We extracted all cardiac cycles, for each lead, and downsampled them from 600 to 200 datapoints. Note that we dropped the 8 first values that were NaNs. Then, we fitted a neural network on 2/3 of the dataset (that contains 134392 cardiac cycles) to predict the lead. Model evaluation was done on the remaining 1/3. The model show good performances in predicting the correct recording lead (accuracy=0.91, precision=0.91). In this function, this model is fitted on each cardiac cycle. It returns the probable recording lead (the most common predicted lead), the signal quality of each cardiac cycle (the probability of belonging to the probable recording lead) and the overall signal quality (the mean of signal quality).

    *Authors*

    - Dominique Makowski (https://github.com/DominiqueMakowski)

    *Dependencies*

    - numpy
    - pandas
    """
    if len(cardiac_cycles) > 200:
        cardiac_cycles = cardiac_cycles.rolling(20).mean().resample("3L").pad()
    if len(cardiac_cycles) < 200:
        cardiac_cycles = cardiac_cycles.resample("1L").pad()
        cardiac_cycles = cardiac_cycles.rolling(20).mean().resample("3L").pad()

    if len(cardiac_cycles) < 200:
        fill_dict = {}
        for i in cardiac_cycles.columns:
            fill_dict[i] = [np.nan] * (200-len(cardiac_cycles))
        cardiac_cycles = pd.concat([pd.DataFrame(fill_dict), cardiac_cycles], ignore_index=True)

    cardiac_cycles = cardiac_cycles.fillna(method="bfill")
    cardiac_cycles = cardiac_cycles.reset_index(drop=True)[8:200]
    cardiac_cycles = z_score(cardiac_cycles).T
    cardiac_cycles = np.array(cardiac_cycles)

    if quality_model == "default":
        model = sklearn.externals.joblib.load(Path.materials() + 'heartbeat_classification.model')
    else:
        model = sklearn.externals.joblib.load(quality_model)

    quality = {}

    # Find dominant class
    lead = model.predict(cardiac_cycles)
    lead = pd.Series(lead).value_counts().index[0]
    quality["Probable_Lead"] = lead

    predict = pd.DataFrame(model.predict_proba(cardiac_cycles))
    predict.columns = model.classes_
    quality["Cardiac_Cycles_Signal_Quality"] = predict[lead].as_matrix()
    quality["Average_Signal_Quality"] = predict[lead].mean()

    return(quality)


# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
def ecg_hrv(rri, sampling_rate, segment_length=256, window="hanning"):
    """
    Computes the Heart-Rate Variability (HRV). Shamelessly stolen from the great `hrv <https://github.com/rhenanbartels/hrv/blob/develop/hrv>`_ package by Rhenan Bartels. All credits go to him.

    Parameters
    ----------
    rri : ndarray
        RR intervals.
    sampling_rate : int
        Sampling rate (samples/second).

    Returns
    ----------
    hrv : dict
        Contains hrv features.

    Example
    ----------
    >>> import neurokit as nk
    >>> hrv = nk.hrv(rri, 1000)

    Notes
    ----------
    *Details*

    - **HRV**: Heart-Rate Variability is a finely tuned measure of heart-brain communication, as well as a strong predictor of morbidity and death (Zohar et al., 2013).

       - **SDNN** is the standard deviation of the time interval between successive normal heart beats (*i.e.*, the RR intervals). Reflects all influences on HRV including slow influences across the day, circadian variations, the effect of hormonal influences such as cortisol and epinephrine.
       - **RMSSD** is the root mean square of the RR intervals (*i.e.*, square root of the mean of the squared differences in time between successive normal heart beats). Reflects high frequency (fast or parasympathetic) influences on HRV (*i.e.*, those influencing larger changes from one beat to the next).
       - **NN50**: This description is waiting your contribution!
       - **PNN50**: This description is waiting your contribution!
       - **mRR** is the mean RR interval.
       - **mHR** is the mean RR interval expressed in seconds.
       - **VLF** is the variance (*i.e.*, power) in HRV in the Very Low Frequency (.003 to .04 Hz). Reflect an intrinsic rhythm produced by the heart which is modulated by primarily by sympathetic activity.
       - **LF**  is the variance (*i.e.*, power) in HRV in the Low Frequency (.04 to .15 Hz). Reflects a mixture of sympathetic and parasympathetic activity, but in long-term recordings like ours, it reflects sympathetic activity and can be reduced by the beta-adrenergic antagonist propanolol (McCraty & Atkinson, 1996).
       - **HF**  is the variance (*i.e.*, power) in HRV in the High Frequency (.15 to .40 Hz). Reflects fast changes in beat-to-beat variability due to parasympathetic (vagal) activity. Sometimes called the respiratory band because it corresponds to HRV changes related to the respiratory cycle and can be increased by slow, deep breathing (about 6 or 7 breaths per minute) (Kawachi et al., 1995) and decreased by anticholinergic drugs or vagal blockade (Hainsworth, 1995).
       - **Total_Power**: no description :'(.
       - **LF_HF**: This description is waiting your contribution!
       - **LFNU**: This description is waiting your contribution!
       - **HFNU**: This description is waiting your contribution!

    *Authors*

    - Rhenan Bartels (https://github.com/rhenanbartels)
    - Dominique Makowski (https://github.com/DominiqueMakowski)

    *Dependencies*

    - scipy
    - numpy
    """
    # Resample RRis as if the sampling rate was 1000Hz
    rri = rri*1000/sampling_rate

    # Initialize empty dict
    hrv = {}

    # Time Domain
    # ==================
    hrv["RMSSD"] = np.sqrt(np.mean(np.diff(rri) ** 2))
    hrv["SDNN"] = np.std(rri, ddof=1)  # make it calculate N-1
    hrv["NN50"] = sum(abs(np.diff(rri)) > 50)
    hrv["PNN50"] = hrv["NN50"] / len(rri) * 100
    hrv["mRR"] = np.mean(rri)
    hrv["mHR"] = np.mean(60 / (rri / 1000))

    # Frequency Domain
    # =================
    # Parameters
    vlf_band=(0.003, 0.04)
    lf_band=(0.04, 0.15)
    hf_band=(0.15, 0.40)
    segment_length=segment_length  # This value needs to be confirmed... 256 is the scipy default.

    freq, power = scipy.signal.welch(x=rri, fs=1, window=window, nperseg=segment_length)

    vlf_indexes = np.logical_and(freq >= vlf_band[0], freq < vlf_band[1])
    lf_indexes = np.logical_and(freq >= lf_band[0], freq < lf_band[1])
    hf_indexes = np.logical_and(freq >= hf_band[0], freq < hf_band[1])

    hrv["VLF"] = np.trapz(y=power[vlf_indexes], x=freq[vlf_indexes])
    hrv["LF"] = np.trapz(y=power[lf_indexes], x=freq[lf_indexes])
    hrv["HF"] = np.trapz(y=power[hf_indexes], x=freq[hf_indexes])

    hrv["Total_Power"] = hrv["VLF"] + hrv["LF"] + hrv["HF"]
    hrv["LF_HF"] = hrv["LF"] / hrv["HF"]
    hrv["LFNU"] = (hrv["LF"] / (hrv["Total_Power"] - hrv["VLF"])) * 100
    hrv["HFNU"] = (hrv["HF"] / (hrv["Total_Power"] - hrv["VLF"])) * 100

    return(hrv)

