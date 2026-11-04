import ee
import geemap

# Inisialisasi library dengan project Anda
ee.Initialize(project='tubes-pcd-praktik-004-019')

# 2. Tentukan Area of Interest (AOI) menggunakan koordinat [Bujur, Lintang]
# Contoh: Titik koordinat di sekitar Jakarta
aoi = ee.Geometry.Point([106.8271, -6.1751]).buffer(10000) # Buffer 10 km

# 3. Panggil dan Filter Citra Satelit (Contoh: Sentinel-2)
satelit = (
    ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(aoi)
    .filterDate('2025-01-01', '2026-10-01') # Filter rentang waktu
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)) # Cari yang awannya < 10%
    .median() # Ambil nilai tengah (menghilangkan sisa awan)
    .clip(aoi) # Potong citra sesuai AOI
)

# 4. Atur Parameter Visualisasi (Warna Asli / True Color)
vis_params = {
    'bands': ['B4', 'B3', 'B2'], # Band Merah, Hijau, Biru
    'min': 0,
    'max': 3000,
}

# 5. Buat Peta Interaktif
Map = geemap.Map()
Map.centerObject(aoi, zoom=12) # Fokuskan peta ke AOI
Map.addLayer(satelit, vis_params, 'Citra Satelit Sentinel-2')
Map.addLayer(aoi, {'color': 'red'}, 'Batas AOI Anda')

# 6. Simpan peta sebagai file HTML lokal dan buka otomatis
Map.to_html('peta_aoi.html')
print("Peta berhasil dibuat! Membuka peta_aoi.html di browser...")

# Buka otomatis di browser default
import webbrowser
webbrowser.open('peta_aoi.html')
