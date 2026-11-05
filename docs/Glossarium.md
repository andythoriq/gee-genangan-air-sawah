# Glosarium Proyek

Daftar istilah yang dipakai di seluruh proyek: kode di `src/`, laporan di `docs/`, dan percakapan
teknis sehari-hari. Ditulis untuk orang yang baru masuk ke proyek ini — mahasiswa berikutnya,
pembimbing, atau penguji.

Cara pakai: cari istilahnya, baca kolom **arti**, lalu kolom **di proyek ini** untuk melihat angka atau
pilihan yang benar-benar dipakai. Istilah asing dipertahankan dalam tanda kurung karena kode dan
dokumen teknis memakainya dalam bahasa Inggris.

Urutan bagian:

1. [Wilayah dan data satelit](#1-wilayah-dan-data-satelit)
2. [Indeks spektral dan ambang](#2-indeks-spektral-dan-ambang)
3. [Validasi dan statistik](#3-validasi-dan-statistik)
4. [Morfologi citra](#4-morfologi-citra)
5. [Analisis dan kontrol](#5-analisis-dan-kontrol)
6. [Perangkat dan implementasi](#6-perangkat-dan-implementasi)
7. [Istilah internal proyek](#7-istilah-internal-proyek)

---

## 1. Wilayah dan data satelit

| Istilah | Arti | Di proyek ini |
|---|---|---|
| **AOI** (Area of Interest) | Poligon yang membatasi seluruh analisis. Semua luas, cakupan, dan peta dihitung di dalam poligon ini saja. | 28 titik sudut hasil survei lapangan, 172,7 ha, sekitar 1,9 km utara–selatan dan 1,7 km timur–barat. Tersimpan di `config.AOI_RING`. |
| **Vertex** (titik sudut) | Satu pasang koordinat [bujur, lintang] yang membentuk poligon. | 28 vertex, vertex pertama diulang di akhir untuk menutup cincin poligon. |
| **WGS84** | Sistem koordinat geografis global, satuan derajat. | Urutan koordinat di proyek ini selalu [bujur, lintang] — urutan yang dipakai Earth Engine. |
| **Scene** (adegan) | Satu rekaman citra dari satu tanggal akuisisi. Satu scene mencakup area sekitar 110 × 110 km. | Jendela 16 hari bisa berisi 1 sampai 21 scene. |
| **Akuisisi** | Proses perekaman citra oleh satelit pada satu waktu. | "Tanggal akuisisi" = tanggal scene direkam, bukan tanggal diunduh. |
| **Revisit** | Selang waktu satelit kembali merekam lokasi yang sama. | Sentinel-2 sekitar 5 hari karena ada dua satelit (2A dan 2B). |
| **Sentinel-2** | Misi satelit observasi bumi milik ESA. | Dipakai level 2A, resolusi 10 m untuk band tampak dan NIR. |
| **Level-2A** | Produk Sentinel-2 yang sudah dikoreksi atmosfer, sehingga nilainya adalah reflektan permukaan, bukan radian di sensor. | Semua analisis memakai level 2A. Level 1C tidak dipakai karena koreksi atmosfernya belum dilakukan. |
| **Reflektan permukaan** (surface reflectance) | Perbandingan cahaya yang dipantulkan permukaan terhadap cahaya yang datang, bernilai 0–1. | Disimpan sebagai bilangan bulat dengan skala 10.000, jadi nilai 2.500 berarti 0,25. |
| **Harmonized** | Baseline pemrosesan yang diseragamkan, supaya scene lama dan baru bisa dibandingkan tanpa lonjakan nilai. | Koleksi yang dipakai: `COPERNICUS/S2_SR_HARMONIZED`. |
| **Band** | Saluran spektral dengan rentang panjang gelombang tertentu. | B2 biru, B3 hijau, B4 merah, B8 NIR, B11 SWIR1. |
| **Resolusi spasial** | Ukuran satu piksel di permukaan bumi. | B2/B3/B4/B8 = 10 m; B11 = 20 m. |
| **Piksel** | Satuan terkecil citra. | Pada 10 m, satu piksel = 100 m². AOI 172 ha berisi sekitar 17.200 piksel. |
| **NIR** (near infrared) | Inframerah dekat, sekitar 842 nm di Sentinel-2. | Band B8. Dipakai NDWI. |
| **SWIR** (short-wave infrared) | Inframerah gelombang pendek, sekitar 1.610 nm (SWIR1). | Band B11. Dipakai MNDWI karena lebih tegas memisahkan air keruh dari tanah basah. |
| **Green** / **Red** / **Blue** | Band tampak hijau, merah, biru. | B3 / B4 / B2. Dipakai untuk citra true colour. |
| **Cloud masking** | Membuang piksel yang tertutup awan atau bayangannya, bukan membuang seluruh scene. | Dilakukan per piksel dengan SCL. |
| **SCL** (Scene Classification Layer) | Band kelas permukaan bawaan Sentinel-2 level 2A, berisi 12 kelas (0–11). | Masker default. Kelas yang dibuang: 3, 8, 9, 10, 11. |
| **QA60** | Band kualitas awan lama, berisi bit flag untuk awan opak (bit 10) dan cirrus (bit 11). | **Tidak dipakai.** Terukur membuang 100% AOI pada scene yang menurut SCL justru cerah. |
| **Bayangan awan** (cloud shadow) | Area yang gelap karena tertutup awan di atasnya. | SCL kelas 3, dibuang. |
| **Cirrus** | Awan tipis tinggi yang sulit terlihat tetapi menggeser nilai spektral. | SCL kelas 10, dibuang. |
| **Tutupan awan per scene** (CLOUDY_PIXEL_PERCENTAGE) | Persentase piksel berawan dalam satu scene, dihitung untuk seluruh scene, bukan untuk AOI. | Di AOI ini semua scene bernilai 70–100%, jadi filter di bawah 100 hanya membuang scene yang sebenarnya masih berguna. |
| **Cakupan** (coverage) | Persentase AOI yang benar-benar punya piksel valid setelah masking. | Angka pertama yang harus dilihat sebelum mempercayai hasil apa pun. |
| **Komposit** | Citra gabungan dari beberapa scene dalam satu jendela waktu. | Median, bukan rata-rata, supaya satu scene berawan tidak menarik nilai. |
| **Median** | Nilai tengah dari sekumpulan nilai setelah diurutkan. | Dipakai di dua tempat: median reflektan lalu indeks (index-of-median), atau indeks per scene lalu median (median-of-index). |
| **Jendela waktu** (window) | Rentang tanggal yang digabung menjadi satu komposit. | 4 hari untuk t1, 10 hari untuk t2, 16 hari di uji null-model. |
| **Jendela kejadian** (t1 / t2) | Dua jendela di sekitar tanggal banjir: t1 dianggap puncak, t2 dianggap surut. | t1 selalu 0% cakupan di semua event — tidak ada citra bebas awan saat banjir. |
| **Jendela referensi** (baseline) | Jendela "kondisi normal" sebagai pembanding, dipakai untuk menghitung selisih. | Tiga pilihan: `dry_season_2024`, `pre_event_2025_02`, `pre_event_2026_01`. |
| **Musim hujan / kemarau** | Pembagian musim di Jawa Barat. | Januari–Maret hujan puncak; Juni–Agustus kemarau. |
| **Fase tanam** | Tahap pertumbuhan padi: olah tanah, pindah tanam, vegetatif, generatif, panen, bera. | Perubahan fase tanam mengubah nilai indeks lebih besar daripada banjir — ini sumber kesalahan utama proyek. |
| **Olah tanah** (land preparation) | Penggenangan dan pembajakan sawah sebelum tanam. | Penyebab jendela Agustus 2025 terbaca 88,7 ha "air". |
| **Pindah tanam** (transplanting) | Memindahkan bibit padi ke petak. | Alasan jendela November–Desember 2024 tidak sepenuhnya kering. |
| **Bera** (fallow) | Petak yang dibiarkan tanpa tanaman. | Salah satu fase yang membuat MNDWI naik tanpa banjir. |
| **Pematang** (bund) | Galengan sempit pemisah petak sawah. | Lebar 1–2 piksel, sering salah terdeteksi sebagai air, dan menjadi alasan utama operasi morfologi. |
| **Sawah** | Lahan pertanian padi. | Objek utama penelitian. |
| **Kali** | Sungai (bahasa Sunda/Jawa). | Kali Cigadung dan Kali Anyar melintasi tepi timur AOI. |

---

## 2. Indeks spektral dan ambang

| Istilah | Arti | Di proyek ini |
|---|---|---|
| **Indeks spektral** | Angka tunggal hasil operasi antar band yang menonjolkan satu sifat permukaan, misalnya kebasahan. | Dua yang dipakai: NDWI dan MNDWI. |
| **NDWI** (Normalized Difference Water Index, McFeeters 1996) | (Hijau − NIR) / (Hijau + NIR). | Dihitung sebagai pembanding, **bukan** metode utama: gagal memisahkan air keruh dari tanah basah. |
| **MNDWI** (Modified NDWI, Xu 2006) | (Hijau − SWIR1) / (Hijau + SWIR1). | Metode utama. SWIR lebih tahan terhadap sedimen, dan sungai di lokasi ini keruh. |
| **Delta MNDWI** | Selisih MNDWI jendela kejadian dikurangi MNDWI jendela referensi. | Besaran yang benar-benar dipakai untuk klasifikasi. Positif berarti lebih basah daripada referensi. |
| **Nilai ternormalisasi** | Hasil bagi dua selisih band, selalu berada di antara −1 dan 1. | Karena ternormalisasi, skala 10.000 pada reflektan tidak perlu dibagi dulu. |
| **Ambang** (threshold) | Nilai batas yang memisahkan kelas air dan bukan air. | 0,05 untuk delta MNDWI. |
| **Ambang operasi** (operating point) | Ambang yang benar-benar dipakai dalam analisis, setelah dipilih dari sapuan. | 0,05, nilai paling konservatif di dalam plateau. |
| **Sapuan ambang** (threshold sweep) | Menghitung ulang seluruh metrik untuk banyak nilai ambang, lalu membandingkannya. | 121 nilai dari −0,60 sampai 0,60 dengan langkah 0,01. |
| **Plateau** | Rentang ambang yang menghasilkan confusion matrix identik, sehingga matriks tidak bisa memilih di dalamnya. | −0,32 sampai 0,05. Di dalam rentang ini semua titik validasi terpisah dengan benar. |
| **Otsu** (metode Otsu) | Cara memilih ambang dari histogram saja, dengan memaksimalkan varians antarkelas. Tidak memakai label. | Menghasilkan 0,045 pada jendela banjir — hampir sama dengan 0,05. Tetapi pada jendela tanpa banjir tetap membagi 45–65% area, jadi hanya dipakai sebagai pembanding. |
| **Histogram** | Sebaran jumlah piksel per rentang nilai. | 400 bin untuk delta, 200 bin untuk MNDWI absolut. |
| **Bin** | Satu rentang nilai di dalam histogram. | Lebar 0,01 untuk delta. |
| **Bimodal** | Sebaran dengan dua puncak, menandakan dua populasi yang wajar dipisahkan. | Delta MNDWI di proyek ini **tidak** bimodal: satu puncak di sekitar −0,015 dengan ekor panjang ke positif. |
| **Unimodal** | Sebaran dengan satu puncak. | Bentuk sebenarnya histogram delta, dan alasan Otsu tidak bisa dipercaya sebagai detektor. |
| **Ekor** (tail) | Bagian sebaran yang memanjang ke satu sisi. | Ekor positif adalah piksel yang menjadi lebih basah. |
| **Analisis sensitivitas** | Mengulang analisis pada beberapa nilai parameter untuk melihat apakah kesimpulannya berubah. | Dilakukan pada ambang 0,03–0,10; kesimpulan tidak berubah. |

---

## 3. Validasi dan statistik

| Istilah | Arti | Di proyek ini |
|---|---|---|
| **Titik validasi** | Lokasi di lapangan yang kondisinya diketahui, dipakai menguji prediksi citra. | 4 titik: Sawah Kontrak 1, Sawah Impres, Sawah PU & Keprak, Sawah Kontrak 2. |
| **Kontrol negatif** | Titik yang seharusnya **tidak** tergenang. Tanpa ini, false positive tidak akan pernah terdeteksi. | Sawah Impres (`expected: "safe"`). Letaknya 1.051 m di luar AOI — kelemahan yang tercatat. |
| **Buffer** | Lingkaran di sekitar titik untuk merata-ratakan beberapa piksel. | 30 m, sekitar 9 piksel 10 m. |
| **Ground truth** | Kondisi sebenarnya di lapangan yang dijadikan acuan. | Hasil survei 4 sawah, dicatat sebagai "inundated" atau "safe". |
| **Confusion matrix** | Tabel 2×2 yang membandingkan prediksi dengan kenyataan. | Dihitung pada ambang operasi. |
| **TP** (true positive) | Tergenang dan diprediksi air. | 2 titik. |
| **FN** (false negative) | Tergenang tetapi diprediksi kering. | 0 titik. |
| **FP** (false positive) | Aman tetapi diprediksi air. | 0 titik. |
| **TN** (true negative) | Aman dan diprediksi kering. | 1 titik. |
| **Recall** / sensitivitas | TP dibagi (TP + FN). Kemampuan menemukan genangan yang benar-benar ada. | 1,00. |
| **Specificity** | TN dibagi (TN + FP). Kemampuan menolak area yang sebenarnya kering. | 1,00, tetapi hanya didukung satu titik. |
| **Balanced accuracy** | Rata-rata recall dan specificity, dipakai karena kelas air dan kering tidak seimbang. | 1,00 pada ambang 0,05. |
| **Akurasi keseluruhan** | (TP + TN) dibagi seluruh titik. | Tidak dipakai sendirian karena bisa menyesatkan saat kelas tidak seimbang. |
| **Sampel acak berstrata** | Mengambil titik secara acak di dalam setiap kelompok (misalnya dekat saluran, tengah petak) agar mewakili seluruh area. | Belum dilakukan. Ini perbaikan validasi yang paling diperlukan. |
| **Interpretasi visual** | Menentukan label dengan melihat citra resolusi tinggi, bukan mendatangi lokasi. | Alternatif yang sah untuk menambah titik, asal dinyatakan sebagai interpretasi, bukan survei. |
| **Interval kepercayaan** | Rentang ketidakpastian di sekitar satu angka. | Dengan 4 titik, ketidakpastiannya sangat lebar dan tidak dilaporkan — sebuah kekurangan. |

---

## 4. Morfologi citra

| Istilah | Arti | Di proyek ini |
|---|---|---|
| **Operasi morfologi** | Operasi pada citra biner yang mengubah bentuk objek berdasarkan bentuk kernel. | Dipakai untuk membersihkan noise pada mask air. |
| **Structuring element** | Bentuk kernel yang menentukan hasil operasi, misalnya lingkaran atau garis. | Lingkaran (pembanding) dan garis 17 arah (metode utama). |
| **Kernel** | Matriks kecil yang digeser ke seluruh citra. | Radius 1–2 piksel untuk lingkaran; panjang 15 piksel untuk garis. |
| **Erosi** | Menggerus objek: piksel bertahan hanya jika seluruh tetangganya juga objek. | `focalMin`. |
| **Dilasi** | Menumbuhkan objek: piksel menjadi objek jika salah satu tetangganya objek. | `focalMax`. |
| **Opening** | Erosi lalu dilasi. Menghapus objek kecil. | Cara standar, tetapi **menghapus sungai** selebar 1 piksel. |
| **Closing** | Dilasi lalu erosi. Menutup lubang kecil. | Dipakai setelah path opening untuk merapikan tepi. |
| **focalMin / focalMax** | Nama fungsi Earth Engine untuk erosi dan dilasi. | Argumen `radius` dan `kernelType="circle"` bawaan, bukan kernel buatan sendiri. |
| **Radius** | Ukuran kernel lingkaran dalam piksel. | 1 piksel = 10 m. |
| **Path opening** | Opening yang hanya mempertahankan objek yang memuat garis lurus sepanjang tertentu, di salah satu dari banyak arah. | 17 arah (0° sampai 176°, langkah 11°), panjang 15 piksel (150 m). |
| **Preserve linear** | Trik menebalkan objek 1 piksel sebelum path opening lalu menipiskannya lagi, supaya kanal sempit tidak hilang. | Dilasi 1 piksel → path opening → erosi 1 piksel. Menaikkan retensi sungai dari 35% ke 100%. |
| **Komponen terhubung** (connected component) | Kumpulan piksel yang saling bersentuhan dan dianggap satu objek. | Dipakai versi JavaScript lewat `connectedPixelCount`. |
| **connectedPixelCount** | Fungsi Earth Engine yang menghitung ukuran komponen terhubung per piksel. | Alternatif yang diuji: menyisakan 100% blok noise dan hanya 35% sungai (4-connected). |
| **Noise** | Piksel air palsu, biasanya dari pematang basah atau bayangan. | Sasaran utama pembersihan. |
| **Retensi** | Persentase objek yang masih tersisa setelah operasi morfologi. | Ukuran keberhasilan: sungai 100%, pematang 0%, blok noise 0%. |
| **Geometri sintetis** | Gambar buatan dengan jawaban yang sudah diketahui, dipakai menguji operator. | Satu kanal 560 m, lima pematang 60 m, lima blok 40 m, satu badan air 200 m. |

---

## 5. Analisis dan kontrol

| Istilah | Arti | Di proyek ini |
|---|---|---|
| **Multitemporal** | Analisis yang membandingkan beberapa waktu. | Inti judul penelitian: perubahan sebaran genangan antarwaktu. |
| **Persistent** (genangan menetap) | Air terdeteksi di kedua jendela. | 5,6 ha terhadap referensi Nov–Des 2024. |
| **New** (genangan baru) | Air hanya di jendela kejadian. | 13,9 ha. |
| **Receded** (genangan surut) | Air hanya di jendela referensi. | 15,5 ha. |
| **Luas** (ha) | Ukuran area dalam hektare. 1 ha = 10.000 m². | Semua luas dilaporkan dalam ha. |
| **pixelArea** | Citra Earth Engine yang tiap pikselnya berisi luas piksel itu dalam m². | Dijumlahkan lalu dibagi 10.000 untuk mendapat ha. |
| **reduceRegion** | Fungsi Earth Engine untuk meringkas nilai citra di dalam satu poligon. | Dipakai untuk luas, cakupan, dan histogram. |
| **Null model** (kontrol null) | Menjalankan pipeline yang sama pada kondisi yang seharusnya tidak menghasilkan apa-apa, untuk melihat seberapa besar "hasil" yang muncul tanpa sebab. | 17 jendela tenang 2025: median 17,9 ha, maksimum 88,7 ha. |
| **Lantai** (floor) | Nilai yang tetap muncul saat tidak ada kejadian; batas bawah yang harus dilampaui agar sebuah angka bermakna. | 17,9 ha (median jendela tenang). Angka banjir 43,4 ha tidak jauh di atasnya. |
| **Perancu** (confound) | Faktor lain yang berubah bersamaan dan ikut terukur, sehingga sulit dipisahkan dari efek yang dicari. | Perubahan fase tanam adalah perancu utama proyek ini. |
| **Artefak** | Angka atau pola yang tampak seperti temuan tetapi berasal dari metode, bukan dari lapangan. | 88,7 ha di Agustus 2025 adalah artefak fase tanam. |
| **Peringkat** (rank) | Posisi satu nilai di dalam sebaran nilai lain. | Angka banjir lebih tinggi dari 10 dari 14 jendela tenang. |

---

## 6. Perangkat dan implementasi

| Istilah | Arti | Di proyek ini |
|---|---|---|
| **GEE** (Google Earth Engine) | Platform komputasi geospasial berbasis cloud; citra diproses di server, bukan di komputer lokal. | Semua perhitungan citra terjadi di GEE. |
| **ImageCollection** | Kumpulan citra di GEE, biasanya hasil filter tanggal dan wilayah. | `COPERNICUS/S2_SR_HARMONIZED` setelah difilter. |
| **Image** | Satu citra multi-band di GEE. | Hasil komposit, indeks, dan mask semuanya Image. |
| **Geometry** | Objek geometri (titik, poligon) di GEE. | AOI adalah satu Polygon; titik validasi adalah Point. |
| **FeatureCollection** | Kumpulan fitur (geometri + properti). | Dipakai untuk mengembalikan tabel cakupan bulanan. |
| **Mask** | Penanda piksel mana yang valid. Piksel bermask tidak ikut dihitung. | Inti dari seluruh pengolahan awan. |
| **selfMask** | Menjadikan nilai piksel sebagai mask: nilai 1 tampil, nilai 0 disembunyikan. | Dipakai untuk menampilkan mask air. |
| **updateMask** | Mengganti mask sebuah citra dengan mask citra lain. | Dipakai untuk memulihkan area berawan setelah morfologi. |
| **Clip** | Memotong citra sesuai poligon. | Semua layer peta dipotong ke AOI; perhitungan luas dibatasi oleh `geometry`, bukan oleh clip. |
| **Tile URL** / **getMapId** | Alamat potongan citra yang bisa ditampilkan di peta web. | Setiap layer peta di aplikasi memakai tile URL dari GEE. |
| **Thumbnail** | Gambar kecil hasil render server. | Disimpan sebagai `water_mask.png` di setiap run. |
| **Streamlit** | Framework Python untuk membuat aplikasi web dari skrip. | Aplikasi analisis mandiri di `src/app.py`. |
| **session_state** | Penyimpanan nilai antar interaksi di Streamlit. | Menyimpan hasil perhitungan agar tidak dihitung ulang saat berpindah tab. |
| **Cache** | Menyimpan hasil fungsi agar pemanggilan berikutnya instan. | Dipakai untuk pemindaian cakupan dan pratinjau citra. |
| **Folium** | Pustaka Python untuk membuat peta interaktif berbasis Leaflet. | Peta di tab Peta. |
| **Basemap** | Peta latar: jalan (OpenStreetMap) atau citra satelit (Esri). | Bisa diganti dari kontrol layer. |
| **Layer control** | Widget di kanan atas peta untuk menyalakan atau mematikan layer. | Juga jalan untuk menyalakan citra mentah saat cakupan 0%. |
| **EPSG / UTM / WGS84** | Kode sistem koordinat. UTM membagi bumi menjadi zona proyeksi bersatuan meter. | EPSG:32748 = UTM zona 48S, dipakai untuk uji geometri sintetis. |
| **Geodesic** | Perhitungan di permukaan bumi yang melengkung, bukan bidang datar. | `aoi.area(1)` menghasilkan 172,7 ha secara geodesik. |
| **Resampling** | Penyesuaian grid saat dua band beresolusi berbeda digabung. | B11 (20 m) di-resample ke grid 10 m B3 saat MNDWI dihitung. |
| **tileScale** | Pengali ubin untuk mengurangi beban memori saat komputasi besar. | Dipakai pada reduksi luas. |
| **maxPixels** | Batas jumlah piksel yang boleh diproses dalam satu reduksi. | Dinaikkan ke 10⁹ agar AOI tidak terpotong. |
| **bestEffort** | Meminta GEE menyelesaikan reduksi dengan perkiraan bila batas piksel terlampaui. | Dipakai pada perhitungan cakupan. |
| **CSV / JSON** | Format berkas untuk menyimpan tabel dan konfigurasi. | Hasil run disimpan sebagai `points.csv`, `sweep.csv`, `run.json`. |

---

## 7. Istilah internal proyek

| Istilah | Arti | Di proyek ini |
|---|---|---|
| **Pipeline** | Rangkaian tahap yang selalu dijalankan berurutan. | Konfigurasi → akses citra → masker → komposit → indeks → ambang → morfologi → perbandingan → kontrol. |
| **Run** | Satu eksekusi analisis dengan satu set parameter. | Disimpan di `outputs/runs/<waktu>_<label>/`. |
| **Modul** | Satu berkas Python dengan satu tanggung jawab. | `config`, `sentinel`, `indices`, `calibrate_threshold`, `morphology`, `compare_baseline`, `null_model`, `runs`, `app`. |
| **Laporan kerja** | Catatan proses dan temuan, bukan laporan akhir. | `docs/agent-reports/2026-11-05-data-availability-and-threshold.md`. |
| **Laporan proses** | Ringkasan alur dan temuan untuk presentasi atau review. | `docs/laporan-2026-11-06.md`. |
| **Ambang terkalibrasi** | Ambang yang dipilih berdasarkan bukti, bukan nilai bawaan. | `config.CALIBRATED_DELTA_THRESHOLD = 0.05`. |
| **Ambang pratinjau** | Ambang kasar khusus untuk menggambar peta percobaan. | `config.PREVIEW_THRESHOLD = 0.0`. Jangan dipakai untuk kesimpulan. |
