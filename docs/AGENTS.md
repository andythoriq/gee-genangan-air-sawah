# RESEARCH PROJECT CONTEXT

## 1. Project Identity

- **Research Direction:** Applied Research (Case Study)

- **Title:** Analysis of Changes in the Distribution of Water Inundation That May Disrupt Rice Fields Using Classical Digital Image Processing Based on Sentinel-2 in Citrajaya Village, Subang Regency
- **Title (id):** Analisis Perubahan Sebaran Genangan Air Menggunakan Pengolahan Citra Digital Berbasis Sentinel-2 di Pesawahan Desa Citrajaya, Kabupaten Subang

- **Study Location:** Desa Citrajaya, Kabupaten Subang, Java Barat.

- **Area of Interest (AOI) Specifications [subject to change if adjustments are required]:**

  - **Bounding Box (Overall Area):** [107.8050, -6.4000, 107.8350, -6.3850]

  - **Target Validation Points:**

    1. Sawah Kontrak 1 (Potentially Inundated): [107.83064, -6.39555]
    2. Sawah Impres (Safe): [107.80748, -6.39770]
    3. Sawah PU & Keprak (Potentially Inundated): [107.81818, -6.38834]
    4. Sawah Kontrak 2 (Potentially Inundated): [107.82643, -6.39678]

## 2. Background & Actual Technical Constraints

- **Agronomic Context:** Young rice plants have a maximum water-submergence tolerance of 3–4 days. Exceeding this duration can lead to crop failure.

- **Environmental Characteristics & Turbid Water Problem:** Floodwater inundation and river overflows around the AOI (Kali Cigadung & Kali Anyar) consist of **turbid water with a high mud-sediment content**. Standard NDWI (Green/NIR) fails to detect this because of the high reflectance of the sediment.

- **Morphological Operation Problem (Pixel Erosion):** To remove *noise* (wet mud/field bunds), a spatial erosion filter (`focal_min`) is used. Unfortunately, this operation also **removes narrow, linear water features**, causing river channels to disappear from the resulting map.

- **Proposed Solution:** Develop an automated mapping system using a SWIR-based water index, combined with a *linear feature preservation* technique to retain river shapes while removing land-related *noise*.

## 3. Methodology (Classical Digital Image Processing)

Exclusively uses pixel-based algorithms and spatial operations (No *Machine Learning*).

- **Primary Data:** Sentinel-2 Level-2A satellite imagery (10 m resolution).

- **Example of the Image Processing Workflow:**

  1. **Cloud Masking:** Filter clouds using the QA60 band, with relaxed tolerance during the peak of the rainy season.

  2. **Water Extraction (MNDWI):** Use a combination of the *Green* (B3) and *Short-Wave Infrared* (B11) bands to ensure that sediment-laden/turbid water is still captured and detected as a water body.

  3. **Thresholding:** Apply a threshold (example: > 0.05) to extract a binary map.

  4. **Noise Removal & River Preservation:** Modify morphological operations to prevent the loss of linear feature connectivity (rivers). *(Note: The specific method is currently being reviewed based on the literature.)*

  5. **Multitemporal Analysis:** Compare inundation during rainfall (T1) and after rainfall (T2) to identify persistent inundation.

## 4. Data Status & Verification (Current State)

The project is currently at the empirical confirmation stage. Some raw data have been collected but **have not yet been fully tested**, including:

- **Local Residents' Statements (Historical Flood Events):** Flood events have reportedly occurred on **February 17, 2025, January 24, 2026, and January 29, 2026**. These dates will be used as the primary parameters for the `t1_start` through `t2_end` variables in the GEE script validation process.

- **Literature & References (*paper-references/*):** Several papers related to turbid water handling and spatial filters have been collected. The technical implementation of these references in Python/GEE code is still at the experimental stage (for example: transitioning from standard NDWI + Morphology to shape-preservation algorithms or other noise-handling methods).

## 5. Expected Outputs

1. Multitemporal maps that accurately display persistent inundation in the target rice field plots.

2. The Kali Cigadung and Kali Anyar river networks remain visible on the map as geographical references.

3. Validated synchronization between satellite maps and the flood-event dates reported by local residents.

## 6. Research Limitations

The system is vulnerable to complete cloud cover throughout the T1 or T2 duration, which is common during the peak monsoon period. Distinguishing flooded areas from rice fields that are intentionally irrigated depends heavily on the accuracy of temporal comparisons.

# AI AGENT CONTEXT & GUIDELINES

## 1. Technical Environment & Setup
- **Platform:** Google Earth Engine (GEE).
- **Local Environment:** Conda environment named `ee`. Agents must assume that all Python scripts or GEE CLI commands will be executed within this environment.
- **Key Libraries:** `earthengine-api`, `geemap` (if applicable for Python), and standard spatial data manipulation libraries.
- **Project Structure:**
  - `AGENTS.md`: This file (Agent instructions).
  - `README.md`: General project documentation.
  - `paper-references/`: Directory containing literature regarding turbid water detection and morphological linear feature preservation.

## 2. Core Methodologies [May Change]
Agents generating code or analytical pipelines must adhere to the following classical digital image processing workflow. **Do NOT use Machine Learning/Deep Learning models.**

1.  **Cloud Masking:** Always implement cloud and cirrus masking using the `QA60` band. Assume high cloud cover since the target events occur during the tropical wet season (e.g., January/February).
2.  **Water Extraction (MNDWI):** Use the Modified Normalized Difference Water Index (MNDWI) utilizing Green and SWIR bands. 
    *   *Why:* The floodwater and nearby rivers carry heavy sediments (turbid water). Standard NDWI (Green/NIR) fails here.
3.  **Thresholding:** Apply strict empirical thresholds (e.g., > 0.05) or automatic thresholding (like Otsu) to separate water from land/wet mud.
4.  **Morphological Filtering & Linear Feature Preservation:** 
    *   Apply morphological operations (Opening/Closing, `focal_min`, `focal_max`) to remove noise (e.g., wet mud, small puddles).
    *   *CRITICAL RULE:* Agents must implement strategies (e.g., directional filters, adjusted structuring elements) to ensure that narrow linear water bodies (rivers) are NOT erased during the erosion/focal_min process.
5.  **Multitemporal Analysis:** Compare water masks between Time 1 (T1: Peak rain/inundation) and Time 2 (T2: 3-14 days post-rain). Persistent water (Water at T1 AND Water at T2) indicates agricultural hazard.

## 3. Operational Rules for AI Agents
- **Code Generation:** When generating Python/GEE API code, ensure it is optimized for Earth Engine server-side execution. Avoid unnecessary client-side loops (`getInfo()`) unless absolutely required for exporting metrics.
- **Contextual Awareness:** Always refer to the `paper-references/` directory when proposing improvements to the thresholding or morphological steps.
- **Language:** Maintain code syntax and inline comments in English, but preserve Indonesian terms for local geographic markers (e.g., "Sawah", "Kali", "Desa Citrajaya").
- **Error Handling:** If GEE returns "Image with no bands" or similar errors, the agent must automatically suggest expanding the temporal window or relaxing the `CLOUDY_PIXEL_PERCENTAGE` filter, as this is a known issue during the Indonesian monsoon season.

## 5. Environments Specs

### 1. Google Earth Engine Project ID
```
tubes-pcd-praktik-004-019
```

### 2. Repository Structure
```
deteksi-genangan-sawah/
│
├── data/
│
├── notebooks/
│
├── src/
│
├── outputs/
│
├── docs/
│   ├── AGENTS.md
│   └── paper-references/
│  
└── README.md
```

### 3. Installed Packages

Top-level dependencies are declared in `environment.yml` at the repository root. The exact
environment that produced the current results is pinned in `environment.lock.yml` (a full
`conda list --export`), kept separate because it is machine-generated, contains every
transitive dependency, and changes on every install.

```bash
conda env create -f environment.yml
conda activate ee
earthengine authenticate
```

Verified versions at the time of writing: Python 3.12.16, earthengine-api 1.7.51,
streamlit 1.66.1, streamlit-folium 0.27.4, folium 0.20.0, pandas 3.1.0, geemap 0.38.9.

Only these are imported directly by `src/`: `ee` (earthengine-api), `geemap`, `streamlit`,
`streamlit_folium`, `folium`, `pandas`, `requests`. Everything else in the lock file is a
transitive dependency.
