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
```
# packages in environment at /opt/miniconda3/envs/ee:
#
# Name                                  Version          
_openmp_mutex                           4.5              
_python_abi3_support                    1.0              
affine                                  3.0.1            
aiohappyeyeballs                        2.7.1            
aiohttp                                 3.14.5           
aiosignal                               1.4.0            
anyio                                   4.16.0           
anywidget                               0.11.0           
aom                                     3.9.1            
appnope                                 1.0.0            
argon2-cffi                             25.1.0           
argon2-cffi-bindings                    26.1.0           
arrow                                   1.4.0            
asttokens                               3.0.2            
async-lru                               2.4.0            
attrs                                   26.1.0           
aws-c-auth                              0.9.3            
aws-c-cal                               0.9.13           
aws-c-common                            0.12.6           
aws-c-compression                       0.3.1            
aws-c-event-stream                      0.5.7            
aws-c-http                              0.10.7           
aws-c-io                                0.23.3           
aws-c-mqtt                              0.13.3           
aws-c-s3                                0.11.3           
aws-c-sdkutils                          0.2.4            
aws-checksums                           0.2.7            
aws-crt-cpp                             0.35.4           
aws-sdk-cpp                             1.11.606         
azure-core-cpp                          1.16.1           
azure-identity-cpp                      1.13.2           
azure-storage-blobs-cpp                 12.15.0          
azure-storage-common-cpp                12.11.0          
azure-storage-files-datalake-cpp        12.13.0          
babel                                   2.18.0           
beautifulsoup4                          4.15.0           
bleach                                  6.4.0            
bleach-with-css                         6.4.0            
blosc                                   1.21.7           
bokeh                                   3.10.0           
bqplot                                  0.13.1           
bqscales                                0.3.7            
branca                                  0.8.2            
brotli                                  1.2.1            
brotli-bin                              1.2.1            
brotli-python                           1.2.1            
bzip2                                   1.0.8            
c-ares                                  1.34.9           
ca-certificates                         2026.10.23       
cairo                                   1.18.6           
certifi                                 2026.10.23       
cffi                                    2.1.1            
charset-normalizer                      3.5.1            
click                                   8.5.0            
click-plugins                           1.1.1.2          
cligj                                   0.7.2            
cloudpickle                             3.1.2            
colour                                  0.1.5            
comm                                    0.2.3            
contourpy                               1.4.0            
cpython                                 3.12.16          
cryptography                            50.0.2           
cycler                                  0.12.1           
cytoolz                                 1.2.0            
dask                                    2026.8.0         
dask-core                               2026.8.0         
dav1d                                   1.2.1            
dbus                                    1.16.2           
debugpy                                 1.8.22           
decorator                               5.3.1            
defusedxml                              0.7.1            
distributed                             2026.8.0         
earthengine-api                         1.7.51           
eerepr                                  0.1.4            
executing                               2.3.0            
ffmpeg                                  8.0.1            
ffmpeg-python                           0.2.0            
filelock                                4.2.4            
folium                                  0.20.0           
font-ttf-dejavu-sans-mono               2.37             
font-ttf-inconsolata                    3.000            
font-ttf-source-code-pro                2.038            
font-ttf-ubuntu                         0.83             
fontconfig                              2.18.3           
fonts-conda-ecosystem                   1                
fonts-conda-forge                       1                
fonttools                               4.68.0           
fqdn                                    1.6.0            
freetype                                2.14.3           
freexl                                  2.0.0            
fribidi                                 1.0.18           
frozenlist                              1.8.0            
fsspec                                  2026.9.0         
future                                  1.0.0            
gdk-pixbuf                              2.44.8           
gdown                                   6.5.1            
geeadd                                  0.5.6            
geemap                                  0.38.9           
geocoder                                1.38.1           
geojson                                 3.3.0            
geopandas                               1.2.0            
geopandas-base                          1.2.0            
geos                                    3.14.1           
gettext                                 0.25.1           
gettext-tools                           0.25.1           
gflags                                  2.3.1            
giflib                                  6.1.3            
glog                                    0.7.1            
glslang                                 16.6.0           
gmp                                     6.3.0            
gnutls                                  3.7.6            
google-api-core                         2.33.0           
google-api-python-client                2.201.0          
google-auth                             2.62.1           
google-auth-httplib2                    0.4.4            
google-cloud-core                       2.5.0            
google-cloud-storage                    3.13.0           
google-crc32c                           1.9.0            
google-resumable-media                  2.11.0           
googleapis-common-protos                1.75.0           
graphite2                               1.3.15           
grpcio                                  1.85.1           
grpcio-status                           1.73.1           
h11                                     0.16.0           
h2                                      4.4.1            
harfbuzz                                15.0.0           
hpack                                   4.2.0            
httpcore                                1.0.9            
httplib2                                0.32.1           
httpx                                   0.28.1           
hyperframe                              6.1.0            
icu                                     78.3             
idna                                    3.20             
importlib-metadata                      10.0.0           
ipyevents                               2.0.4            
ipyfilechooser                          0.6.0            
ipykernel                               7.4.0            
ipyleaflet                              0.20.0           
ipython                                 9.18.1           
ipython_pygments_lexers                 1.1.1            
ipytree                                 0.2.2            
ipywidgets                              8.1.9            
isoduration                             20.11.0          
jedi                                    0.20.1           
jinja2                                  3.1.6            
joblib                                  1.6.0            
json-c                                  0.18             
json5                                   0.17.3           
jsonpointer                             3.8              
jsonschema                              4.26.0           
jsonschema-specifications               2025.9.1         
jsonschema-with-format-nongpl           4.26.0           
jupyter-builder                         1.2.4            
jupyter-lsp                             2.3.1            
jupyter_client                          8.10.0           
jupyter_core                            5.9.1            
jupyter_events                          0.12.1           
jupyter_leaflet                         0.20.0           
jupyter_server                          2.21.1           
jupyter_server_terminals                0.5.4            
jupyterlab                              4.6.5            
jupyterlab_pygments                     0.3.0            
jupyterlab_server                       2.28.1           
jupyterlab_widgets                      3.0.17           
kiwisolver                              1.5.1            
krb5                                    1.22.2           
lame                                    3.100            
lark                                    1.3.1            
lcms2                                   2.20             
lerc                                    4.3.0            
libabseil                               20250512.1       
libarchive                              3.8.11           
libarrow                                21.0.0           
libarrow-acero                          21.0.0           
libarrow-compute                        21.0.0           
libarrow-dataset                        21.0.0           
libarrow-substrait                      21.0.0           
libasprintf                             0.25.1           
libasprintf-devel                       0.25.1           
libass                                  0.17.4           
libblas                                 3.11.0           
libbrotlicommon                         1.2.1            
libbrotlidec                            1.2.1            
libbrotlienc                            1.2.1            
libcblas                                3.11.0           
libcrc32c                               1.1.2            
libcurl                                 8.23.0           
libcxx                                  23.1.4           
libdeflate                              1.25             
libedit                                 3.1.20260512     
libev                                   4.33             
libevent                                2.1.12           
libexpat                                2.9.0            
libffi                                  3.7.0            
libfreetype                             2.14.3           
libfreetype6                            2.14.3           
libgcc                                  16.2.0           
libgdal-core                            3.13.3           
libgettextpo                            0.25.1           
libgettextpo-devel                      0.25.1           
libgfortran                             16.2.0           
libgfortran5                            16.2.0           
libglib                                 2.90.0           
libgoogle-cloud                         2.39.0           
libgoogle-cloud-storage                 2.39.0           
libgrpc                                 1.73.1           
libharfbuzz                             15.0.0           
libharfbuzz-devel                       15.0.0           
libhwloc                                2.15.0           
libhwy                                  1.4.0            
libiconv                                1.18             
libidn2                                 2.3.8            
libintl                                 0.25.1           
libintl-devel                           0.25.1           
libjpeg-turbo                           3.2.1            
libjxl                                  0.12.0           
libkml                                  1.3.0            
liblapack                               3.11.0           
liblzma                                 5.8.3            
libnghttp2                              1.71.0           
libogg                                  1.3.5            
libopenblas                             0.3.34           
libopentelemetry-cpp                    1.21.0           
libopentelemetry-cpp-headers            1.21.0           
libopenvino                             2025.4.1         
libopenvino-arm-cpu-plugin              2025.4.1         
libopenvino-auto-batch-plugin           2025.4.1         
libopenvino-auto-plugin                 2025.4.1         
libopenvino-hetero-plugin               2025.4.1         
libopenvino-ir-frontend                 2025.4.1         
libopenvino-onnx-frontend               2025.4.1         
libopenvino-paddle-frontend             2025.4.1         
libopenvino-pytorch-frontend            2025.4.1         
libopenvino-tensorflow-frontend         2025.4.1         
libopenvino-tensorflow-lite-frontend    2025.4.1         
libopus                                 1.6.1            
libpango                                1.58.2           
libpango-devel                          1.58.2           
libparquet                              21.0.0           
libpng                                  1.6.59           
libprotobuf                             6.31.1           
libpsl                                  0.23.1           
libpython                               3.12.16          
libre2-11                               2025.11.05       
librsvg                                 2.62.4           
librttopo                               1.1.0            
libsodium                               1.0.22           
libspatialite                           5.1.0            
libsqlite                               3.54.1           
libssh2                                 1.11.1           
libtasn1                                4.21.0           
libthrift                               0.22.0           
libtiff                                 4.7.2            
libunistring                            0.9.10           
libusb                                  1.0.30           
libutf8proc                             2.11.3           
libvorbis                               1.3.7            
libvpx                                  1.15.2           
libvulkan-loader                        1.4.357.0        
libwebp-base                            1.6.0            
libxcb                                  1.17.0           
libxml2                                 2.15.4           
libxml2-16                              2.15.4           
libxml2-devel                           2.15.4           
libzlib                                 1.3.2            
llvm-openmp                             23.1.4           
locket                                  1.0.0            
logzero                                 1.7.0            
lz4                                     4.4.5            
lz4-c                                   1.10.0           
lzo                                     2.10             
mapclassify                             2.11.0           
markupsafe                              3.0.4            
matplotlib-base                         3.10.9           
matplotlib-inline                       0.2.2            
minizip                                 4.2.2            
mistune                                 3.4.0            
msgpack-python                          1.2.4            
multidict                               7.2.1            
munkres                                 1.1.4            
muparser                                2.3.5            
narwhals                                2.28.0           
nbclient                                0.11.0           
nbconvert-core                          7.17.2           
nbformat                                5.11.1           
ncurses                                 6.6              
nest-asyncio2                           1.7.4            
nettle                                  3.8.1            
networkx                                3.7              
nlohmann_json                           3.12.0           
notebook-shim                           0.2.4            
numpy                                   2.5.4            
openh264                                2.6.0            
openjpeg                                2.5.4            
openssl                                 3.6.5            
orc                                     2.2.1            
overrides                               7.7.0            
packaging                               26.3             
pandas                                  3.1.0            
pandocfilters                           1.5.1            
pango                                   1.58.2           
parso                                   0.8.7            
partd                                   1.4.2            
pcre2                                   10.47            
pexpect                                 4.9.0            
pillow                                  13.0.0           
pip                                     26.2.2           
pixman                                  0.46.4           
platformdirs                            4.14.3           
plotly                                  7.1.0            
proj                                    9.9.0            
prometheus-cpp                          1.3.0            
prometheus_client                       0.26.0           
prompt-toolkit                          3.0.53           
propcache                               0.5.4            
proto-plus                              1.28.2           
protobuf                                6.31.1           
psutil                                  7.2.2            
psygnal                                 0.16.1           
pthread-stubs                           0.4              
ptyprocess                              0.7.0            
pugixml                                 1.15             
pure_eval                               0.2.4            
pyarrow                                 21.0.0           
pyarrow-core                            21.0.0           
pyasn1                                  0.6.5            
pyasn1-modules                          0.4.2            
pycparser                               3.12             
pycrs                                   1.0.2            
pygments                                2.21.0           
pyobjc-core                             13.0             
pyobjc-framework-cocoa                  13.0             
pyogrio                                 0.13.0           
pyparsing                               3.3.3            
pyperclip                               1.11.0           
pyproj                                  3.8.0            
pyshp                                   3.1.6            
pysocks                                 1.7.1            
python                                  3.12.16          
python-abi3                             3.12             
python-box                              7.4.1            
python-dateutil                         4.0.0            
python-fastjsonschema                   2.22.3           
python-gil                              3.12.16          
python-json-logger                      4.2.0            
python-tzdata                           2026.6           
python_abi                              3.12             
pyu2f                                   0.1.5            
pyyaml                                  6.0.3            
pyzmq                                   27.3.0           
qhull                                   2020.2           
rasterio                                1.5.2            
ratelim                                 0.1.6            
re2                                     2025.11.05       
readline                                8.3              
referencing                             0.37.0           
requests                                2.34.2           
rfc3339-validator                       0.1.4            
rfc3986-validator                       0.1.1            
rfc3987-syntax                          1.1.0            
rioxarray                               0.23.0           
rpds-py                                 2026.9.1         
ruamel.yaml                             0.19.1           
ruamel.yaml.clib                        0.2.15           
scikit-learn                            1.9.1            
scipy                                   1.18.1           
scooby                                  0.12.1           
sdl2                                    2.32.56          
sdl3                                    3.4.20           
send2trash                              2.1.0            
setuptools                              84.2.1           
shaderc                                 2025.5           
shapely                                 2.2.0            
six                                     1.17.0           
snappy                                  1.2.2            
sniffio                                 1.3.1            
snuggs                                  1.4.7            
sortedcontainers                        2.4.0            
soupsieve                               4.0              
spirv-tools                             2026.4           
sqlite                                  3.54.1           
stack_data                              0.6.3            
svt-av1                                 3.1.2            
tbb                                     2023.1.0         
tblib                                   3.2.2            
terminado                               0.18.1           
threadpoolctl                           3.7.0            
tinycss2                                1.4.0            
tk                                      8.6.13           
toml                                    0.10.2           
tomli                                   2.5.0            
toolz                                   1.2.0            
tornado                                 6.5.10           
tqdm                                    4.70.1           
traitlets                               5.16.1           
traittypes                              0.2.3            
typing-extensions                       4.16.0           
typing_extensions                       4.16.0           
typing_utils                            0.1.0            
tzdata                                  2026e            
unicodedata2                            18.0.0           
uri-template                            1.3.0            
uriparser                               0.9.8            
uritemplate                             4.2.0            
urllib3                                 2.5.0            
wcwidth                                 0.9.4            
webcolors                               25.10.0          
webencodings                            0.6.1            
websocket-client                        1.9.2            
wheel                                   0.48.0           
widgetsnbextension                      4.0.16           
wrapt                                   2.5.2            
x264                                    1!164.3095       
x265                                    3.5              
xarray                                  2026.9.0         
xee                                     0.1.2            
xerces-c                                3.3.0            
xorg-libxau                             1.0.12           
xorg-libxdmcp                           1.1.5            
xyzservices                             2026.9.1         
yaml                                    0.2.5            
yarl                                    1.25.1           
zeromq                                  4.3.5            
zict                                    3.0.0            
zipp                                    4.1.2            
zlib                                    1.3.2            
zlib-ng                                 2.3.3            
zstandard                               0.25.0           
zstd                                    1.5.7            
```