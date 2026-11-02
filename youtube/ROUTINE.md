# Haftalık YouTube belgeseli — talimatlar (bulut rutini)

Kanal: **Terra Wild Nature Belgesel** (youtube.com/@terrawildnature-tr). Her hafta **1 belgesel**, yayın **Cumartesi 20:00** (Türkiye).

- **Sen (Claude, haftalık rutin):** Konuyu seçer, ~30 dakikalık senaryoyu yazar, bilgileri doğrular, telifsiz fotoğrafları seçer ve `youtube/docs/<klasör>/` altına üç dosya commit'lersin: `script.json`, `photos.json`, `meta.json`.
- **GitHub Actions (`.github/workflows/youtube-doc.yml`):** Push gelince fotoğrafları indirir, seslendirir, videoyu 16 parçada paralel üretir, kapak/açıklama/hikâye görselini hazırlar, paketi yayımlar ve sahibine bildirim açar.

Bu görevde **Instagram işi yapma** (`CLAUDE.md`'deki gönderi/Reels adımları bu rutine ait değil). Videoyu sen üretmiyorsun, YouTube'a da sen yüklemiyorsun.

## 0. Başlamadan

1. Kurulum: `python3 -m pip install -q --break-system-packages --ignore-installed pillow numpy`
2. `youtube/docs/` içinde `meta.json` olup `status.json` olmayan klasör varsa önceki belgesel henüz üretilmemiş demektir: **yeni belgesel hazırlama**, "sırada bekleyen belgesel var: <klasör>" yazıp bitir.
3. `youtube/published.md` dosyasını oku: önceki konular ve canlılar.

## 1. Konu ve format

**Kanalın amacı vahşi doğa ve hayvanlardır (sahibinin kesin kuralı).** Belgeselin konusu her zaman **canlılar**: bir yer, dağ, göl, mağara ya da coğrafya belgeseli **yapma**. Yer/derinlik/boyut sadece canlıları sıralamak için bir çerçevedir. Başlık, kapak ve açıklama da hayvanları öne çıkarmalı ("… yaşayan canlılar", "… hayvanlar").

Format: **sayaçlı yolculuk/sıralama.** Ekranın solundaki sayaç (derinlik, yükseklik, boy, hız, yaşam süresi…) ilerler, her seviyede bir canlı anlatılır. Bölgeler (zone) ve ölçek karşılaştırmaları (landmark) yalnızca kısa geçişlerdir; segmentlerin büyük çoğunluğu canlı (creature) olmalı.

- `published.md`'deki bir konuyu tekrar etme. Oradaki canlıları ana canlı olarak kullanma.
- Konu, Türkiye'deki izleyicinin merak edeceği ve arayacağı bir **hayvan** konusu olmalı. Fikirler (yapılmamış olanlardan seç, benzerlerini de üretebilirsin):
  - **En küçükten en büyüğe hayvanlar:** milimetrelik canlılardan mavi balinaya (boy sıralaması, `scale: log`, `direction: up`)
  - **Dünyanın en hızlı hayvanları:** yavaştan en hızlıya, km/sa (hız sıralaması, `up`)
  - **En uzun yaşayan hayvanlar:** günlerden yüzyıllara (yaşam süresi, `scale: log`, `up`)
  - **Gökyüzünde en yükseğe uçan hayvanlar:** yerden 11.000 metreye uçan kuşlar ve böcekler (yükseklik, `up`)
  - **Yerin altında yaşayan hayvanlar:** topraktan mağaraların ve madenlerin derinliklerine (derinlik, `down`)
  - **Yağmur ormanının hayvanları:** orman tabanından ağaçların tepesine, her katta yaşayan canlılar (yükseklik, `up`)
  - **En soğuktan en sıcağa:** donan kurbağalardan kaynayan sulardaki canlılara (sıcaklık, `up`)
- **Fotoğraf kontrolü önce:** Konuyu kesinleştirmeden önce her aday canlı için uygun fotoğraf olup olmadığına bak (bölüm 4). En az 22 canlının iyi fotoğrafı yoksa başka konu seç.

## 2. Senaryo (`script.json`)

```json
{
  "title": "DAĞLARIN HAYVANLARI",
  "subtitle": "Ormandan 8.849 metreye",
  "journey": {
    "label": "YÜKSEKLİK", "unit": "m", "max": 8849, "direction": "up",
    "zones": [[0, 1000, "ORMAN"], [1000, 3000, "BULUT ORMANI"], [3000, 5000, "ALPİN"], [5000, 8000, "BUZUL"], [8000, 8849, "ÖLÜM BÖLGESİ"]],
    "stats": [
      {"name": "OKSİJEN", "x": [0, 2000, 4000, 6000, 8849], "y": [100, 79, 61, 46, 33], "style": "pct"},
      {"name": "SICAKLIK", "x": [0, 8849], "y": [25, -32], "prefix": "~", "suffix": " °C"},
      {"name": "BASINÇ", "x": [0, 8849], "y": [1013, 314], "suffix": " hPa"}],
    "palette": [[0, [90, 160, 210]], [1000, [70, 140, 200]], [3000, [50, 110, 185]], [6000, [30, 70, 150]], [8849, [12, 30, 80]]],
    "rays": 0, "particles": "snow", "glow": null,
    "music": ["Reawakening.mp3", "Investigations.mp3"]
  },
  "intro_photos": ["07_0", "15_1", "22_0", "30_0"],
  "segments": [
    {"type": "intro", "depth": 0, "text": "..."},
    {"type": "zone", "depth": 0, "name": "ORMAN KUŞAĞI", "range": "0 – 1.000 m", "text": "..."},
    {"type": "creature", "depth": 300, "name": "Bengal Kaplanı", "latin": "Panthera tigris tigris", "range": "0 – 3.000 m", "text": "..."},
    {"type": "landmark", "depth": 828, "name": "Burj Halife", "value": "828 m", "text": "..."},
    {"type": "zone", "depth": 5000, "name": "BUZUL KUŞAĞI", "range": "5.000 – 8.000 m", "music_switch": true, "text": "..."},
    {"type": "landmark", "depth": 8849, "name": "Everest Zirvesi", "value": "8.849 m", "chapter": true, "text": "..."},
    {"type": "outro", "depth": 8849, "text": "..."}
  ]
}
```

**journey** (okyanus dışındaki her konuda zorunlu):
- `label`: sayacın başlığı (DERİNLİK / YÜKSEKLİK). `unit`: "m". `max`: yolculuğun sonu. `direction`: `down` (iniş) ya da `up` (çıkış).
- `zones`: 4-6 bölge, `[başlangıç, bitiş, "KISA AD"]`, art arda ve `max`'ta biten. Ad en fazla ~14 karakter.
- `stats`: sayacın altındaki 3 değer. Her biri `x` (konum) ve `y` (değer) noktalarıyla doğrusal hesaplanır. Değerler gerçek olmalı (kaynağa bak). `style: "pct"` yüzde gösterir. `prefix`, `suffix`, `dec` (ondalık) kullanılabilir.
- `palette`: arka plan rengi, konuma göre `[konum, [R, G, B]]`. İniş: açıktan koyuya. Çıkış (gökyüzü): açık maviden koyu laciverte. Mağara/yer altı: toprak kahvesinden siyaha.
- `rays`: güneş ışınlarının görüneceği son konum (yoksa 0). `particles`: `marine` (su içi), `snow` (kar), `dust` (toz) ya da `null`. `glow`: bu konumdan sonra biyolüminesans pırıltıları (su altı konularında), yoksa `null`.
- `music`: iki parça: `Reawakening.mp3` (sakin, görkemli), `Investigations.mp3` (gizemli), `Ancient_Rite.ogg` (vahşi, enerjik). İkinci parça `music_switch: true` olan bölgede başlar.

**Sıralama belgeselleri** (boy, hız, yaşam süresi gibi): sayaç konumu canlının kendi değeridir ve her canlının değerleri farklıdır, bu yüzden:
- `"stats": []` yap ve her creature segmentine kendi bilgilerini ekle: `"stats": [["AĞIRLIK", "150 ton"], ["YAŞAM", "90 yıl"], ["NEREDE", "Tüm okyanuslar"]]` (3 satır, değer ≤ 16 karakter, doğrulanmış).
- Değerler çok geniş aralıktaysa (0,1 cm … 30 m) `"scale": "log"` ve `"min": <en küçük değerin altı>` ekle.
- Birim büyüyünce değişsin: `"units": [[0, "cm", 1], [100, "m", 0.01]]` (100 cm ve üstü metre gösterilir). Hız için `"unit": "km/sa"`.
- Kartta `range` yerine sıralama değeri görünsün: `"range_label": "BOY"` ve her canlıda `"range": "30 m"`.
- Zonlar sıralamanın kademeleri olur: `[[0.1, 1, "MİLİMETRİK"], [1, 10, "KÜÇÜK"], …]`.
- Landmark'lar tanıdık ölçeklerdir (bir otobüs 12 m, insan 1,7 m, bir futbol topu 22 cm).

**segments:**
- Sıra: `intro` → (zone, creature, landmark karışık) → `outro`. `depth` = yolculuktaki konum (metre). **Sadece aynı yöne ilerler** (0'dan `max`'a doğru, hiç geri gitmez).
- **Uzunluk:** toplam metin **18.000-21.000 karakter** (≈30 dakika). 40-50 segment: 4-6 zone, **24-30 creature**, 6-9 landmark.
  - intro ~700 karakter: kanca, bugün nereye gideceğimiz, "ekranın solundaki göstergeyi takip edin".
  - zone 300-450: bölgenin koşulları (sıcaklık, ışık, oksijen, basınç…).
  - creature 400-650: en şaşırtıcı bilgiyle başla, sonra yaşam alanı, beslenme, rekorlar. `range`: canlının yaşadığı aralık ("0 – 3.000 m") ya da kısa bir yer adı.
  - landmark 150-250: ölçek karşılaştırması ("Burj Halife'nin tepesi tam burada"). En önemli 1-2 tanesine `"chapter": true` (bölüm listesine girer).
  - outro ~550: kısa özet, en şaşırtıcı son bilgi, "Bu yolculuğu beğendiyseniz kanala abone olmayı ve videoyu beğenmeyi unutmayın. Bir sonraki belgeselde görüşmek üzere." **"Terra Wild Nature'ı izlediğiniz için teşekkürler" deme** (sahibi bunu istemedi).
- **Seslendirme kuralları** (metni yapay ses okuyacak): Sayıları yazıyla yaz ("sekiz bin sekiz yüz kırk dokuz metre", "üç yüz milyon"). Kısaltma, parantez, eğik çizgi, madde işareti kullanma. Kısa ve akıcı cümleler, belgesel anlatıcısı tonu, "biz" dili ("şimdi biraz daha yükseliyoruz").
- `name`: Türkçe adı (Türkçe yaygın adı yoksa anlaşılır bir Türkçe ad + `latin`). `latin`: bilimsel ad.
- `intro_photos` (isteğe bağlı): açılışta ilk 4'ü tam ekran gösterilir, en çarpıcı fotoğrafları seç. Verilmezse otomatik seçilir.

## 3. Bilgiler (doğruluk — çok önemli)

- Her canlı için en az İngilizce Wikipedia sayfasını oku (WebFetch `https://en.wikipedia.org/wiki/<Bilimsel_ad>`, olmazsa `curl`). Metindeki her sayı ve iddia orada (ya da başka güvenilir kaynakta: IUCN, Britannica, NOAA, üniversite/müze) geçmeli. **Canlının yaşadığı yükseklik/derinlik** de doğrulanmalı; canlıyı gerçekten bulunduğu seviyeye koy.
- Landmark yükseklikleri ve bölge değerleri (sıcaklık, oksijen, basınç) de doğrulanmalı.
- Emin olmadığın bilgiyi yazma, abartma. Kaynaklara erişemiyorsan belgesel üretme ve bunu son mesajında açıkça yaz.

## 4. Fotoğraflar (`photos.json`) — telif kuralları

Instagram'daki kuralların aynısı (`CLAUDE.md` bölüm 2): önce kamu malı / CC0, sonra CC BY, CC BY-SA. **Asla** NC, ND, lisansı belirsiz, filigranlı fotoğraf kullanma. Ayrıca belgeselde:
- **Çizim, gravür, müze örneği, doldurulmuş ya da ölü hayvan kullanma.** Bir canlının sadece böyle görselleri varsa o canlıyı seçme.
- Her creature için **2-3** farklı fotoğraf, her landmark için 1-2 (landmark'ta fotoğraf yoksa ekranda büyük rakam gösterilir, sorun değil). Zone ve intro/outro segmentlerine fotoğraf verme.
- Arama: `python tools/commons.py search "<bilimsel ad>"` ve `python tools/commons.py inat "<bilimsel ad>"`. Commons 429 verirse iNaturalist'e geç.
- İndir ve **Read ile gözle kontrol et:** `python tools/commons.py download "<File:... ya da iNat adresi>" youtube/docs/<klasör>/photos/<NN>_<k>.jpg`. Doğru canlı mı, net mi, hayvan kadrajın ortasında mı? Yatay fotoğrafları tercih et (video 16:9).
- Dosya adı: `<segment no, iki hane>_<sıra>.jpg` (ör. 7. segmentin ikinci fotoğrafı `07_1.jpg`).
- `photos.json` (anahtar = segment no):
```json
{
  "07": [
    {"file": "07_0.jpg", "src": "File:Bengal tiger in Ranthambhore.jpg", "source": "Wikimedia Commons", "license": "CC BY-SA 4.0", "author": "Ad Soyad"},
    {"file": "07_1.jpg", "src": "https://inaturalist-open-data.s3.amazonaws.com/photos/123/original.jpg", "source": "iNaturalist", "license": "CC0", "author": "kullanıcı"}
  ]
}
```
  `src`: Commons dosya adı ya da iNaturalist adresi (Actions buradan yeniden indirir). `author`: **indirme çıktısındaki tam ad** (arama satırındaki kısaltılmış hali değil), `license` aynen.
- Fotoğraf dosyalarını commit'leme (`.gitignore` engeller); depoya sadece üç JSON girer.

## 5. Başlık, kapak, açıklama (`meta.json`)

```json
{
  "title": "Yükseldikçe Hayatta Kalmak Zorlaşıyor: Dağların Hayvanları",
  "description": "Himalayaların eteklerindeki ormanlardan 8.849 metreye, her yükseklikte hayatta kalmayı başaran hayvanlarla tanışıyoruz. ... (2-4 cümle, anahtar kelimeler doğal geçsin)",
  "sources": "İngilizce Wikipedia, Britannica, National Geographic ve ilgili bilimsel yayınlar.",
  "hashtags": ["#belgesel", "#hayvanlar", "#vahşiyaşam", "#doğa", "#terrawildnature"],
  "tags": ["belgesel", "hayvan belgeseli", "dağ hayvanları", "kar leoparı", "himalaya hayvanları", "vahşi yaşam", "türkçe belgesel", "doğa belgeseli"],
  "thumb": {"lines": ["8.849 METRE", "YUKARIDA", "KİM YAŞIYOR?"], "photo": "21_0", "cx": 0.6, "cy": 0.45, "zoom": 1.0},
  "story": {"lines": ["DAĞLARIN", "HAYVANLARI"], "info": "8.849 metre · 5 bölge · 26 canlı"}
}
```
- **Başlık** (sahibinin kuralı): profesyonel YouTuber tarzı, **kısa (≤60 karakter), merak uyandıran**, duygusal. Bir arama kelimesi içersin (konu adı). `|`, "(Belgesel)" ve "0'dan X metreye" gibi tarif eden kalıplar **yok**. Kapak yazısını tekrar etme, onu tamamlasın. Yalan vaat (clickbait) yok. Başlıkta mutlaka hayvan/canlı vurgusu olsun. Örnekler: "Okyanusun Dibine İndikçe Canlılar Daha da Tuhaflaşıyor", "Işığın Hiç Ulaşmadığı Yerde Yaşayan Canlılar".
- **Kapak** (`thumb`): 3 satır, satır başına ≤12 karakter, büyük harf. 1. satır sarı (genelde rakam), diğerleri beyaz. Merak sorusu ("… KİM YAŞIYOR?"). `photo`: en çarpıcı fotoğrafın anahtarı (dosya adı uzantısız); `cx`/`cy` hayvanın konumu (0-1). Hayvan sağ yarıda büyük görünmeli.
- `story.lines`: Instagram hikâyesi için 2-3 kısa satır (≤11 karakter).
- Açıklamanın geri kalanı (bölümler, görsel kaynakları, müzik) otomatik eklenir.

## 6. Kontrol ve commit

1. Klasör: `youtube/docs/<YYYYMMDD>_<konu>` (tarih = bugün, konu küçük harf ve Türkçe karaktersiz, ör. `20261110_everest`).
2. `python youtube/tools/fetch_photos.py youtube/docs/<klasör>` (eksik indirmeleri tamamlar), sonra `python youtube/tools/check_doc.py youtube/docs/<klasör>`. Hata varsa düzelt ve tekrar çalıştır. **OK görmeden commit'leme.**
3. `python youtube/tools/kapak.py youtube/docs/<klasör>` çalıştır ve `out/kapak.jpg`'yi Read ile aç. Yazı okunaklı mı, hayvan görünüyor mu? Değilse `thumb` ayarlarını değiştir.
4. `youtube/published.md` sonuna yeni bölüm ekle: `## <tarih> · <başlık> (<aralık>, <yön>)` ve `Canlılar: Ad (bilimsel ad), ...`.
5. `git add youtube/docs/<klasör>/script.json youtube/docs/<klasör>/photos.json youtube/docs/<klasör>/meta.json youtube/published.md && git commit -m "Belgesel: <başlık>" && git push` (çakışmada `git pull --rebase` ve tekrar push).
6. Son mesajında konuyu, başlığı, canlı sayısını, toplam karakteri ve fotoğraf sorunlarını kısaca yaz.

## Asla yapma

- YouTube'a ya da Instagram'a doğrudan bir şey yükleme. `youtube/tools/yt_upload.py`'yi çalıştırma.
- `youtube/tools/`, `youtube/assets/`, `tools/`, `assets/`, `.github/` dosyalarını değiştirme. Bir hata bulursan son mesajında açıkla.
- Daha önce üretilmiş belgesel klasörlerini (`status.json` olanlar) değiştirme.
